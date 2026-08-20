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
      details: error,
    });
  }

  return new ApiError({
    message: 'An unexpected error occurred.',
    status: null,
    details: error,
  });
}
