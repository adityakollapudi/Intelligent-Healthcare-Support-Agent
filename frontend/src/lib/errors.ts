// Normalized API errors (backend format: doc 06 §4).

export type ApiErrorKind = "http" | "network" | "timeout" | "aborted" | "invalid_response";

export interface ApiErrorDetail {
  field?: string | null;
  issue: string;
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly code: string;
  readonly requestId: string | null;
  readonly details: ApiErrorDetail[];
  readonly retryAfterSeconds: number | null;

  constructor(init: {
    kind: ApiErrorKind;
    message: string;
    status?: number | null;
    code?: string;
    requestId?: string | null;
    details?: ApiErrorDetail[];
    retryAfterSeconds?: number | null;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.kind = init.kind;
    this.status = init.status ?? null;
    this.code = init.code ?? init.kind.toUpperCase();
    this.requestId = init.requestId ?? null;
    this.details = init.details ?? [];
    this.retryAfterSeconds = init.retryAfterSeconds ?? null;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

/** Human-readable explanation plus a next step. Never includes server internals. */
export function describeError(error: unknown): { title: string; message: string; retryable: boolean } {
  if (!isApiError(error)) {
    return { title: "Something went wrong", message: "An unexpected problem occurred. Please try again.", retryable: true };
  }
  switch (error.kind) {
    case "network":
      return {
        title: "Can't reach the IHSA service",
        message: "Check that the backend is running and your connection is working, then try again.",
        retryable: true,
      };
    case "timeout":
      return { title: "This is taking longer than expected", message: "The request timed out. Please try again.", retryable: true };
    case "invalid_response":
      return { title: "Unexpected response", message: "The service returned data this screen can't display.", retryable: true };
    case "aborted":
      return { title: "Request cancelled", message: "The request was cancelled.", retryable: true };
  }
  switch (error.status) {
    case 401:
      return { title: "Please sign in again", message: "Your session has ended.", retryable: false };
    case 403:
      return { title: "Not permitted", message: "Your account doesn't have permission to do this.", retryable: false };
    case 404:
      return { title: "Not found", message: "We couldn't find that item.", retryable: false };
    case 422:
      return { title: "Check your input", message: "Some of the information entered isn't valid.", retryable: false };
    case 429:
      return {
        title: "Too many requests",
        message: error.retryAfterSeconds
          ? `Please wait about ${Math.ceil(error.retryAfterSeconds / 60)} minute(s) and try again.`
          : "Please wait a moment and try again.",
        retryable: false,
      };
    case 503:
      return { title: "Service temporarily unavailable", message: "A required service is unavailable. Please try again shortly.", retryable: true };
    default:
      return { title: "Something went wrong", message: "The service hit an unexpected problem. Please try again.", retryable: true };
  }
}
