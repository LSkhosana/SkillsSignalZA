export type PaymentPhase =
  | 'claiming'
  | 'summary'
  | 'initializing'
  | 'checkout_opened'
  | 'waiting'
  | 'delayed'
  | 'succeeded'
  | 'blocked'
  | 'error';

export function canStartPaymentInitialization(
  phase: PaymentPhase,
  inFlight: boolean,
  hasAuthorizationUrl: boolean,
): boolean {
  if (inFlight || hasAuthorizationUrl) {
    return false;
  }
  return phase === 'summary' || phase === 'error';
}

export function canReopenCheckout(phase: PaymentPhase, authorizationUrl: string | null): boolean {
  if (!authorizationUrl) {
    return false;
  }
  return (
    phase === 'checkout_opened' ||
    phase === 'waiting' ||
    phase === 'delayed' ||
    phase === 'error'
  );
}

export function canCheckPayment(phase: PaymentPhase): boolean {
  return phase !== 'claiming' && phase !== 'succeeded' && phase !== 'blocked';
}

export function shouldMarkPaymentDelayed(attempts: number, maxAttempts: number, stillLocked: boolean): boolean {
  return stillLocked && attempts >= maxAttempts;
}
