// One case-detail panel for creators, support agents and administrators. What it shows and which
// buttons appear come from the backend (`view`, `allowed_actions`); every change is a PATCH that the
// backend validates against the lifecycle rules, with `version` so a stale or repeated click fails
// instead of applying twice. Success is shown only after the API returns the updated case.
import { useEffect, useRef, useState } from "react";

import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Alert, Button, ErrorState, LoadingState, StatusBadge, type BadgeTone } from "../../components/ui";
import { useRequest } from "../../hooks/useRequest";
import { isApiError } from "../../lib/errors";
import { formatDateTime, humanize } from "../../lib/format";
import { ChecklistReport } from "../../pages/ReadinessPage";
import { FieldTable } from "../../pages/DocumentsPage";
import { adminService, documentsService, readinessService, supportCasesService } from "../../services";
import type { CaseAction, CaseDetail, CaseStatus, CaseUpdate } from "../../types/api";

const STATUS_TONE: Record<CaseStatus, BadgeTone> = {
  OPEN: "info",
  ASSIGNED: "info",
  IN_PROGRESS: "info",
  AWAITING_USER: "warning",
  RESOLVED: "success",
  CLOSED: "neutral",
  CANCELLED: "neutral",
};

/** Plain-language status, so "created" is never mistaken for "reviewed". */
export const CASE_STATUS_HELP: Record<CaseStatus, string> = {
  OPEN: "Waiting for a support agent to pick it up. Nobody has reviewed it yet.",
  ASSIGNED: "An agent has taken the case but hasn't started work yet.",
  IN_PROGRESS: "An agent is working on the case.",
  AWAITING_USER: "The agent asked the requester for more information.",
  RESOLVED: "The agent provided a resolution. The requester can reopen it for 14 days.",
  CLOSED: "Finished.",
  CANCELLED: "Withdrawn or cancelled.",
};

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return <StatusBadge label={humanize(status)} tone={STATUS_TONE[status]} icon={status === "AWAITING_USER" ? "⚠" : "●"} />;
}

interface ActionSpec {
  label: string;
  title: string;
  build: (input: { text: string; agent: string }, isAdmin: boolean) => Omit<CaseUpdate, "version">;
  /** Which text input the dialog needs, if any, and whether it is required. */
  input?: { label: string; required: boolean | "admin" };
  agentPicker?: boolean;
  tone?: "primary" | "danger";
}

const ACTIONS: Record<CaseAction, ActionSpec> = {
  assign_to_me: { label: "Assign to me", title: "Take this case?", build: () => ({ assign_to_me: true }) },
  start: { label: "Start work", title: "Start working on this case?", build: () => ({ status: "IN_PROGRESS" }) },
  release: { label: "Release", title: "Return this case to the queue?", build: () => ({ release: true }) },
  request_info: {
    label: "Ask requester for information",
    title: "Ask the requester for more information?",
    input: { label: "What do you need from the requester?", required: true },
    build: ({ text }) => ({ status: "AWAITING_USER", note: text }),
  },
  resume: { label: "Resume work", title: "Resume work on this case?", build: () => ({ status: "IN_PROGRESS" }) },
  resolve: {
    label: "Resolve",
    title: "Resolve this case?",
    input: { label: "Resolution (shown to the requester)", required: true },
    build: ({ text }) => ({ status: "RESOLVED", resolution_note: text }),
  },
  reopen: {
    label: "Reopen",
    title: "Reopen this case?",
    input: { label: "Why does it need more work?", required: true },
    build: ({ text }) => ({ status: "IN_PROGRESS", note: text }),
  },
  close: {
    label: "Close",
    title: "Close this case?",
    input: { label: "Reason", required: "admin" },
    build: ({ text }, isAdmin) => ({ status: "CLOSED", ...(isAdmin ? { reason: text } : {}) }),
  },
  cancel: {
    label: "Cancel case",
    title: "Cancel this case?",
    tone: "danger",
    input: { label: "Reason", required: "admin" },
    build: ({ text }, isAdmin) => ({ status: "CANCELLED", ...(isAdmin ? { reason: text } : text ? { note: text } : {}) }),
  },
  add_note: { label: "Add note", title: "Add a note", input: { label: "Note", required: true }, build: ({ text }) => ({ note: text }) },
  assign: {
    label: "Assign…",
    title: "Assign this case",
    agentPicker: true,
    input: { label: "Reason (optional)", required: false },
    build: ({ text, agent }) => ({ assigned_to_user_id: agent, ...(text ? { reason: text } : {}) }),
  },
  unassign: { label: "Unassign", title: "Return this case to the queue?", build: () => ({ unassign: true }) },
};

