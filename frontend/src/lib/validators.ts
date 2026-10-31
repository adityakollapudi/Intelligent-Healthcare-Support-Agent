// Lightweight runtime guards for backend responses (no schema library needed for this scope).
import {
  type AdminMetrics,
  type AgentSummary,
  type AuditEvent,
  type KnowledgeGaps,
  CHECKLIST_STATUSES,
  FIELD_STATUSES,
  JOB_STATUSES,
  READINESS_STATUSES,
  type ChecklistDetail,
  type ChecklistSummary,
  type DocumentDetail,
  type DocumentSummary,
  type RequirementSetSummary,
  CASE_CATEGORIES,
  CASE_STATUSES,
  CLAIM_STATUSES,
  type BenefitsResponse,
  type CaseDetail,
  type CasePage,
  type ChatRecord,
  type ChatResponse,
  type ClaimDetail,
  type ClaimPage,
  type ClaimSummary,
  type HealthResponse,
  type LoginResponse,
  type MeResponse,
  type SessionDetail,
  type SessionSummary,
} from "../types/api";

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isStrOrNull = (v: unknown) => v === null || isStr(v);
const ROLES = ["MEMBER", "PROVIDER", "SUPPORT_AGENT", "ADMIN"];

export const isHealth = (v: unknown): v is HealthResponse =>
  isObj(v) && (v.status === "ok" || v.status === "degraded") && isObj(v.checks);

export const isLogin = (v: unknown): v is LoginResponse =>
  isObj(v) && isStr(v.access_token) && isObj(v.user) && ROLES.includes(v.user.role as string);

export const isMe = (v: unknown): v is MeResponse =>
  isObj(v) && isStr(v.id) && ROLES.includes(v.role as string) && Array.isArray(v.permissions);

export const isClaimSummary = (v: unknown): v is ClaimSummary =>
  isObj(v) &&
  isStr(v.claim_number) &&
  isStr(v.submission_date) &&
  isStr(v.last_status_change_at) &&
  (CLAIM_STATUSES as readonly string[]).includes(v.status as string) &&
  isStrOrNull(v.provider_name);

export const isClaimDetail = (v: unknown): v is ClaimDetail =>
  isClaimSummary(v) && isObj(v) && isStr(v.member_number) && isStrOrNull(v.status_description);

export const isClaimPage = (v: unknown): v is ClaimPage =>
  isObj(v) && Array.isArray(v.items) && v.items.every(isClaimSummary) && isStrOrNull(v.next_cursor);

export const isBenefits = (v: unknown): v is BenefitsResponse =>
  isObj(v) &&
  isStr(v.plan_code) &&
  isStr(v.plan_name) &&
  Array.isArray(v.benefits) &&
  v.benefits.every((b) => isObj(b) && isStr(b.benefit_category) && isStr(b.service_name) && typeof b.prior_auth_required === "boolean");

const isCitation = (v: unknown) =>
  isObj(v) && isStr(v.marker) && isStr(v.document_title) && isStr(v.document_version) && isStr(v.excerpt);

const isRequirementItem = (v: unknown) =>
  isObj(v) &&
  isStr(v.requirement_code) &&
  isStr(v.description) &&
  typeof v.is_mandatory === "boolean" &&
  (v.source === null || (isObj(v.source) && isStr(v.source.document_title) && isStr(v.source.excerpt)));

const RECORD_DATA: Record<ChatRecord["kind"], (d: Obj) => boolean> = {
  claims: (d) => Array.isArray(d.claims) && d.claims.every(isClaimSummary),
  plan_benefits: (d) => isBenefits(d),
  requirements: (d) => isStr(d.procedure_code) && isStr(d.disclaimer) && Array.isArray(d.requirements) && d.requirements.every(isRequirementItem),
  support_case_proposal: (d) =>
    (CASE_CATEGORIES as readonly string[]).includes(d.category as string) && isStr(d.summary) && isStr(d.idempotency_key),
  document_sources: (d) =>
    Array.isArray(d.sources) &&
    d.sources.every((s) => isObj(s) && isStr(s.marker) && isStr(s.filename) && isStr(s.excerpt) && typeof s.page === "number"),
};

export const isChatRecord = (v: unknown): v is ChatRecord =>
  isObj(v) && isStr(v.kind) && v.kind in RECORD_DATA && isObj(v.data) && RECORD_DATA[v.kind as ChatRecord["kind"]](v.data);

const isToolExecution = (v: unknown) => isObj(v) && isStr(v.tool_name) && isStr(v.result_status) && isStr(v.summary);

// Older stored messages may predate tools; absent lists are treated as empty, malformed ones are rejected.
const optionalList = (v: unknown, item: (x: unknown) => boolean) => v === undefined || (Array.isArray(v) && v.every(item));

export const isChatResponse = (v: unknown): v is ChatResponse =>
  isObj(v) &&
  optionalList(v.records, isChatRecord) &&
  optionalList(v.tool_executions, isToolExecution) &&
  isStr(v.session_id) &&
  isStr(v.message_id) &&
  isStr(v.answer_text) &&
  isStr(v.answer_type) &&
  isStr(v.evidence_status) &&
  Array.isArray(v.citations) &&
  v.citations.every(isCitation) &&
  Array.isArray(v.proposed_actions) &&
  isObj(v.escalation);

export const isSessionPage = (v: unknown): v is { items: SessionSummary[] } =>
  isObj(v) && Array.isArray(v.items) && v.items.every((s) => isObj(s) && isStr(s.session_id) && isStr(s.title));

