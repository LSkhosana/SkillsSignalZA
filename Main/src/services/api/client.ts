import { getApiBaseUrl, getOptionalPublicEnv } from '@/lib/env';

import { ApiError, toApiError } from './errors';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

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

export type ApiClient = {
  request: <T>(path: string, options?: ApiRequestOptions) => Promise<T>;
  requestResult: <T>(path: string, options?: ApiRequestOptions) => Promise<ApiResult<T>>;
};

export type CreateApiClientOptions = {
  getAccessToken?: () => string | null | undefined | Promise<string | null | undefined>;
  fetchImpl?: FetchLike;
};

function joinUrl(baseUrl: string, path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${baseUrl}${normalizedPath}`;
}

function isJsonContentType(contentType: string | null): boolean {
  return Boolean(contentType?.toLowerCase().includes('application/json'));
}

function isFormDataBody(body: unknown): body is FormData {
  return typeof FormData !== 'undefined' && body instanceof FormData;
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
  if (!body || typeof body !== 'object') {
    return undefined;
  }

  const record = body as { error_code?: unknown; code?: unknown };
  if (typeof record.error_code === 'string' && record.error_code.length > 0) {
    return record.error_code;
  }
  if (typeof record.code === 'string' && record.code.length > 0) {
    return record.code;
  }

  return undefined;
}

function omitContentType(headers: Record<string, string>): Record<string, string> {
  const next: Record<string, string> = {};
  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === 'content-type') {
      continue;
    }
    next[key] = value;
  }
  return next;
}

export function createApiClient(options: CreateApiClientOptions = {}): ApiClient {
  const fetchImpl = options.fetchImpl ?? fetch;

  async function requestResult<T>(
    path: string,
    requestOptions: ApiRequestOptions = {},
  ): Promise<ApiResult<T>> {
    try {
      const baseUrl = getApiBaseUrl();
      const method = requestOptions.method ?? 'GET';
      let headers: Record<string, string> = {
        Accept: 'application/json',
        ...requestOptions.headers,
      };

      const token = requestOptions.accessToken ?? (await options.getAccessToken?.()) ?? null;
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      const init: RequestInit = {
        method,
        signal: requestOptions.signal,
      };

      if (isFormDataBody(requestOptions.body)) {
        headers = omitContentType(headers);
        init.body = requestOptions.body;
      } else if (requestOptions.body !== undefined) {
        headers['Content-Type'] = 'application/json';
        init.body = JSON.stringify(requestOptions.body);
      }

      init.headers = headers;

      const response = await fetchImpl(joinUrl(baseUrl, path), init);
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

  async function request<T>(path: string, requestOptions: ApiRequestOptions = {}): Promise<T> {
    const result = await requestResult<T>(path, requestOptions);
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
