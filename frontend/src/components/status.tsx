// Domain status → badge mappings (values from doc 02 §3).
import type { ChecklistItemStatus, ClaimStatus, EvidenceStatus, FieldValidationStatus } from "../types/api";
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

export function MetaBadge({ meta }: { meta: Meta }) {
  return <StatusBadge label={meta.label} tone={meta.tone} icon={meta.icon} />;
}
