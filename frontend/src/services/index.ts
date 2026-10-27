// Typed service functions for implemented endpoints; see lib/features.ts for what exists.
import { apiRequest } from "../lib/api-client";
import {
  isAdminMetrics,
  isAgents,
  isAuditPage,
  isKnowledgeGaps,
  isAnalyzeResponse,
  isChecklistDetail,
  isChecklistPage,
  isDocumentDetail,
  isDocumentPage,
  isDocumentSummary,
  isRequirementSets,
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
  AdminMetrics,
  AgentSummary,
  AuditEvent,
  CaseUpdate,
  KnowledgeGaps,
  ChecklistDetail,
  ChecklistSummary,
  DeclaredPurpose,
  DocumentDetail,
  DocumentSummary,
  RequirementSetSummary,
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
  /** FR-034: rate one of my assistant answers; re-rating replaces the earlier rating. */
  feedback: (messageId: string, rating: "HELPFUL" | "NOT_HELPFUL") =>
    apiRequest<{ message_id: string; rating: string; updated_at: string }>(
      `/chat/messages/${encodeURIComponent(messageId)}/feedback`,
      {
        method: "POST",
        body: { rating },
        validate: (v): v is { message_id: string; rating: string; updated_at: string } =>
          typeof v === "object" && v !== null && (v as { rating?: unknown }).rating === rating,
      },
    ),
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
  list: (
    params: {
      scope?: "mine" | "queue" | "assigned" | "all";
      status?: CaseStatus[];
      category?: string;
      case_number?: string;
      cursor?: string | null;
      limit?: number;
    },
    signal?: AbortSignal,
  ) =>
    apiRequest<CasePage>("/support-cases", {
      query: {
        scope: params.scope,
        status: params.status,
        category: params.category,
        case_number: params.case_number,
        cursor: params.cursor,
        limit: params.limit ?? 20,
      },
      signal,
      validate: isCasePage,
    }),
  /** Validated by the backend lifecycle rules; `version` makes a stale or repeated request fail with 409. */
  update: (caseId: string, body: CaseUpdate) =>
    apiRequest<CaseDetail>(`/support-cases/${encodeURIComponent(caseId)}`, { method: "PATCH", body, validate: isCaseDetail }),
  get: (caseId: string, signal?: AbortSignal) =>
    apiRequest<CaseDetail>(`/support-cases/${encodeURIComponent(caseId)}`, { signal, validate: isCaseDetail }),
};

// Phase 6 documents (doc 06 §3.6). Upload stores the file only; analysis is a separate request
// whose result is read back by polling GET /documents/{id}.
export const documentsService = {
  upload: (file: File, purpose?: DeclaredPurpose) => {
    const form = new FormData();
    form.append("file", file, file.name);
    if (purpose) form.append("declared_purpose", purpose);
    return apiRequest<DocumentSummary>("/documents", { method: "POST", body: form, validate: isDocumentSummary });
  },
  list: (signal?: AbortSignal) => apiRequest<{ items: DocumentSummary[] }>("/documents", { signal, validate: isDocumentPage }),
  get: (id: string, signal?: AbortSignal) =>
    apiRequest<DocumentDetail>(`/documents/${encodeURIComponent(id)}`, { signal, validate: isDocumentDetail }),
  analyze: (id: string) =>
    apiRequest<{ job_id: string; status: string }>(`/documents/${encodeURIComponent(id)}/analyze`, {
      method: "POST",
      body: {},
      validate: isAnalyzeResponse,
    }),
};

// Phase 6 readiness (doc 06 §3.7). A checklist is documentation completeness only, never an approval.
export const readinessService = {
  requirementSets: (signal?: AbortSignal) =>
    apiRequest<RequirementSetSummary[]>("/authorization/requirement-sets", { signal, validate: isRequirementSets }),
  create: (body: { procedure_code: string; document_ids: string[]; provider_note?: string | null }) =>
    apiRequest<ChecklistDetail>("/authorization/readiness", { method: "POST", body, validate: isChecklistDetail }),
  list: (signal?: AbortSignal) =>
    apiRequest<{ items: ChecklistSummary[] }>("/authorization/checklists", { signal, validate: isChecklistPage }),
  get: (id: string, signal?: AbortSignal) =>
    apiRequest<ChecklistDetail>(`/authorization/checklists/${encodeURIComponent(id)}`, { signal, validate: isChecklistDetail }),
};

// Phase 7 administration (doc 06 section 3.9). Read-only views of persisted data.
export const adminService = {
  metrics: (range: { from?: string; to?: string }, signal?: AbortSignal) =>
    apiRequest<AdminMetrics>("/admin/metrics", { query: range, signal, validate: isAdminMetrics }),
  knowledgeGaps: (range: { from?: string; to?: string }, signal?: AbortSignal) =>
    apiRequest<KnowledgeGaps>("/admin/knowledge-gaps", { query: range, signal, validate: isKnowledgeGaps }),
  auditEvents: (
    params: { action?: string; outcome?: string; resource_type?: string; resource_ref?: string; cursor?: string | null },
    signal?: AbortSignal,
  ) =>
    apiRequest<{ items: AuditEvent[]; next_cursor: string | null }>("/admin/audit-events", {
      query: { ...params, limit: 25 },
      signal,
      validate: isAuditPage,
    }),
  agents: (signal?: AbortSignal) => apiRequest<AgentSummary[]>("/admin/support-agents", { signal, validate: isAgents }),
};