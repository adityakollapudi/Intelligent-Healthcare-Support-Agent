// Types mirroring the backend Pydantic schemas (backend/app/schemas/*) and doc 06.
// Phases 2, 4 and 5 endpoints are implemented; types marked "planned" follow the Phase 1 contract only.

export type Role = "MEMBER" | "PROVIDER" | "SUPPORT_AGENT" | "ADMIN";
export type DataEnvironment = "SYNTHETIC_PROTOTYPE";

export const CLAIM_STATUSES = [
  "RECEIVED",
  "UNDER_PROCESSING",
  "PENDING_INFORMATION",
  "PROCESSED_PAID",
  "PROCESSED_DENIED",
] as const;
export type ClaimStatus = (typeof CLAIM_STATUSES)[number];

// --- Implemented (Phase 2) ---------------------------------------------------

export interface HealthResponse {
  status: "ok" | "degraded";
  checks: { api: "ok"; database: "ok" | "unavailable" };
  time: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: { id: string; display_name: string; role: Role };
}

export interface MeResponse {
  id: string;
  display_name: string;
  email: string;
  role: Role;
  organization: { id: string; name: string } | null;
  member: { member_number: string; plan_code: string } | null;
  permissions: string[];
}

export interface ClaimSummary {
  claim_number: string;
  plan_code: string;
  provider_name: string | null;
  service_date: string;
  submission_date: string;
  status: ClaimStatus;
  status_reason_code: string | null;
  last_status_change_at: string;
}

export interface ClaimDetail extends ClaimSummary {
  member_number: string;
  status_description: string | null;
  data_environment: DataEnvironment;
}

export interface ClaimPage {
  items: ClaimSummary[];
  next_cursor: string | null;
  data_environment: DataEnvironment;
}

export interface BenefitSource {
  document_title: string;
  document_version: string;
  effective_date: string | null;
  page_start: number | null;
  chunk_id: string;
}

export interface BenefitItem {
  benefit_category: string;
  service_name: string;
  in_network_cost_share: string | null;
  out_of_network_cost_share: string | null;
  prior_auth_required: boolean;
  visit_limit: string | null;
  limitations: string | null;
  source: BenefitSource | null;
}

export interface BenefitsResponse {
  plan_code: string;
  plan_name: string;
  plan_year: number;
  effective_start: string;
  effective_end: string | null;
  benefits: BenefitItem[];
  data_environment: DataEnvironment;
}

// --- Chat (Phase 4, backend/app/schemas/chat.py) -----------------------------

export interface Citation {
  marker: string;
  chunk_id: string | null;
  document_id: string;
  document_title: string;
  document_type: string;
  document_version: string;
  effective_date: string | null;
  section_heading: string | null;
  page_start: number | null;
  page_end: number | null;
  excerpt: string;
}

export type EvidenceStatus = "SUPPORTED" | "INSUFFICIENT" | "CONFLICTING" | "VERIFIED_RECORD" | "NOT_APPLICABLE";
export type AnswerType =
  | "DOCUMENT_GROUNDED"
  | "TOOL_RESULT"
  | "CLARIFICATION"
  | "INSUFFICIENT_EVIDENCE"
  | "UNSUPPORTED_REQUEST"
  | "ERROR";

export interface ProposedAction {
  action_type: "CREATE_SUPPORT_CASE" | "UPLOAD_DOCUMENT" | "START_READINESS_CHECK" | "VIEW_CLAIM" | "VIEW_CASE";
  label: string;
  requires_confirmation: boolean;
  /** False when the action's backend arrives in a later phase. */
  available: boolean;
  prefill: Record<string, unknown>;
}

// --- Tools and support cases (Phase 5) ----------------------------------------

export interface ToolExecution {
  tool_name: string;
  result_status: string;
  summary: string;
}

export interface RequirementSource {
  document_id: string;
  document_title: string;
  document_version: string;
  effective_date: string | null;
  section_heading: string | null;
  page_start: number | null;
  chunk_id: string;
  excerpt: string;
}

export interface RequirementItem {
  requirement_code: string;
  description: string;
  is_mandatory: boolean;
  rule_type: string;
  /** null when the stated passage couldn't be verified in the source document. */
  source: RequirementSource | null;
}

