import {
  buildAssessmentFormData,
  claimAssessment,
  createApiClient,
  getReport,
  initializePayment,
  submitAssessment,
} from '@/services/api';

import { formField, headerMap, jsonResponse, PAYMENT_INITIALIZED } from './fixtures';

describe('API client and assessment operations', () => {
  it('preserves multipart boundary behavior and exact link envelope', async () => {
    let captured: RequestInit | undefined;
    const fetchImpl = jest.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      captured = init;
      return jsonResponse(201, {
        schema_version: 'anonymous.assessment.v1',
        state: 'COMPLETED',
        assessment_id: 'a-test-1',
        run_id: 'r-test-1',
        access_state: 'PREVIEW',
        claim_token: 'token',
        preview: { schema_version: 'readiness.preview.v1' },
        error_code: null,
      });
    });
    const client = createApiClient({ fetchImpl });
    const result = await submitAssessment(
      {
        track: 'software_engineering',
        cv: {
          uri: 'file:///tmp/cv.pdf',
          name: 'cv.pdf',
          mimeType: 'application/pdf',
          size: 2048,
        },
        links: [{ submitted_url: 'https://github.com/example/app', declared_type: 'repository' }],
      },
      { client },
    );

    expect(result.ok).toBe(true);
    expect(captured?.body).toBeInstanceOf(FormData);
    const headers = headerMap(captured);
    expect(headers['Content-Type']).toBeUndefined();
    expect(headers['content-type']).toBeUndefined();
    const links = JSON.parse(formField(captured?.body as FormData, 'links') ?? 'null');
    expect(links).toEqual([{ submitted_url: 'https://github.com/example/app', declared_type: 'repository' }]);
    expect(formField(captured?.body as FormData, 'track')).toBe('software_engineering');
    expect(Object.keys(links[0]).sort()).toEqual(['declared_type', 'submitted_url']);
  });

  it('buildAssessmentFormData keeps only submitted_url and declared_type', async () => {
    const form = await buildAssessmentFormData({
      track: 'data_analytics',
      cv: { uri: 'file:///tmp/cv.docx', name: 'cv.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', size: 100 },
      links: [{ submitted_url: 'https://kaggle.com/user', declared_type: 'kaggle' }],
    });
    expect(JSON.parse(formField(form, 'links') ?? '[]')).toEqual([
      { submitted_url: 'https://kaggle.com/user', declared_type: 'kaggle' },
    ]);
  });

  it('attaches a bearer token only when available', async () => {
    const withToken = jest.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => jsonResponse(200, { schema_version: 'assessment.claim.v1', state: 'CLAIMED', assessment_id: 'a-test-1', access_state: 'PREVIEW', claimed_at: '2026-09-11T08:00:00Z', error_code: null }));
    const withoutToken = jest.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      expect(headerMap(init).Authorization).toBeUndefined();
      return jsonResponse(401, { schema_version: 'assessment.claim.v1', state: 'FAILED', assessment_id: 'a-test-1', access_state: null, claimed_at: null, error_code: 'AUTH_REQUIRED' });
    });

    await claimAssessment('a-test-1', 'claim-token', {
      accessToken: 'tok_live',
      client: createApiClient({ fetchImpl: withToken }),
    });
    expect(headerMap(withToken.mock.calls[0][1]).Authorization).toBe('Bearer tok_live');

    const missing = await claimAssessment('a-test-1', 'claim-token', {
      accessToken: null,
      client: createApiClient({ fetchImpl: withoutToken }),
    });
    expect(missing.ok).toBe(false);
    expect(missing.ok === false && missing.error.code).toBe('AUTH_REQUIRED');
  });

  it('preserves backend error_code on JSON failures', async () => {
    const client = createApiClient({
      fetchImpl: async () =>
        jsonResponse(402, {
          schema_version: 'assessment.report.v1',
          state: 'FAILED',
          assessment_id: 'a-test-1',
          error_code: 'REPORT_LOCKED',
        }),
    });
    const result = await getReport('a-test-1', { accessToken: 'tok', client });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('REPORT_LOCKED');
      expect(result.status).toBe(402);
    }
  });

  it('initializes payment with bearer auth and no client body', async () => {
    const fetchImpl = jest.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe('POST');
      expect(init?.body).toBeUndefined();
      expect(headerMap(init).Authorization).toBe('Bearer tok_pay');
      expect(headerMap(init)['Content-Type']).toBeUndefined();
      const serialized = JSON.stringify(init ?? {});
      expect(serialized).not.toContain('15900');
      expect(serialized).not.toContain('ZAR');
      expect(serialized).not.toContain('email');
      expect(serialized).not.toContain('amount');
      expect(serialized).not.toContain('currency');
      return jsonResponse(200, PAYMENT_INITIALIZED);
    });
    const result = await initializePayment('a-test-1', {
      accessToken: 'tok_pay',
      client: createApiClient({ fetchImpl }),
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.authorization_url).toBe('https://checkout.paystack.com/test-session');
    }
  });

  it('sends bearer token on report GET', async () => {
    const fetchImpl = jest.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      expect(String(url)).toContain('/api/v1/assessments/a-test-1/report');
      expect(init?.method).toBe('GET');
      expect(headerMap(init).Authorization).toBe('Bearer tok_report');
      return jsonResponse(200, { schema_version: 'readiness.report.v1', assessment_id: 'a-test-1' });
    });
    const result = await getReport('a-test-1', {
      accessToken: 'tok_report',
      client: createApiClient({ fetchImpl }),
    });
    expect(result.ok).toBe(true);
  });
});
