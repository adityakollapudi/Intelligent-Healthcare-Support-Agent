import { afterEach, describe, expect, it, vi } from "vitest";

import { apiError, json, mockApi } from "../test/fetch-mock";
import { apiRequest, buildUrl, configureSession } from "./api-client";
import { ApiError, describeError } from "./errors";

afterEach(() => {
  vi.unstubAllGlobals();
  configureSession({ getToken: () => null, onUnauthorized: () => undefined });
});

describe("buildUrl", () => {
  it("joins the configured base URL and encodes repeated query params", () => {
    expect(buildUrl("/claims", { status: ["RECEIVED", "PROCESSED_PAID"], limit: 10, cursor: null })).toBe(
      "http://api.test/api/v1/claims?status=RECEIVED&status=PROCESSED_PAID&limit=10",
    );
  });
});

describe("apiRequest", () => {
  it("sends the bearer token and parses JSON", async () => {
    const { calls } = mockApi({ "GET /thing": () => json(200, { ok: true }) });
    configureSession({ getToken: () => "tok", onUnauthorized: vi.fn() });
    await expect(apiRequest("/thing")).resolves.toEqual({ ok: true });
    expect(calls[0]!.headers.get("Authorization")).toBe("Bearer tok");
  });

  it("omits the token for auth: false requests", async () => {
    const { calls } = mockApi({ "POST /auth/login": () => json(200, {}) });
    configureSession({ getToken: () => "tok", onUnauthorized: vi.fn() });
    await apiRequest("/auth/login", { method: "POST", body: { a: 1 }, auth: false });
    expect(calls[0]!.headers.get("Authorization")).toBeNull();
    expect(calls[0]!.body).toEqual({ a: 1 });
  });

  it("normalizes the backend error format", async () => {
    mockApi({ "GET /claims/x": () => apiError(404, "RESOURCE_NOT_FOUND", "The requested item was not found.") });
    const error = await apiRequest("/claims/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ kind: "http", status: 404, code: "RESOURCE_NOT_FOUND", requestId: "req-test" });
  });

  it("reads Retry-After on 429", async () => {
    mockApi({ "POST /auth/login": () => json(429, { error: { code: "RATE_LIMITED", message: "x" } }, { "Retry-After": "120" }) });
    const error = (await apiRequest("/auth/login", { method: "POST", auth: false }).catch((e) => e)) as ApiError;
    expect(error.retryAfterSeconds).toBe(120);
    expect(describeError(error).message).toContain("2 minute");
  });

  it("ends the session on 401 when a token was sent", async () => {
    const onUnauthorized = vi.fn();
    configureSession({ getToken: () => "expired", onUnauthorized });
    mockApi({ "GET /auth/me": () => apiError(401, "UNAUTHENTICATED") });
    await expect(apiRequest("/auth/me")).rejects.toMatchObject({ status: 401 });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("does not end the session for a failed login (no token)", async () => {
    const onUnauthorized = vi.fn();
    configureSession({ getToken: () => null, onUnauthorized });
    mockApi({ "POST /auth/login": () => apiError(401, "INVALID_CREDENTIALS") });
    await expect(apiRequest("/auth/login", { method: "POST", auth: false })).rejects.toMatchObject({ status: 401 });
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it("maps network failures", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    await expect(apiRequest("/health")).rejects.toMatchObject({ kind: "network" });
  });

  it("handles non-JSON error bodies", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>Bad gateway</html>", { status: 502 })));
    await expect(apiRequest("/health")).rejects.toMatchObject({ kind: "http", status: 502, code: "HTTP_502" });
  });

  it("rejects responses that fail validation", async () => {
    mockApi({ "GET /thing": () => json(200, { unexpected: true }) });
    const isOk = (v: unknown): v is { ok: boolean } => typeof v === "object" && v !== null && "ok" in v;
    await expect(apiRequest("/thing", { validate: isOk })).rejects.toMatchObject({ kind: "invalid_response" });
  });

  it("returns null for 204", async () => {
    mockApi({ "POST /auth/logout": () => new Response(null, { status: 204 }) });
    await expect(apiRequest("/auth/logout", { method: "POST", expectEmpty: true })).resolves.toBeNull();
  });

  it("supports caller cancellation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) => new Promise((_, reject) => init.signal!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))))),
    );
    const controller = new AbortController();
    const pending = apiRequest("/slow", { signal: controller.signal });
    controller.abort();
    await expect(pending).rejects.toMatchObject({ kind: "aborted" });
  });

  it("times out", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) => new Promise((_, reject) => init.signal!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))))),
    );
    const pending = apiRequest("/slow").catch((e) => e);
    await vi.advanceTimersByTimeAsync(2100);
    expect(await pending).toMatchObject({ kind: "timeout" });
    vi.useRealTimers();
  });

  it("never logs tokens or bodies", async () => {
    const spies = (["log", "info", "warn", "error", "debug"] as const).map((m) => vi.spyOn(console, m));
    configureSession({ getToken: () => "secret-token", onUnauthorized: vi.fn() });
    mockApi({ "POST /x": () => apiError(500, "INTERNAL_ERROR") });
    await apiRequest("/x", { method: "POST", body: { password: "hunter2" } }).catch(() => undefined);
    for (const spy of spies) {
      const text = JSON.stringify(spy.mock.calls);
      expect(text).not.toContain("secret-token");
      expect(text).not.toContain("hunter2");
    }
  });
});
