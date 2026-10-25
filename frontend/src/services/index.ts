// Typed service functions. Only Phase 2 endpoints are called; see lib/features.ts for the rest.
import { apiRequest } from "../lib/api-client";
import { isBenefits, isChatResponse, isClaimDetail, isClaimPage, isHealth, isLogin, isMe } from "../lib/validators";
import type {
  BenefitsResponse,
  ChatResponse,
  ClaimDetail,
  ClaimPage,
  ClaimStatus,
  HealthResponse,
  LoginResponse,
  MeResponse,
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

// Phase 4 boundary (POST /chat, doc 06 §3.3). Not called while features.chat.available is false.
export const chatService = {
  send: (body: { session_id: string | null; client_message_id: string; message: string }, signal?: AbortSignal) =>
    apiRequest<ChatResponse>("/chat", { method: "POST", body, signal, validate: isChatResponse }),
};