export const isSessionDetail = (v: unknown): v is SessionDetail =>
  isObj(v) &&
  isStr(v.session_id) &&
  Array.isArray(v.messages) &&
  v.messages.every(
    (m) =>
      isObj(m) &&
      (m.sender === "USER" || m.sender === "ASSISTANT") &&
      isStr(m.content) &&
      optionalList(m.records, isChatRecord) &&
      optionalList(m.tool_executions, isToolExecution),
  );

const isCaseSummary = (v: unknown) =>
  isObj(v) &&
  isStr(v.case_id) &&
  isStr(v.case_number) &&
  /^CASE-\d{4}-\d{6}$/.test(v.case_number) &&
  (CASE_STATUSES as readonly string[]).includes(v.status as string) &&
  (CASE_CATEGORIES as readonly string[]).includes(v.category as string);

export const isCaseDetail = (v: unknown): v is CaseDetail =>
  isCaseSummary(v) && isObj(v) && isStr(v.summary) && Array.isArray(v.events);

export const isCasePage = (v: unknown): v is CasePage =>
  isObj(v) && Array.isArray(v.items) && v.items.every(isCaseSummary) && isStrOrNull(v.next_cursor ?? null);

// --- Phase 6 documents and readiness ---------------------------------------------------------
const inList = (list: readonly string[], v: unknown) => list.includes(v as string);
const isJob = (v: unknown) =>
  isObj(v) && isStr(v.job_id) && inList(JOB_STATUSES, v.status) && isStrOrNull(v.error_code) && isStrOrNull(v.error_detail);
const isField = (v: unknown) =>
  isObj(v) && isStr(v.field_name) && inList(FIELD_STATUSES, v.validation_status) && isStrOrNull(v.raw_value) && isStrOrNull(v.normalized_value);
const isJobDetail = (v: unknown) =>
  isJob(v) && isObj(v) && Array.isArray(v.fields) && v.fields.every(isField) && Array.isArray(v.pages) && Array.isArray(v.warnings);

export const isDocumentSummary = (v: unknown): v is DocumentSummary =>
  isObj(v) && isStr(v.document_id) && isStr(v.original_filename) && typeof v.page_count === "number" &&
  (v.latest_job === null || isJob(v.latest_job));

export const isDocumentDetail = (v: unknown): v is DocumentDetail =>
  isObj(v) && isStr(v.document_id) && isStr(v.original_filename) && (v.latest_job === null || isJobDetail(v.latest_job));

export const isDocumentPage = (v: unknown): v is { items: DocumentSummary[] } =>
  isObj(v) && Array.isArray(v.items) && v.items.every(isDocumentSummary);

export const isAnalyzeResponse = (v: unknown): v is { job_id: string; status: string } =>
  isObj(v) && isStr(v.job_id) && inList(JOB_STATUSES, v.status);

const isCounts = (v: unknown) => isObj(v) && CHECKLIST_STATUSES.every((s) => typeof v[s] === "number");

const isChecklistSummary = (v: unknown): v is ChecklistSummary =>
  isObj(v) && isStr(v.checklist_id) && isStr(v.procedure_code) && inList(READINESS_STATUSES, v.readiness_status) && isCounts(v.counts);

export const isChecklistDetail = (v: unknown): v is ChecklistDetail => {
  if (!isChecklistSummary(v) || !isObj(v) || !Array.isArray(v.items) || !isStr(v.reviewer_summary) || !isStr(v.disclaimer)) return false;
  const items = v.items as unknown[];
  if (!items.every((i) => isObj(i) && isStr(i.requirement_code) && inList(CHECKLIST_STATUSES, i.item_status) && isStr(i.explanation))) {
    return false;
  }
  // The displayed counts must agree with the items they summarize; a mismatch is rejected, not shown.
  const counts = v.counts as Record<string, number>;
  return CHECKLIST_STATUSES.every((s) => items.filter((i) => (i as Obj).item_status === s).length === counts[s]);
};

export const isChecklistPage = (v: unknown): v is { items: ChecklistSummary[] } =>
  isObj(v) && Array.isArray(v.items) && v.items.every(isChecklistSummary);

export const isRequirementSets = (v: unknown): v is RequirementSetSummary[] =>
  Array.isArray(v) && v.every((s) => isObj(s) && isStr(s.procedure_code) && isStr(s.display_name) && isStr(s.version));

// --- Phase 7 administration -------------------------------------------------------------------
const isCounted = (v: unknown) => isObj(v) && Object.values(v).every((n) => typeof n === "number");

export const isAdminMetrics = (v: unknown): v is AdminMetrics =>
  isObj(v) && isObj(v.period) && isObj(v.cases) && isObj(v.chat) && isObj(v.documents) && isObj(v.readiness) &&
  typeof v.cases.created === "number" && isCounted(v.cases.created_by_status) && isCounted(v.cases.current_by_status) &&
  Array.isArray(v.cases.created_per_day) && isCounted(v.chat.by_evidence_status) && Array.isArray(v.unavailable);

export const isKnowledgeGaps = (v: unknown): v is KnowledgeGaps =>
  isObj(v) && Array.isArray(v.items) && Array.isArray(v.by_intent) && Array.isArray(v.tool_failures) &&
  typeof v.suppressed_topics === "number";

export const isAuditPage = (v: unknown): v is { items: AuditEvent[]; next_cursor: string | null } =>
  isObj(v) && Array.isArray(v.items) &&
  v.items.every((e) => isObj(e) && typeof e.id === "number" && isStr(e.action) && ["SUCCESS", "DENIED", "FAILURE"].includes(e.outcome as string)) &&
  isStrOrNull(v.next_cursor ?? null);

export const isAgents = (v: unknown): v is AgentSummary[] =>
  Array.isArray(v) && v.every((a) => isObj(a) && isStr(a.id) && isStr(a.display_name) && typeof a.open_assigned_count === "number");