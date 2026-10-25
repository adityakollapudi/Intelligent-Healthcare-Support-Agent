// Types mirroring the backend Pydantic schemas (backend/app/schemas/*) and doc 06.
// Phase 2 endpoints are implemented; types marked "planned" follow the Phase 1 contract only.

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

// --- Planned (Phase 1 contract; endpoints not implemented yet) ---------------

export interface Citation {
  marker: string;
  chunk_id: string;
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
  prefill: Record<string, unknown>;
}

export interface ChatResponse {
  session_id: string;
  message_id: string;
  intent: string;
  answer_type: AnswerType;
  evidence_status: EvidenceStatus;
  answer_text: string;
  citations: Citation[];
  tool_executions: { tool_name: string; result_status: string; summary: string }[];
  proposed_actions: ProposedAction[];
  escalation: { offered: boolean; reason: string | null };
  disclaimers: string[];
  latency_ms: number;
  created_at: string;
}

export type ChecklistItemStatus = "SATISFIED" | "MISSING" | "UNREADABLE" | "NEEDS_MANUAL_REVIEW";

export interface ChecklistItem {
  requirement_code: string;
  description: string;
  item_status: ChecklistItemStatus;
  explanation: string;
}

export type FieldValidationStatus = "VALID" | "ABSENT" | "ILLEGIBLE" | "INVALID_FORMAT" | "INCONSISTENT" | "LOW_CONFIDENCE";
