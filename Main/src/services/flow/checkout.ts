import {
  claimAssessment,
  customerMessageForCode,
  customerMessageFromError,
  getReport,
  initializePayment,
  isAuthError,
  type ApiClient,
  type PaymentCheckoutOutcome,
  type ReadinessReport,
} from '@/services/api';
import { deleteClaimToken, loadClaimToken } from './claim-token';
import { markPendingAssessmentClaimed } from './pending-assessment';

export type ClaimContinuation =
  | { status: 'needs_auth' }
  | { status: 'claimed' }
  | { status: 'already_claimed' }
  | { status: 'blocked'; code: string; message: string }
  | { status: 'error'; code?: string; message: string };

export type CheckoutContinuation =
  | { status: 'needs_auth' }
  | { status: 'already_unlocked' }
  | { status: 'payment_initialized'; authorizationUrl: string }
  | { status: 'waiting'; message: string }
  | { status: 'blocked'; code: string; message: string }
  | { status: 'error'; code?: string; message: string };

export type ReportContinuation =
  | { status: 'unlocked'; report: ReadinessReport }
  | { status: 'locked' }
  | { status: 'needs_auth' }
  | { status: 'blocked'; code: string; message: string }
  | { status: 'error'; code?: string; message: string };

const BLOCKING_CLAIM_CODES = new Set([
  'CLAIM_TOKEN_INVALID',
  'CLAIM_EXPIRED',
  'ASSESSMENT_ALREADY_CLAIMED',
  'ASSESSMENT_NOT_FOUND',
  'INVALID_CLAIM_REQUEST',
]);

type FlowClientOptions = {
  accessToken?: string | null;
  client?: ApiClient;
};

export async function continueAfterAuthentication(
  assessmentId: string,
  options: FlowClientOptions = {},
): Promise<ClaimContinuation> {
  if (!options.accessToken) {
    return { status: 'needs_auth' };
  }

  const claimToken = await loadClaimToken(assessmentId);
  if (!claimToken) {
    return { status: 'already_claimed' };
  }

  const result = await claimAssessment(assessmentId, claimToken, options);
  if (!result.ok) {
    if (isAuthError(result.error)) {
      return { status: 'needs_auth' };
    }
    const code = result.error.code ?? 'CLAIM_SERVICE_UNAVAILABLE';
    const message = customerMessageFromError(
      result.error,
      'This assessment could not be claimed. Start a new assessment.',
    );
    if (BLOCKING_CLAIM_CODES.has(code)) {
      await deleteClaimToken(assessmentId);
      return { status: 'blocked', code, message };
    }
    return { status: 'error', code, message };
  }

  if (result.data.state === 'CLAIMED') {
    await deleteClaimToken(assessmentId);
    await markPendingAssessmentClaimed(assessmentId);
    return { status: 'claimed' };
  }

  const code = result.data.error_code ?? 'CLAIM_SERVICE_UNAVAILABLE';
  return {
    status: 'blocked',
    code,
    message: customerMessageForCode(code, 'This assessment could not be claimed.'),
  };
}

export async function startCheckout(
  assessmentId: string,
  options: FlowClientOptions = {},
): Promise<CheckoutContinuation> {
  if (!options.accessToken) {
    return { status: 'needs_auth' };
  }

  const result = await initializePayment(assessmentId, options);
  if (!result.ok) {
    if (isAuthError(result.error)) {
      return { status: 'needs_auth' };
    }
    const code = result.error.code ?? 'PAYMENT_SERVICE_UNAVAILABLE';
    if (code === 'ASSESSMENT_NOT_OWNED' || code === 'ASSESSMENT_ALREADY_CLAIMED') {
      return {
        status: 'blocked',
        code,
        message: customerMessageFromError(result.error, 'This assessment is not available on this account.'),
      };
    }
    if (code === 'PAYMENT_INITIALIZING') {
      return {
        status: 'waiting',
        message: customerMessageFromError(result.error, 'Checkout is already in progress.'),
      };
    }
    return {
      status: 'error',
      code,
      message: customerMessageFromError(result.error, 'Payment could not be started.'),
    };
  }

  return continuationFromCheckout(result.data);
}

export function continuationFromCheckout(outcome: PaymentCheckoutOutcome): CheckoutContinuation {
  if (outcome.state === 'ALREADY_UNLOCKED') {
    return { status: 'already_unlocked' };
  }
  if (outcome.state === 'PAYMENT_INITIALIZED') {
    if (!outcome.authorization_url) {
      return {
        status: 'error',
        code: 'PAYMENT_INITIALIZATION_FAILED',
        message: 'Checkout could not be opened. Try again shortly.',
      };
    }
    return { status: 'payment_initialized', authorizationUrl: outcome.authorization_url };
  }
  const code = outcome.error_code ?? 'PAYMENT_SERVICE_UNAVAILABLE';
  return {
    status: 'error',
    code,
    message: customerMessageForCode(code, 'Payment could not be started.'),
  };
}

export async function checkReportUnlock(
  assessmentId: string,
  options: FlowClientOptions = {},
): Promise<ReportContinuation> {
  if (!options.accessToken) {
    return { status: 'needs_auth' };
  }

  const result = await getReport(assessmentId, options);
  if (result.ok) {
    return { status: 'unlocked', report: result.data };
  }
  if (isAuthError(result.error)) {
    return { status: 'needs_auth' };
  }
  if (result.error.code === 'REPORT_LOCKED' || result.status === 402) {
    return { status: 'locked' };
  }
  if (
    result.error.code === 'ASSESSMENT_NOT_OWNED' ||
    result.error.code === 'ASSESSMENT_NOT_FOUND' ||
    result.error.code === 'ASSESSMENT_NOT_COMPLETED'
  ) {
    return {
      status: 'blocked',
      code: result.error.code,
      message: customerMessageFromError(result.error, 'This report is not available.'),
    };
  }
  return {
    status: 'error',
    code: result.error.code,
    message: customerMessageFromError(result.error, 'The report could not be loaded.'),
  };
}
