// Lightweight runtime guards for backend responses (no schema library needed for this scope).
import {
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
