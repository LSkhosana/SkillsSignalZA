import { ASSESSMENTS_PATH } from '@/lib/constants';
import { getAccessToken } from '@/services/auth';

import { apiClient, type ApiClient, type ApiResult } from './client';
import { ApiError } from './errors';
import type {
  AnonymousAssessmentOutcome,
  AssessmentClaimOutcome,
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