function ActionDialog({ action, detail, isAdmin, onDone, onClose }: {
  action: CaseAction;
  detail: CaseDetail;
  isAdmin: boolean;
  onDone: (updated: CaseDetail) => void;
  onClose: () => void;
}) {
  const spec = ACTIONS[action];
  const [text, setText] = useState("");
  const [agent, setAgent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [touched, setTouched] = useState(false);
  const agents = useRequest((signal) => adminService.agents(signal));
  useEffect(() => {
    if (spec.agentPicker) void agents.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once when the dialog opens
  }, []);

  const required = spec.input && (spec.input.required === true || (spec.input.required === "admin" && isAdmin));
  const invalid = (required && !text.trim()) || (spec.agentPicker && !agent);
  const stale = isApiError(error) && error.code === "VERSION_CONFLICT";

  const submit = async () => {
    setTouched(true);
    if (invalid) return;
    setBusy(true);
    setError(null);
    try {
      onDone(await supportCasesService.update(detail.case_id, { version: detail.version, ...spec.build({ text: text.trim(), agent }, isAdmin) }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ConfirmDialog open title={spec.title} confirmLabel={spec.label.replace("…", "")} tone={spec.tone} busy={busy} onCancel={onClose} onConfirm={() => void submit()}>
      <p className="muted small">
        {detail.case_number} · currently {humanize(detail.status)}
      </p>
      {spec.agentPicker && (
        <div className="field">
          <label htmlFor="assignee">Support agent</label>
          {agents.state.status === "error" ? (
            <ErrorState error={agents.state.error} />
          ) : (
            <select id="assignee" value={agent} onChange={(e) => setAgent(e.target.value)}>
              <option value="">Choose an agent…</option>
              {agents.state.status === "success" &&
                agents.state.data.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.display_name} ({a.open_assigned_count} active)
                  </option>
                ))}
            </select>
          )}
        </div>
      )}
      {spec.input && (
        <div className="field">
          <label htmlFor="case-action-text">
            {spec.input.label}
            {required ? "" : " (optional)"}
          </label>
          <textarea id="case-action-text" rows={3} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} />
        </div>
      )}
      {touched && invalid && <p className="field-error">Please fill in the required information.</p>}
      {stale && (
        <Alert tone="warning" title="This case changed">
          Someone else updated the case. Close this dialog and reload it before trying again. Nothing was changed.
        </Alert>
      )}
      {Boolean(error) && !stale && <ErrorState error={error} />}
    </ConfirmDialog>
  );
}

function LinkedChecklist({ id }: { id: string }) {
  const req = useRequest((signal) => readinessService.get(id, signal));
  useEffect(() => {
    void req.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once
  }, [id]);
  if (req.state.status === "loading") return <LoadingState label="Loading linked checklist…" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} />;
  return req.state.status === "success" ? <ChecklistReport checklist={req.state.data} /> : null;
}

function LinkedDocument({ id, name }: { id: string; name: string }) {
  const [open, setOpen] = useState(false);
  const req = useRequest((signal) => documentsService.get(id, signal));
  return (
    <li>
      <button type="button" className="link-button" aria-expanded={open} onClick={() => {
        setOpen(!open);
        if (!open && req.state.status === "idle") void req.run();
      }}>
        {name}
      </button>
      {open && req.state.status === "loading" && <LoadingState label="Loading fields…" />}
      {open && req.state.status === "error" && <ErrorState error={req.state.error} />}
      {open && req.state.status === "success" &&
        (req.state.data.latest_job ? <FieldTable fields={req.state.data.latest_job.fields} /> : <p className="muted small">Not analyzed.</p>)}
    </li>
  );
}