export interface RequirementSet {
  procedure_code: string;
  display_name: string;
  version: string;
  source_document_title: string;
  source_document_version: string;
  evidence_status: "SUPPORTED" | "PARTIALLY_SUPPORTED";
  requirements: RequirementItem[];
  disclaimer: string;
}

export const CASE_CATEGORIES = [
  "BENEFITS_QUESTION",
  "CLAIM_INQUIRY",
  "DOCUMENT_ISSUE",
  "PA_READINESS_REVIEW",
  "KNOWLEDGE_GAP",
  "TECHNICAL_ISSUE",
  "OTHER",
] as const;
export type CaseCategory = (typeof CASE_CATEGORIES)[number];

export const CASE_STATUSES = ["OPEN", "ASSIGNED", "IN_PROGRESS", "AWAITING_USER", "RESOLVED", "CLOSED", "CANCELLED"] as const;
export type CaseStatus = (typeof CASE_STATUSES)[number];

export interface SupportCaseProposal {
  category: CaseCategory;
  summary: string;
  escalation_reason: string;
  related_session_id: string | null;
  idempotency_key: string;
  requires_confirmation: true;
}

/** Structured tool output shown next to an answer. Discriminated by `kind`. */
export type ChatRecord =
  | { kind: "claims"; data: { claims: (ClaimSummary & { status_description?: string | null })[] } }
  | { kind: "plan_benefits"; data: BenefitsResponse }
  | { kind: "requirements"; data: RequirementSet }
  | { kind: "support_case_proposal"; data: SupportCaseProposal };

export interface CreateCaseRequest {
  category: CaseCategory;
  summary: string;
  escalation_reason?: string;
  related_session_id?: string | null;
  related_claim_number?: string | null;
}

export interface CaseEvent {
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  note: string | null;
  actor_display_name: string;
  created_at: string;
}

export interface CaseSummary {
  case_id: string;
  case_number: string;
  category: CaseCategory;
  status: CaseStatus;
  escalation_reason: string;
  summary_preview: string;
  created_at: string;
  updated_at: string;
}

export interface CaseDetail {
  case_id: string;
  case_number: string;
  category: CaseCategory;
  status: CaseStatus;
  escalation_reason: string;
  summary: string;
  related_session_id: string | null;
  related_claim_number: string | null;
  resolution_note: string | null;
  version: number;
  events: CaseEvent[];
  created_at: string;
  updated_at: string;
  data_environment: DataEnvironment;
}

export interface CasePage {
  items: CaseSummary[];
  next_cursor: string | null;
}

export interface SessionSummary {
  session_id: string;
  title: string;
  last_message_at: string;
  created_at: string;
}

export interface HistoryMessage {
  message_id: string;
  sender: "USER" | "ASSISTANT";
  content: string;
  intent: string | null;
  answer_type: AnswerType | null;
  evidence_status: EvidenceStatus | null;
  citations: Citation[];
  tool_executions: ToolExecution[];
  records: ChatRecord[];
  proposed_actions: ProposedAction[];
  disclaimers: string[];
  created_at: string;
}

export interface SessionDetail {
  session_id: string;
  title: string;
  messages: HistoryMessage[];
}

export interface ChatResponse {
  session_id: string;
  message_id: string;
  intent: string;
  answer_type: AnswerType;
  evidence_status: EvidenceStatus;
  answer_text: string;
  citations: Citation[];
  tool_executions: ToolExecution[];
  records: ChatRecord[];
  proposed_actions: ProposedAction[];
  escalation: { offered: boolean; reason: string | null };
  disclaimers: string[];
  latency_ms: number;
  created_at: string;
  data_environment: DataEnvironment;
}

// --- Planned (Phase 1 contract; endpoints not implemented yet) ---------------

export type ChecklistItemStatus = "SATISFIED" | "MISSING" | "UNREADABLE" | "NEEDS_MANUAL_REVIEW";

export interface ChecklistItem {
  requirement_code: string;
  description: string;
  item_status: ChecklistItemStatus;
  explanation: string;
}

export type FieldValidationStatus = "VALID" | "ABSENT" | "ILLEGIBLE" | "INVALID_FORMAT" | "INCONSISTENT" | "LOW_CONFIDENCE";
