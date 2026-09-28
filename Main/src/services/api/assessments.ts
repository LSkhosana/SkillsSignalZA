import { ASSESSMENTS_PATH } from '@/lib/constants';
import { getAccessToken } from '@/services/auth';

import { apiClient, type ApiClient, type ApiResult } from './client';
import { ApiError } from './errors';
import type {
  AnonymousAssessmentOutcome,
  AssessmentClaimOutcome,
  AssessmentSummariesOutcome,
  CandidateLinkInput,
  PaymentCheckoutOutcome,
  PickedCvDocument,
  ReadinessReport,
} from './types';

export type SubmitAssessmentInput = {
  track: string;
  cv: PickedCvDocument;
  links: CandidateLinkInput[];
};

export type AssessmentRequestOptions = {
  accessToken?: string | null;
  client?: ApiClient;
  signal?: AbortSignal;
};

function assessmentPath(assessmentId: string, suffix = ''): string {
  return `${ASSESSMENTS_PATH}/${encodeURIComponent(assessmentId)}${suffix}`;
}

async function resolveAccessToken(explicit?: string | null): Promise<string | null> {
  if (explicit !== undefined) {
    return explicit;
  }
  return getAccessToken();
}

export async function buildAssessmentFormData(input: SubmitAssessmentInput): Promise<FormData> {
  const form = new FormData();
  form.append('track', input.track);
  await appendCvPart(form, input.cv);
  form.append('links', JSON.stringify(input.links));
  return form;
}

async function appendCvPart(form: FormData, cv: PickedCvDocument): Promise<void> {
  if (typeof File !== 'undefined' && cv.uri.startsWith('blob:')) {
    const response = await fetch(cv.uri);
    const blob = await response.blob();
    const file = new File([blob], cv.name, { type: cv.mimeType || blob.type });
    form.append('cv', file);
    return;
  }

  if (typeof Blob !== 'undefined' && cv.uri.startsWith('data:')) {
    const response = await fetch(cv.uri);
    const blob = await response.blob();
    form.append('cv', blob);
    return;
  }

  form.append('cv', {
    uri: cv.uri,
    name: cv.name,
    type: cv.mimeType,
  } as unknown as Blob);
}

export async function submitAssessment(
  input: SubmitAssessmentInput,
  options: AssessmentRequestOptions = {},
): Promise<ApiResult<AnonymousAssessmentOutcome>> {
  const client = options.client ?? apiClient;
  const body = await buildAssessmentFormData(input);
  return client.requestResult<AnonymousAssessmentOutcome>(ASSESSMENTS_PATH, {
    method: 'POST',
    body,
    signal: options.signal,
  });
}

export async function claimAssessment(
  assessmentId: string,
  claimToken: string,
  options: AssessmentRequestOptions = {},
): Promise<ApiResult<AssessmentClaimOutcome>> {
  const client = options.client ?? apiClient;
  const accessToken = await resolveAccessToken(options.accessToken);
  return client.requestResult<AssessmentClaimOutcome>(assessmentPath(assessmentId, '/claim'), {
    method: 'POST',
    accessToken,
    body: { claim_token: claimToken },
    signal: options.signal,
  });
}

export async function initializePayment(
  assessmentId: string,
  options: AssessmentRequestOptions = {},
): Promise<ApiResult<PaymentCheckoutOutcome>> {
  const client = options.client ?? apiClient;
  const accessToken = await resolveAccessToken(options.accessToken);
  return client.requestResult<PaymentCheckoutOutcome>(assessmentPath(assessmentId, '/payment'), {
    method: 'POST',
    accessToken,
    signal: options.signal,
  });
}

export async function getReport(
  assessmentId: string,
  options: AssessmentRequestOptions = {},
): Promise<ApiResult<ReadinessReport>> {
  const client = options.client ?? apiClient;
  const accessToken = await resolveAccessToken(options.accessToken);
  const result = await client.requestResult<unknown>(assessmentPath(assessmentId, '/report'), {
    method: 'GET',
    accessToken,
    signal: options.signal,
  });

  if (!result.ok) {
    return result;
  }

  if (!isReadinessReport(result.data)) {
    return {
      ok: false,
      status: result.status,
      error: new ApiError({
        message: 'The report payload was not a readiness report.',
        status: result.status,
        code: 'REPORT_BUILD_FAILED',
        details: result.data,
      }),
    };
  }

  return { ok: true, data: result.data, status: result.status };
}

