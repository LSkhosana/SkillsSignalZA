import { customerMessageForCode } from '@/services/api/customer-errors';
import type { AnonymousAssessmentOutcome } from '@/services/api/types';

export type WorkspacePhase = 'draft' | 'submitting' | 'review_required' | 'not_scorable' | 'service_failure';

export type SubmissionDisposition =
  | { type: 'preview' }
  | { type: 'review_required'; message: string }
  | { type: 'not_scorable'; message: string }
  | { type: 'service_failure'; message: string };

const SERVICE_FAILURE_CODES = new Set([
  'ASSESSMENT_SERVICE_UNAVAILABLE',
  'ASSESSMENT_PIPELINE_FAILED',
  'STORAGE_FAILED',
  'PERSISTENCE_FAILED',
  'REPORTING_FAILED',
  'API_URL_MISSING',
  'INVALID_SUBMISSION',
]);

export function editingAllowed(phase: WorkspacePhase): boolean {
  return phase === 'draft' || phase === 'service_failure';
}

export function submissionAllowed(phase: WorkspacePhase, inFlight: boolean, ready: boolean): boolean {
  if (inFlight || !ready) {
    return false;
  }
  return phase === 'draft' || phase === 'service_failure';
}

export function paymentAllowedForAssessmentState(state: AnonymousAssessmentOutcome['state']): boolean {
  return state === 'COMPLETED';
}

export function dispositionForOutcome(data: AnonymousAssessmentOutcome): SubmissionDisposition {
  if (data.state === 'REVIEW_REQUIRED') {
    return {
      type: 'review_required',
      message: customerMessageForCode('REVIEW_REQUIRED', 'This assessment needs review.'),
    };
  }

  if (data.state === 'COMPLETED' && data.preview && data.claim_token) {
    return { type: 'preview' };
  }

  if (data.state === 'FAILED' || (data.error_code != null && SERVICE_FAILURE_CODES.has(data.error_code))) {
    return {
      type: 'service_failure',
      message: customerMessageForCode(
        data.error_code ?? 'ASSESSMENT_SERVICE_UNAVAILABLE',
        'The assessment could not be submitted.',
      ),
    };
  }

  return {
    type: 'not_scorable',
    message: customerMessageForCode(data.error_code ?? 'NOT_SCORABLE', 'This submission could not produce a preview.'),
  };
}

export function paymentAllowedForDisposition(type: SubmissionDisposition['type']): boolean {
  return type === 'preview';
}
