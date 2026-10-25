// Typed service functions for implemented endpoints; see lib/features.ts for what exists.
import { apiRequest } from "../lib/api-client";
import {
  isBenefits,
  isCaseDetail,
  isCasePage,
  isChatResponse,
  isClaimDetail,
  isClaimPage,
  isHealth,
  isLogin,
  isMe,
  isSessionDetail,
  isSessionPage,
} from "../lib/validators";
import type {
  BenefitsResponse,
  CaseDetail,
  CasePage,
  CaseStatus,
  CreateCaseRequest,
  ChatResponse,
  ClaimDetail,
  ClaimPage,
  ClaimStatus,
  HealthResponse,
  LoginResponse,
  MeResponse,
  SessionDetail,
  SessionSummary,
} from "../types/api";

export const healthService = {
  // /health answers 503 with a degraded body; callers treat that ApiError as "degraded".
  get: (signal?: AbortSignal) => apiRequest<HealthResponse>("/health", { auth: false, signal, validate: isHealth }),
};

export const authService = {
  login: (email: string, password: string) =>
    apiRequest<LoginResponse>("/auth/login", { method: "POST", body: { email, password }, auth: false, validate: isLogin }),
  me: (signal?: AbortSignal) => apiRequest<MeResponse>("/auth/me", { signal, validate: isMe }),
  logout: () => apiRequest<null>("/auth/logout", { method: "POST", expectEmpty: true }),
};

export const claimsService = {
  list: (params: { status?: ClaimStatus[]; limit?: number; cursor?: string | null }, signal?: AbortSignal) =>
    apiRequest<ClaimPage>("/claims", {
      query: { status: params.status, limit: params.limit, cursor: params.cursor },
      signal,
      validate: isClaimPage,
    }),
  get: (claimNumber: string, signal?: AbortSignal) =>
    apiRequest<ClaimDetail>(`/claims/${encodeURIComponent(claimNumber)}`, { signal, validate: isClaimDetail }),
};

export const benefitsService = {
  get: (planCode: string, benefitCategory?: string, signal?: AbortSignal) =>
    apiRequest<BenefitsResponse>(`/benefits/${encodeURIComponent(planCode)}`, {
      query: { benefit_category: benefitCategory },
      signal,
      validate: isBenefits,
    }),
};

// Phase 4 chat API (doc 06 §3.3).
export const chatService = {
  send: (body: { session_id: string | null; client_message_id: string; message: string }, signal?: AbortSignal) =>
    apiRequest<ChatResponse>("/chat", { method: "POST", body, signal, validate: isChatResponse }),
  sessions: (signal?: AbortSignal) =>
    apiRequest<{ items: SessionSummary[] }>("/chat/sessions", { query: { limit: 20 }, signal, validate: isSessionPage }),
  session: (sessionId: string, signal?: AbortSignal) =>
    apiRequest<SessionDetail>(`/chat/sessions/${encodeURIComponent(sessionId)}`, { signal, validate: isSessionDetail }),
};

// Phase 5 support cases (doc 06 §3.8). Creation is always a user-confirmed request carrying an
// Idempotency-Key; retrying with the same key returns the same case instead of a duplicate.
export const supportCasesService = {
  create: (body: CreateCaseRequest, idempotencyKey: string) =>
    apiRequest<CaseDetail>("/support-cases", {
      method: "POST",
      body,
      headers: { "Idempotency-Key": idempotencyKey },
      validate: isCaseDetail,
    }),
  list: (params: { status?: CaseStatus[] }, signal?: AbortSignal) =>
    apiRequest<CasePage>("/support-cases", { query: { status: params.status, limit: 50 }, signal, validate: isCasePage }),
  get: (caseId: string, signal?: AbortSignal) =>
    apiRequest<CaseDetail>(`/support-cases/${encodeURIComponent(caseId)}`, { signal, validate: isCaseDetail }),
};
