// The single HTTP client for the IHSA backend. Tokens and bodies are never logged.
import { config } from "./config";
import { ApiError, type ApiErrorDetail } from "./errors";

type Validator<T> = (value: unknown) => value is T;

export interface RequestOptions<T> {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  query?: Record<string, string | number | string[] | undefined | null>;
  body?: unknown;
  signal?: AbortSignal;
  /** Runtime shape check; responses failing it become `invalid_response` errors. */
  validate?: Validator<T>;
  /** Attach the bearer token (default true). */
  auth?: boolean;
  /** Return null on 2xx-with-no-body (204). */
  expectEmpty?: boolean;
}

interface SessionHooks {
  getToken: () => string | null;
  onUnauthorized: () => void;
}

let hooks: SessionHooks = { getToken: () => null, onUnauthorized: () => undefined };

/** Called once by the session provider; keeps the token in memory only. */
export function configureSession(next: SessionHooks): void {
  hooks = next;
}

export function buildUrl(path: string, query?: RequestOptions<unknown>["query"]): string {
  const url = new URL(config.apiBaseUrl + (path.startsWith("/") ? path : `/${path}`));
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    for (const item of Array.isArray(value) ? value : [value]) url.searchParams.append(key, String(item));
  }
  return url.toString();
}

function parseErrorBody(body: unknown): { code?: string; message?: string; requestId?: string; details?: ApiErrorDetail[] } {
  if (typeof body !== "object" || body === null || !("error" in body)) return {};
  const err = (body as { error: Record<string, unknown> }).error;
  if (typeof err !== "object" || err === null) return {};
  return {
    code: typeof err.code === "string" ? err.code : undefined,
    message: typeof err.message === "string" ? err.message : undefined,
    requestId: typeof err.request_id === "string" ? err.request_id : undefined,
    details: Array.isArray(err.details) ? (err.details as ApiErrorDetail[]) : undefined,
  };
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return undefined; // non-JSON body
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions<T> = {}): Promise<T> {
  const { method = "GET", query, body, signal, validate, auth = true, expectEmpty = false } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = auth ? hooks.getToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, config.requestTimeoutMs);
  const onCallerAbort = () => controller.abort();
  signal?.addEventListener("abort", onCallerAbort);

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      credentials: "omit",
    });
  } catch {
    if (timedOut) throw new ApiError({ kind: "timeout", message: "Request timed out" });
    if (signal?.aborted) throw new ApiError({ kind: "aborted", message: "Request cancelled" });
    throw new ApiError({ kind: "network", message: "Network request failed" });
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onCallerAbort);
  }

  const requestId = response.headers.get("X-Request-ID");
  const payload = await readJson(response);

  if (!response.ok) {
    const parsed = parseErrorBody(payload);
    const retryAfter = Number(response.headers.get("Retry-After"));
    const error = new ApiError({
      kind: "http",
      status: response.status,
      code: parsed.code ?? `HTTP_${response.status}`,
      message: parsed.message ?? `Request failed with status ${response.status}`,
      requestId: parsed.requestId ?? requestId,
      details: parsed.details,
      retryAfterSeconds: Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null,
    });
    // An expired/revoked token ends the session; the login request itself is excluded.
    if (response.status === 401 && token) hooks.onUnauthorized();
    throw error;
  }

  if (expectEmpty || response.status === 204) return null as T;
  if (payload === undefined || payload === null || (validate && !validate(payload))) {
    throw new ApiError({ kind: "invalid_response", status: response.status, message: "Unexpected response shape", requestId });
  }
  return payload as T;
}
