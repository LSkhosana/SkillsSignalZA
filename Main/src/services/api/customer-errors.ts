import { ApiError } from './errors';

const CUSTOMER_MESSAGES: Record<string, string> = {
  INVALID_SUBMISSION: 'The submission could not be accepted. Check the CV and links, then try again.',
  UNSUPPORTED_MEDIA_TYPE: 'Please upload a PDF or DOCX file.',
  FILE_TOO_LARGE: 'The CV must be 10 MB or smaller.',
  TOO_MANY_LINKS: 'You can add up to five links.',
  ASSESSMENT_SERVICE_UNAVAILABLE: 'The assessment service is temporarily unavailable. Try again shortly.',
  ASSESSMENT_PIPELINE_FAILED: 'The assessment service is temporarily unavailable. Try again shortly.',
  STORAGE_FAILED: 'The assessment service is temporarily unavailable. Try again shortly.',
  PERSISTENCE_FAILED: 'The assessment could not be saved. Try again shortly.',
  REPORTING_FAILED: 'The preview could not be prepared. Try again shortly.',
  NOT_SCORABLE: 'This submission could not be scored. Start a new assessment with a clearer CV.',
  REVIEW_REQUIRED: 'This assessment needs review and cannot unlock a full report yet.',
  AUTH_REQUIRED: 'Sign in to continue.',
  AUTH_INVALID: 'Your session is no longer valid. Sign in again.',
  AUTH_SERVICE_UNAVAILABLE: 'Sign-in is temporarily unavailable. Try again shortly.',
  INVALID_CLAIM_REQUEST: 'This assessment could not be claimed. Start a new assessment.',
  CLAIM_TOKEN_INVALID: 'This assessment cannot be claimed. Start a new assessment.',
  CLAIM_EXPIRED: 'The claim window has expired. Start a new assessment.',
  ASSESSMENT_ALREADY_CLAIMED: 'This assessment belongs to a different account.',
  CLAIM_SERVICE_UNAVAILABLE: 'Claiming is temporarily unavailable. Try again shortly.',
  ASSESSMENT_NOT_FOUND: 'This assessment is no longer available.',
  ASSESSMENT_NOT_OWNED: 'This assessment is not available on this account.',
  ASSESSMENT_NOT_COMPLETED: 'This assessment is not ready yet.',
  PAYMENT_EMAIL_REQUIRED: 'Your account needs a valid email address before checkout.',
  PAYMENT_INITIALIZING: 'Checkout is already in progress. Wait a moment, then check payment.',
  PAYMENT_SERVICE_UNAVAILABLE: 'Payment is temporarily unavailable. Try again shortly.',
  PAYMENT_INITIALIZATION_FAILED: 'Payment could not be started. Try again shortly.',
  PAYMENT_RULESET_INVALID: 'Payment is temporarily unavailable. Try again shortly.',
  REPORT_LOCKED: 'Payment has not unlocked the report yet. Complete checkout, then check again.',
  REPORT_BUILD_FAILED: 'The report could not be loaded. Try again shortly.',
  REPORT_SERVICE_UNAVAILABLE: 'The report service is temporarily unavailable. Try again shortly.',
  API_URL_MISSING: 'The app is not configured to reach the assessment service.',
};

export function customerMessageForCode(code: string | undefined, fallback: string): string {
  if (code && CUSTOMER_MESSAGES[code]) {
    return CUSTOMER_MESSAGES[code];
  }
  return fallback;
}

export function customerMessageFromError(error: ApiError, fallback: string): string {
  return customerMessageForCode(error.code, fallback);
}

export function isAuthError(error: ApiError): boolean {
  return error.status === 401 || error.code === 'AUTH_REQUIRED' || error.code === 'AUTH_INVALID';
}
