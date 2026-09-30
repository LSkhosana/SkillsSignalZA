export type ApiErrorPayload = {
  message: string;
  status: number | null;
  code?: string;
  details?: unknown;
};

export class ApiError extends Error {
  readonly status: number | null;
  readonly code?: string;
  readonly details?: unknown;

  constructor({ message, status, code, details }: ApiErrorPayload) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }

  if (error instanceof Error) {
    return new ApiError({
      message: error.message,
      status: null,
      code: codeFromThrownMessage(error.message),
      details: error,
    });
  }

  return new ApiError({
    message: 'An unexpected error occurred.',
    status: null,
    details: error,
  });
}

function codeFromThrownMessage(message: string): string | undefined {
  const normalized = message.toLowerCase();
  if (normalized.includes('expo_public_api_url') || normalized.includes('missing required environment')) {
    return 'API_URL_MISSING';
  }
  if (
    normalized === 'failed to fetch' ||
    normalized === 'network request failed' ||
    normalized.includes('networkerror') ||
    normalized.includes('load failed')
  ) {
    return 'ASSESSMENT_SERVICE_UNAVAILABLE';
  }
  return undefined;
}