export function CasePanel({ caseId, isAdmin = false, onChanged, onClose }: {
  caseId: string;
  isAdmin?: boolean;
  onChanged?: (c: CaseDetail) => void;
  onClose?: () => void;
}) {
  const detail = useRequest((signal) => supportCasesService.get(caseId, signal));
  const [action, setAction] = useState<CaseAction | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    setNotice(null);
    void detail.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when another case is selected
  }, [caseId]);

  // Keep showing the last loaded case while it refreshes after an action (no blank flash).
  const lastRef = useRef<CaseDetail | null>(null);
  if (detail.state.status === "success") lastRef.current = detail.state.data;
  if (detail.state.status === "error") return <ErrorState error={detail.state.error} onRetry={() => void detail.run()} />;
  const c = detail.state.status === "success" ? detail.state.data : lastRef.current?.case_id === caseId ? lastRef.current : null;
  if (!c) return <LoadingState label="Loading case…" />;
  const actions = c.allowed_actions ?? [];

  return (
    <section className="card section" aria-label="Case details">
      <div className="card-head">
        <h2 className="mono">{c.case_number}</h2>
        <CaseStatusBadge status={c.status} />
      </div>
      <p className="muted small">{CASE_STATUS_HELP[c.status]}</p>
      {notice && (
        <Alert tone="success" title="Saved">
          {notice}
        </Alert>
      )}
      <dl className="facts">
        <div>
          <dt>Category</dt>
          <dd>{humanize(c.category)}</dd>
        </div>
        <div>
          <dt>Why it was escalated</dt>
          <dd>{humanize(c.escalation_reason)}</dd>
        </div>
        <div>
          <dt>Requested by</dt>
          <dd>{c.created_by ? `${c.created_by.display_name} (${humanize(c.created_by.role ?? "")})` : "—"}</dd>
        </div>
        <div>
          <dt>Assigned to</dt>
          <dd>{c.assigned_to?.display_name ?? "Nobody yet"}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatDateTime(c.created_at)}</dd>
        </div>
        <div>
          <dt>Last updated</dt>
          <dd>{formatDateTime(c.updated_at)}</dd>
        </div>
        {c.related_claim_number && (
          <div>
            <dt>Related claim</dt>
            <dd className="mono">
              {c.related_claim_number} {c.related_claim_status && <span className="muted">({humanize(c.related_claim_status)})</span>}
            </dd>
          </div>
        )}
      </dl>
      <p className="record-title">Summary</p>
      <p className="message-text">{c.summary}</p>
      {c.resolution_note && (
        <Alert tone="success" title="Resolution">
          {c.resolution_note}
        </Alert>
      )}
      {c.view === "summary" && (
        <p className="muted small">
          Summary view: linked documents, conversation and notes are shown only to the requester and the assigned agent.
        </p>
      )}

      {actions.length > 0 && (
        <div className="message-actions" aria-label="Case actions">
          {actions.map((a) => (
            <Button key={a} variant={a === "cancel" ? "danger" : a === "assign_to_me" || a === "start" || a === "resolve" ? "primary" : "secondary"} className="btn-sm" onClick={() => setAction(a)}>
              {ACTIONS[a].label}
            </Button>
          ))}
        </div>
      )}

      {(c.conversation_excerpt?.length ?? 0) > 0 && (
        <details className="section">
          <summary>Conversation excerpt (last {c.conversation_excerpt!.length} messages)</summary>
          <ol className="record-list small">
            {c.conversation_excerpt!.map((m, i) => (
              <li key={i}>
                <strong>{m.sender === "USER" ? "Requester" : "Assistant"}:</strong> <span className="message-text">{m.content}</span>
              </li>
            ))}
          </ol>
        </details>
      )}
      {(c.documents?.length ?? 0) > 0 && (
        <div className="section">
          <p className="record-title">Linked documents</p>
          <ul className="record-list">
            {c.documents!.map((d) => (
              <LinkedDocument key={d.document_id} id={d.document_id} name={d.original_filename} />
            ))}
          </ul>
        </div>
      )}
      {c.related_checklist_id && c.view === "full" && (
        <details className="section">
          <summary>Linked readiness checklist</summary>
          <LinkedChecklist id={c.related_checklist_id} />
        </details>
      )}

      <p className="record-title">History</p>
      <ol className="record-list">
        {c.events.map((e, i) => (
          <li key={i}>
            {formatDateTime(e.created_at)}: {humanize(e.event_type)}
            {e.to_status && ` (${humanize(e.to_status)})`} by {e.actor_display_name}
            {e.note && <span className="muted"> · {e.note}</span>}
          </li>
        ))}
      </ol>
      {onClose && (
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      )}
      {action && (
        <ActionDialog
          action={action}
          detail={c}
          isAdmin={isAdmin}
          onClose={() => {
            setAction(null);
            void detail.run();
          }}
          onDone={(updated) => {
            setAction(null);
            setNotice(`${ACTIONS[action].label.replace("…", "")}: the case is now ${humanize(updated.status).toLowerCase()}.`);
            void detail.run();
            onChanged?.(updated);
          }}
        />
      )}
    </section>
  );
}
