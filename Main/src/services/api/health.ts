import { apiClient, hasApiBaseUrl, type ApiResult } from './client';
import { ApiError } from './errors';

export const HEALTH_PATH = '/api/v1/health';

export type HealthResponse = {
  status: string;
};

function isHealthResponse(value: unknown): value is HealthResponse {
  return Boolean(
    value &&
      typeof value === 'object' &&
      typeof (value as { status?: unknown }).status === 'string',
  );
}

/**
 * Calls GET /api/v1/health when an API base URL is configured.
 * Returns a normalized failure instead of throwing so the UI can render
 * while Server/ is not running yet.
 */
export async function getHealth(): Promise<ApiResult<HealthResponse>> {
  if (!hasApiBaseUrl()) {
    return {
      ok: false,
      status: null,
      error: new ApiError({
        message: 'EXPO_PUBLIC_API_URL is not set. The app can still run without a server.',
        status: null,
        code: 'API_URL_MISSING',
      }),
    };
  }

  const result = await apiClient.requestResult<unknown>(HEALTH_PATH, { method: 'GET' });

  if (!result.ok) {
    return result;
  }

  if (!isHealthResponse(result.data)) {
    return {
      ok: false,
      status: result.status,
      error: new ApiError({
        message: 'Health endpoint returned an unexpected payload.',
        status: result.status,
        code: 'HEALTH_INVALID_PAYLOAD',
        details: result.data,
      }),
    };
  }

  return { ok: true, data: result.data, status: result.status };
}
