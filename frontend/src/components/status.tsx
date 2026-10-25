// Domain status → badge mappings (values from doc 02 §3).
import type { ChecklistItemStatus, ClaimStatus, EvidenceStatus, FieldValidationStatus, JobStatus, ReadinessStatus } from "../types/api";
import { StatusBadge, type BadgeTone } from "./ui";

type Meta = { label: string; tone: BadgeTone; icon: string; help?: string };

export const CLAIM_STATUS_META: Record<ClaimStatus, Meta> = {
  RECEIVED: { label: "Received", tone: "info", icon: "●", help: "The claim was received and is waiting to be processed." },
  UNDER_PROCESSING: { label: "Under processing", tone: "info", icon: "◐", help: "The claim is being processed." },
  PENDING_INFORMATION: { label: "Pending information", tone: "warning", icon: "⚠", help: "More information is needed before processing can continue." },
  PROCESSED_PAID: { label: "Processed – paid", tone: "success", icon: "✔", help: "Processing finished and payment was issued." },
  PROCESSED_DENIED: { label: "Processed – denied", tone: "danger", icon: "✖", help: "Processing finished and the claim was not paid." },
};

export const CHECKLIST_STATUS_META: Record<ChecklistItemStatus, Meta> = {
  SATISFIED: { label: "Satisfied", tone: "success", icon: "✔", help: "The rule passed using valid evidence from your documents." },
  MISSING: { label: "Missing", tone: "danger", icon: "✖", help: "No evidence for this requirement was found." },
  UNREADABLE: { label: "Unreadable", tone: "warning", icon: "?", help: "Evidence exists but couldn't be read reliably." },
  NEEDS_MANUAL_REVIEW: { label: "Needs manual review", tone: "info", icon: "👤", help: "A person must check this item (manual rule or conflicting values)." },
};

export const FIELD_STATUS_META: Record<FieldValidationStatus, Meta> = {
  VALID: { label: "Valid", tone: "success", icon: "✔" },
  ABSENT: { label: "Absent", tone: "danger", icon: "✖" },
  ILLEGIBLE: { label: "Illegible", tone: "warning", icon: "?" },
  INVALID_FORMAT: { label: "Invalid format", tone: "warning", icon: "⚠" },
  INCONSISTENT: { label: "Inconsistent", tone: "warning", icon: "≠" },
  LOW_CONFIDENCE: { label: "Low confidence", tone: "warning", icon: "~" },
};

export const EVIDENCE_STATUS_META: Record<EvidenceStatus, Meta> = {
  SUPPORTED: { label: "Supported by sources", tone: "success", icon: "✔" },
  VERIFIED_RECORD: { label: "From your record", tone: "success", icon: "✔" },
  INSUFFICIENT: { label: "Couldn't verify", tone: "warning", icon: "⚠" },
  CONFLICTING: { label: "Sources disagree", tone: "warning", icon: "≠" },
  NOT_APPLICABLE: { label: "General information", tone: "neutral", icon: "ⓘ" },
};

export const JOB_STATUS_META: Record<JobStatus, Meta> = {
  QUEUED: { label: "Queued", tone: "info", icon: "◷", help: "Waiting to be analyzed." },
  RUNNING: { label: "Analyzing", tone: "info", icon: "◐", help: "Text extraction and field checks are running." },
  COMPLETED: { label: "Analyzed", tone: "success", icon: "✔", help: "Finished; every field passed its checks." },
  COMPLETED_WITH_WARNINGS: { label: "Analyzed with warnings", tone: "warning", icon: "⚠", help: "Finished; some fields need your attention." },
  FAILED: { label: "Analysis failed", tone: "danger", icon: "✖", help: "The document could not be analyzed." },
};

export const READINESS_STATUS_META: Record<ReadinessStatus, Meta> = {
  DOCUMENTATION_APPEARS_COMPLETE: { label: "Documentation appears complete", tone: "success", icon: "✔" },
  DOCUMENTATION_INCOMPLETE: { label: "Documentation incomplete", tone: "danger", icon: "✖" },
  MANUAL_REVIEW_REQUIRED: { label: "Manual review required", tone: "info", icon: "👤" },
};

export function MetaBadge({ meta }: { meta: Meta }) {
  return <StatusBadge label={meta.label} tone={meta.tone} icon={meta.icon} />;
}
