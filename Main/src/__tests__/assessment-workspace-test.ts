import {
  dispositionForOutcome,
  editingAllowed,
  paymentAllowedForAssessmentState,
  paymentAllowedForDisposition,
  submissionAllowed,
} from '@/lib/assessment-workspace';
import { validateEvidenceUrl } from '@/lib/evidence-url';
import type { AnonymousAssessmentOutcome } from '@/services/api';

import { COMPLETED_ASSESSMENT } from './fixtures';

function outcome(
  patch: Partial<AnonymousAssessmentOutcome> & Pick<AnonymousAssessmentOutcome, 'state'>,
): AnonymousAssessmentOutcome {
  return {
    schema_version: 'anonymous.assessment.v1',
    assessment_id: 'a-1',
    run_id: 'r-1',
    access_state: null,
    claim_token: null,
    preview: null,
    error_code: null,
    ...patch,
  };
}

describe('assessment workspace transitions', () => {
  it('blocks submit until a valid submission is idle in draft', () => {
    expect(submissionAllowed('draft', false, false)).toBe(false);
    expect(submissionAllowed('draft', false, true)).toBe(true);
    expect(submissionAllowed('submitting', false, true)).toBe(false);
    expect(submissionAllowed('draft', true, true)).toBe(false);
    expect(submissionAllowed('review_required', false, true)).toBe(false);
    expect(submissionAllowed('not_scorable', false, true)).toBe(false);
    expect(submissionAllowed('service_failure', false, true)).toBe(true);
    expect(submissionAllowed('service_failure', true, true)).toBe(false);
  });

  it('locks editing during submission and blocked outcomes', () => {
    expect(editingAllowed('draft')).toBe(true);
    expect(editingAllowed('service_failure')).toBe(true);
    expect(editingAllowed('submitting')).toBe(false);
    expect(editingAllowed('review_required')).toBe(false);
    expect(editingAllowed('not_scorable')).toBe(false);
  });

  it('allows payment only from a completed preview', () => {
    expect(paymentAllowedForAssessmentState('COMPLETED')).toBe(true);
    expect(paymentAllowedForAssessmentState('REVIEW_REQUIRED')).toBe(false);
    expect(paymentAllowedForAssessmentState('NOT_SCORABLE')).toBe(false);
    expect(paymentAllowedForAssessmentState('FAILED')).toBe(false);

    expect(paymentAllowedForDisposition(dispositionForOutcome(COMPLETED_ASSESSMENT).type)).toBe(true);
    expect(
      paymentAllowedForDisposition(
        dispositionForOutcome(outcome({ state: 'REVIEW_REQUIRED', error_code: 'REVIEW_REQUIRED' })).type,
      ),
    ).toBe(false);
    expect(
      paymentAllowedForDisposition(
        dispositionForOutcome(outcome({ state: 'NOT_SCORABLE', error_code: 'NOT_SCORABLE' })).type,
      ),
    ).toBe(false);
    expect(
      paymentAllowedForDisposition(
        dispositionForOutcome(outcome({ state: 'FAILED', error_code: 'ASSESSMENT_SERVICE_UNAVAILABLE' })).type,
      ),
    ).toBe(false);
    expect(dispositionForOutcome(outcome({ state: 'COMPLETED', preview: null, claim_token: null })).type).toBe(
      'not_scorable',
    );
  });

  it('rejects malformed evidence URLs and accepts public http(s) URLs', () => {
    expect(validateEvidenceUrl('')).toBeNull();
    expect(validateEvidenceUrl('   ')).toBeNull();
    expect(validateEvidenceUrl('notaurl')).toBeTruthy();
    expect(validateEvidenceUrl('javascript:alert(1)')).toBeTruthy();
    expect(validateEvidenceUrl('https://github.com/example/app')).toBeNull();
    expect(validateEvidenceUrl('http://portfolio.example')).toBeNull();
  });
});
