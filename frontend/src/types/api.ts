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

// --- Documents and readiness (Phase 6, backend/app/schemas/document.py, readiness.py) ---------

export const JOB_STATUSES = ["QUEUED", "RUNNING", "COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED"] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];
export const FIELD_STATUSES = ["VALID", "ABSENT", "ILLEGIBLE", "INVALID_FORMAT", "INCONSISTENT", "LOW_CONFIDENCE"] as const;
export type FieldValidationStatus = (typeof FIELD_STATUSES)[number];
export const CHECKLIST_STATUSES = ["SATISFIED", "MISSING", "UNREADABLE", "NEEDS_MANUAL_REVIEW"] as const;
export type ChecklistItemStatus = (typeof CHECKLIST_STATUSES)[number];
export const READINESS_STATUSES = ["DOCUMENTATION_APPEARS_COMPLETE", "DOCUMENTATION_INCOMPLETE", "MANUAL_REVIEW_REQUIRED"] as const;
export type ReadinessStatus = (typeof READINESS_STATUSES)[number];
export type DeclaredPurpose = "PA_REQUEST" | "SUPPORTING_DOCUMENT" | "OTHER";

export interface PageDetail {
  page_number: number;
  method: "TEXT_LAYER" | "OCR" | null;
  status: "OK" | "EMPTY" | "PARTIAL" | "LOW_QUALITY" | "UNREADABLE";
  char_count: number;
  ocr_confidence: number | null;
  warning: string | null;
}

export interface DocumentField {
  field_id: string;
  field_name: string;
  raw_value: string | null;
  normalized_value: string | null;
  validation_status: FieldValidationStatus;
  validation_message: string | null;
  source_page: number | null;
  extraction_method: "TEXT_LAYER" | "OCR" | null;
  /** OCR word confidence 0–1; not a calibrated probability. null for text-layer values. */
  confidence: number | null;
}

export interface JobSummary {
  job_id: string;
  status: JobStatus;
  detected_document_type: string | null;
  pages_text_layer: number;
  pages_ocr: number;
  ocr_mean_confidence: number | null;
  warning_count: number;
  error_code: string | null;
  error_detail: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface JobDetail extends JobSummary {
  extraction_schema_version: string | null;
  pipeline_version: string | null;
  warnings: string[];
  pages: PageDetail[];
  fields: DocumentField[];
}

export interface DocumentSummary {
  document_id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  page_count: number;
  declared_purpose: DeclaredPurpose | null;
  created_at: string;
  expires_at: string;
  latest_job: JobSummary | null;
  data_environment: DataEnvironment;
}

export interface DocumentDetail extends Omit<DocumentSummary, "latest_job"> {
  latest_job: JobDetail | null;
}

export interface ItemEvidence {
  field_id: string;
  document_id: string;
  field_name: string;
  validation_status: string;
  normalized_value: string | null;
  source_page: number | null;
}

export interface ChecklistItem {
  requirement_code: string;
  description: string;
  rule_type: string;
  is_mandatory: boolean;
  item_status: ChecklistItemStatus;
  explanation: string;
  evidence: ItemEvidence[];
  requirement_source: RequirementSource | null;
}

export type ChecklistCounts = Record<ChecklistItemStatus, number>;

export interface ChecklistSummary {
  checklist_id: string;
  procedure_code: string;
  readiness_status: ReadinessStatus;
  review_state: string;
  counts: ChecklistCounts;
  created_at: string;
}

export interface ChecklistDetail extends ChecklistSummary {
  display_name: string;
  requirement_set_version: string;
  requirement_source_document: string | null;
  rules_version: string;
  documents: { document_id: string; original_filename: string; job_id: string; detected_document_type: string | null }[];
  items: ChecklistItem[];
  warnings: string[];
  provider_note: string | null;
  reviewer_summary: string;
  disclaimer: string;
  data_environment: DataEnvironment;
}

export interface RequirementSetSummary {
  procedure_code: string;
  display_name: string;
  version: string;
}