export function isReadinessReport(value: unknown): value is ReadinessReport {
  return Boolean(
    value &&
      typeof value === 'object' &&
      (value as { schema_version?: unknown }).schema_version === 'readiness.report.v1',
  );
}

export async function listOwnedAssessments(
  options: AssessmentRequestOptions = {},
): Promise<ApiResult<AssessmentSummariesOutcome>> {
  const client = options.client ?? apiClient;
  const accessToken = await resolveAccessToken(options.accessToken);
  const result = await client.requestResult<unknown>(ASSESSMENTS_PATH, {
    method: 'GET',
    accessToken,
    signal: options.signal,
  });

  if (!result.ok) {
    return result;
  }

  const mapped = mapSummariesOutcome(result.data);
  if (!mapped) {
    return {
      ok: false,
      status: result.status,
      error: new ApiError({
        message: 'The reports list could not be read.',
        status: result.status,
        code: 'SUMMARIES_SERVICE_UNAVAILABLE',
        details: result.data,
      }),
    };
  }

  if (mapped.state === 'FAILED') {
    return {
      ok: false,
      status: result.status,
      error: new ApiError({
        message: 'The reports list could not be loaded.',
        status: result.status,
        code: mapped.error_code ?? 'SUMMARIES_SERVICE_UNAVAILABLE',
        details: mapped,
      }),
    };
  }

  return { ok: true, data: mapped, status: result.status };
}

export function isAssessmentSummariesOutcome(value: unknown): value is AssessmentSummariesOutcome {
  return mapSummariesOutcome(value) != null;
}

function mapSummariesOutcome(value: unknown): AssessmentSummariesOutcome | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (record.schema_version !== 'assessment.summaries.v1') {
    return null;
  }
  if (record.state !== 'LISTED' && record.state !== 'FAILED') {
    return null;
  }
  if (!Array.isArray(record.items)) {
    return null;
  }
  const items: AssessmentSummariesOutcome['items'] = [];
  for (const row of record.items) {
    const item = mapSummaryItem(row);
    if (!item) {
      return null;
    }
    items.push(item);
  }
  if (typeof record.limit !== 'number' || typeof record.offset !== 'number' || typeof record.has_more !== 'boolean') {
    return null;
  }
  const errorCode = record.error_code;
  if (errorCode != null && (typeof errorCode !== 'string' || !errorCode.trim())) {
    return null;
  }
  return {
    schema_version: 'assessment.summaries.v1',
    state: record.state,
    items,
    limit: record.limit,
    offset: record.offset,
    has_more: record.has_more,
    error_code: typeof errorCode === 'string' ? errorCode : null,
  };
}

function mapSummaryItem(value: unknown): AssessmentSummariesOutcome['items'][number] | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (typeof record.assessment_id !== 'string' || !record.assessment_id.trim()) {
    return null;
  }
  if (typeof record.track !== 'string' || !record.track.trim()) {
    return null;
  }
  if (record.access_state !== 'PREVIEW' && record.access_state !== 'UNLOCKED') {
    return null;
  }
  if (typeof record.assessed_at !== 'string' || !record.assessed_at.trim()) {
    return null;
  }
  const score = record.final_score;
  if (score != null && (typeof score !== 'number' || !Number.isInteger(score) || score < 0 || score > 100)) {
    return null;
  }
  const band = record.band;
  if (band != null && !isBandId(band)) {
    return null;
  }
  const unlocked = record.unlocked_at;
  if (unlocked != null && (typeof unlocked !== 'string' || !unlocked.trim())) {
    return null;
  }
  return {
    assessment_id: record.assessment_id,
    track: record.track,
    final_score: typeof score === 'number' ? score : null,
    band: isBandId(band) ? band : null,
    access_state: record.access_state,
    assessed_at: record.assessed_at,
    unlocked_at: typeof unlocked === 'string' ? unlocked : null,
  };
}

function isBandId(value: unknown): value is AssessmentSummariesOutcome['items'][number]['band'] {
  return (
    value === 'limited_application_evidence' ||
    value === 'foundation_visible' ||
    value === 'developing_application_readiness' ||
    value === 'strong_application_evidence'
  );
}
