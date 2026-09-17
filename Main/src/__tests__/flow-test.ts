import { createApiClient } from '@/services/api';
import {
  checkReportUnlock,
  continueAfterAuthentication,
  deleteClaimToken,
  loadClaimToken,
  loadPendingAssessment,
  saveClaimToken,
  savePendingAssessment,
  setClaimTokenStoreForTests,
  setPendingAssessmentStorageForTests,
  startCheckout,
} from '@/services/flow';

import {
  ALREADY_UNLOCKED,
  jsonResponse,
  PAYMENT_INITIALIZED,
  PREVIEW_FIXTURE,
  REPORT_FIXTURE,
} from './fixtures';

function memoryStore() {
  const data = new Map<string, string>();
  return {
    getItem: async (key: string) => data.get(key) ?? null,
    setItem: async (key: string, value: string) => {
      data.set(key, value);
    },
    removeItem: async (key: string) => {
      data.delete(key);
    },
    snapshot: () => data,
  };
}

describe('pending assessment and checkout continuation', () => {
  const pending = memoryStore();
  const secrets = memoryStore();

  beforeEach(async () => {
    pending.snapshot().clear();
    secrets.snapshot().clear();
    setPendingAssessmentStorageForTests(pending);
    setClaimTokenStoreForTests(secrets);
    await savePendingAssessment({
      assessment_id: 'a-test-1',
      preview: PREVIEW_FIXTURE,
      claimed: false,
    });
    await saveClaimToken('a-test-1', 'raw-claim-token-value');
  });

  afterEach(() => {
    setPendingAssessmentStorageForTests(null);
    setClaimTokenStoreForTests(null);
  });

  it('stores pending assessment without the raw claim token', async () => {
    const loaded = await loadPendingAssessment();
    expect(loaded?.assessment_id).toBe('a-test-1');
    expect(loaded?.preview.final_score).toBe(72);
    expect(JSON.stringify(loaded)).not.toContain('raw-claim-token-value');
    expect(await loadClaimToken('a-test-1')).toBe('raw-claim-token-value');
  });

  it('deletes the claim token after a successful claim', async () => {
    const client = createApiClient({
      fetchImpl: async () =>
        jsonResponse(200, {
          schema_version: 'assessment.claim.v1',
          state: 'CLAIMED',
          assessment_id: 'a-test-1',
          access_state: 'PREVIEW',
          claimed_at: '2026-09-11T08:00:00Z',
          error_code: null,
        }),
    });
    const result = await continueAfterAuthentication('a-test-1', { accessToken: 'tok', client });
    expect(result.status).toBe('claimed');
    expect(await loadClaimToken('a-test-1')).toBeNull();
    expect((await loadPendingAssessment())?.claimed).toBe(true);
  });

  it('routes to auth before checkout when there is no session', async () => {
    const claim = await continueAfterAuthentication('a-test-1', { accessToken: null });
    expect(claim.status).toBe('needs_auth');
    expect(await loadClaimToken('a-test-1')).toBe('raw-claim-token-value');
    const checkout = await startCheckout('a-test-1', { accessToken: null });
    expect(checkout.status).toBe('needs_auth');
  });

  it('treats same-owner retry without a stored token as continuation', async () => {
    await deleteClaimToken('a-test-1');
    const result = await continueAfterAuthentication('a-test-1', { accessToken: 'tok' });
    expect(result.status).toBe('already_claimed');
  });

  it('blocks payment on wrong-owner and expired claims', async () => {
    const wrongOwner = createApiClient({
      fetchImpl: async () =>
        jsonResponse(409, {
          schema_version: 'assessment.claim.v1',
          state: 'FAILED',
          assessment_id: 'a-test-1',
          access_state: null,
          claimed_at: null,
          error_code: 'ASSESSMENT_ALREADY_CLAIMED',
        }),
    });
    const blocked = await continueAfterAuthentication('a-test-1', {
      accessToken: 'tok',
      client: wrongOwner,
    });
    expect(blocked.status).toBe('blocked');
    expect(blocked.status === 'blocked' && blocked.code).toBe('ASSESSMENT_ALREADY_CLAIMED');
    expect(await loadClaimToken('a-test-1')).toBeNull();

    await saveClaimToken('a-test-1', 'raw-claim-token-value');
    const expired = createApiClient({
      fetchImpl: async () =>
        jsonResponse(410, {
          schema_version: 'assessment.claim.v1',
          state: 'FAILED',
          assessment_id: 'a-test-1',
          access_state: null,
          claimed_at: null,
          error_code: 'CLAIM_EXPIRED',
        }),
    });
    const expiredResult = await continueAfterAuthentication('a-test-1', {
      accessToken: 'tok',
      client: expired,
    });
    expect(expiredResult.status).toBe('blocked');
    expect(expiredResult.status === 'blocked' && expiredResult.code).toBe('CLAIM_EXPIRED');
  });

  it('skips checkout when payment returns ALREADY_UNLOCKED', async () => {
    const result = await startCheckout('a-test-1', {
      accessToken: 'tok',
      client: createApiClient({ fetchImpl: async () => jsonResponse(200, ALREADY_UNLOCKED) }),
    });
    expect(result).toEqual({ status: 'already_unlocked' });
  });

  it('uses only the server-returned authorization URL', async () => {
    const result = await startCheckout('a-test-1', {
      accessToken: 'tok',
      client: createApiClient({ fetchImpl: async () => jsonResponse(200, PAYMENT_INITIALIZED) }),
    });
    expect(result.status).toBe('payment_initialized');
    expect(result.status === 'payment_initialized' && result.authorizationUrl).toBe(
      'https://checkout.paystack.com/test-session',
    );
  });

  it('stays waiting on REPORT_LOCKED and transitions on 200 report', async () => {
    const locked = await checkReportUnlock('a-test-1', {
      accessToken: 'tok',
      client: createApiClient({
        fetchImpl: async () =>
          jsonResponse(402, {
            schema_version: 'assessment.report.v1',
            state: 'FAILED',
            assessment_id: 'a-test-1',
            error_code: 'REPORT_LOCKED',
          }),
      }),
    });
    expect(locked).toEqual({ status: 'locked' });

    const unlocked = await checkReportUnlock('a-test-1', {
      accessToken: 'tok',
      client: createApiClient({ fetchImpl: async () => jsonResponse(200, REPORT_FIXTURE) }),
    });
    expect(unlocked.status).toBe('unlocked');
    expect(unlocked.status === 'unlocked' && unlocked.report.schema_version).toBe('readiness.report.v1');
  });
});
