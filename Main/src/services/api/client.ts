import { getApiBaseUrl, getOptionalPublicEnv } from '@/lib/env';

import { ApiError, toApiError } from './errors';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export type ApiRequestOptions = {
  method?: HttpMethod;
  body?: unknown;
  accessToken?: string | null;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

export type ApiSuccess<T> = {
  ok: true;
  data: T;
  status: number;
};

export type ApiFailure = {
  ok: false;
  error: ApiError;
  status: number | null;
};

export type ApiResult<T> = ApiSuccess<T> | ApiFailure;

function joinUrl(baseUrl: string, path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${baseUrl}${normalizedPath}`;
}

function isJsonContentType(contentType: string | null): boolean {
  return Boolean(contentType?.toLowerCase().includes('application/json'));
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get('content-type');
  if (isJsonContentType(contentType)) {
    return response.json() as Promise<unknown>;
  }

  const text = await response.text();
  return text.length > 0 ? text : null;
}

function errorMessageFromBody(body: unknown, fallback: string): string {
  if (typeof body === 'string' && body.trim().length > 0) {
    return body;
  }

  if (body && typeof body === 'object') {
    const record = body as Record<string, unknown>;
    if (typeof record.message === 'string' && record.message.length > 0) {
      return record.message;
    }
    if (typeof record.error === 'string' && record.error.length > 0) {
      return record.error;
    }
  }

  return fallback;
}

function errorCodeFromBody(body: unknown): string | undefined {
  if (body && typeof body === 'object' && typeof (body as { code?: unknown }).code === 'string') {
    return (body as { code: string }).code;
  }

  return undefined;
}

export function createApiClient(getAccessToken?: () => string | null | undefined) {
  async function requestResult<T>(
    path: string,
    options: ApiRequestOptions = {},
  ): Promise<ApiResult<T>> {
    try {
      const baseUrl = getApiBaseUrl();
      const method = options.method ?? 'GET';
      const headers: Record<string, string> = {
        Accept: 'application/json',
        ...options.headers,
      };

      const token = options.accessToken ?? getAccessToken?.() ?? null;
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      const init: RequestInit = {
        method,
        headers,
        signal: options.signal,
      };

      if (options.body !== undefined) {
        headers['Content-Type'] = 'application/json';
        init.body = JSON.stringify(options.body);
      }

      const response = await fetch(joinUrl(baseUrl, path), init);
      const body = await parseBody(response);

      if (!response.ok) {
        const error = new ApiError({
          message: errorMessageFromBody(body, `Request failed with status ${response.status}.`),
          status: response.status,
          code: errorCodeFromBody(body),
          details: body,
        });

        return { ok: false, error, status: response.status };
      }

      return { ok: true, data: body as T, status: response.status };
    } catch (error) {
      const apiError = toApiError(error);
      return { ok: false, error: apiError, status: apiError.status };
    }
  }

  async function request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    const result = await requestResult<T>(path, options);
    if (!result.ok) {
      throw result.error;
    }

    return result.data;
  }

  return { request, requestResult };
}

export const apiClient = createApiClient();

export function hasApiBaseUrl(): boolean {
  return Boolean(getOptionalPublicEnv('EXPO_PUBLIC_API_URL'));
}
