import { authResumeHref, authResumeParams } from '@/lib/auth-resume';
import {
  canCheckPayment,
  canReopenCheckout,
  canStartPaymentInitialization,
  shouldMarkPaymentDelayed,
} from '@/lib/payment-workspace';

describe('auth resume', () => {
  it('resumes payment, report or preview without extra params', () => {
    expect(authResumeHref('a-test-1', 'payment')).toBe('/assessment/a-test-1/payment');
    expect(authResumeHref('a-test-1', 'report')).toBe('/assessment/a-test-1/report');
    expect(authResumeHref('a-test-1', 'preview')).toBe('/assessment/a-test-1/preview');
    expect(authResumeHref(undefined, 'payment')).toBe('/');
    expect(authResumeParams('a-test-1', 'payment')).toEqual({ assessmentId: 'a-test-1', next: 'payment' });
    expect(JSON.stringify(authResumeParams('a-test-1', 'payment'))).not.toMatch(/claim/i);
  });
});

describe('payment workspace transitions', () => {
  it('blocks duplicate initialization and allows reopen of an existing checkout URL', () => {
    expect(canStartPaymentInitialization('summary', false, false)).toBe(true);
    expect(canStartPaymentInitialization('summary', true, false)).toBe(false);
    expect(canStartPaymentInitialization('summary', false, true)).toBe(false);
    expect(canStartPaymentInitialization('waiting', false, false)).toBe(false);
    expect(canStartPaymentInitialization('blocked', false, false)).toBe(false);
    expect(canReopenCheckout('waiting', 'https://checkout.paystack.com/test-session')).toBe(true);
    expect(canReopenCheckout('summary', 'https://checkout.paystack.com/test-session')).toBe(false);
    expect(canCheckPayment('claiming')).toBe(false);
    expect(canCheckPayment('waiting')).toBe(true);
    expect(shouldMarkPaymentDelayed(20, 20, true)).toBe(true);
    expect(shouldMarkPaymentDelayed(3, 20, true)).toBe(false);
  });
});
