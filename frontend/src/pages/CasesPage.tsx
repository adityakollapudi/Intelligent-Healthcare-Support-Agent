// Support cases (Phase 5): the caller's own cases from GET /support-cases, a detail view, and a
// confirmed create form. A case number is shown only after the backend has returned it.
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { Alert, Button, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, type BadgeTone } from "../components/ui";
import { useSession } from "../features/auth/session";
import { useRequest } from "../hooks/useRequest";
import { formatDateTime, humanize } from "../lib/format";
import { supportCasesService } from "../services";
import { CASE_CATEGORIES, CASE_STATUSES, type CaseCategory, type CaseDetail, type CaseStatus } from "../types/api";

const STATUS_TONE: Record<CaseStatus, BadgeTone> = {
  OPEN: "info",
  ASSIGNED: "info",
  IN_PROGRESS: "info",
  AWAITING_USER: "warning",
  RESOLVED: "success",
  CLOSED: "neutral",
  CANCELLED: "neutral",
};

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return <StatusBadge label={humanize(status)} tone={STATUS_TONE[status]} icon={status === "AWAITING_USER" ? "⚠" : "●"} />;
}

const SUMMARY_MIN = 10;
const SUMMARY_MAX = 2000;

function NewCaseForm({ onCreated, onCancel }: { onCreated: (c: CaseDetail) => void; onCancel: () => void }) {
  const [category, setCategory] = useState<CaseCategory>("OTHER");
  const [summary, setSummary] = useState("");
  const [touched, setTouched] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // One key per draft: a retry of the same draft can't create a second case; editing starts a new draft.
  const [key, setKey] = useState(() => crypto.randomUUID());

  const trimmed = summary.trim();
  const invalid =
    trimmed.length < SUMMARY_MIN
      ? `Describe the issue in at least ${SUMMARY_MIN} characters.`
      : trimmed.length > SUMMARY_MAX
        ? `Summaries can be up to ${SUMMARY_MAX} characters.`
        : null;

  const edit = (apply: () => void) => {
    apply();
    setKey(crypto.randomUUID());
    setError(null);
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await supportCasesService.create({ category, summary: trimmed }, key);
      setConfirming(false);
      onCreated(created);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className="card section"
      aria-label="New support case"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        setTouched(true);
        if (!invalid) setConfirming(true);
      }}
    >
      <div className="field">
        <label htmlFor="case-category">Category</label>
        <select id="case-category" value={category} onChange={(e) => edit(() => setCategory(e.target.value as CaseCategory))}>
          {CASE_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {humanize(c)}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="case-summary">What do you need help with?</label>
        <p id="case-summary-hint" className="field-hint">
          Don't include passwords or information about other people. Synthetic prototype: no real data.
        </p>
        <textarea
          id="case-summary"
          rows={4}
          value={summary}
          maxLength={SUMMARY_MAX + 1}
          aria-invalid={touched && invalid ? true : undefined}
          aria-describedby="case-summary-hint case-summary-error"
          onChange={(e) => edit(() => setSummary(e.target.value))}
        />
        {touched && invalid && (
          <p id="case-summary-error" className="field-error">
            {invalid}
          </p>
        )}
      </div>
      <div className="modal-actions">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">Review and create</Button>
      </div>
      <ConfirmDialog
        open={confirming}
        title="Create this support case?"
        confirmLabel={error ? "Try again" : "Create case"}
        busy={busy}
        onCancel={() => setConfirming(false)}
        onConfirm={() => void submit()}
      >
        <p>
          <strong>{humanize(category)}</strong>
        </p>
        <p className="message-text">{trimmed}</p>
        {Boolean(error) && <ErrorState error={error} />}
      </ConfirmDialog>
    </form>
  );
}

function CaseDetailView({ caseId, onClose }: { caseId: string; onClose: () => void }) {
  const detail = useRequest((signal) => supportCasesService.get(caseId, signal));
  useEffect(() => {
    void detail.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when the selected case changes
  }, [caseId]);
  const { state } = detail;
  return (
    <section className="card section" aria-label="Case details">
      {state.status === "loading" && <LoadingState label="Loading case…" />}
      {state.status === "error" && <ErrorState error={state.error} onRetry={() => void detail.run()} />}
      {state.status === "success" && (
        <>
          <div className="card-head">
            <h2 className="mono">{state.data.case_number}</h2>
            <CaseStatusBadge status={state.data.status} />
          </div>
          <dl className="facts">
            <div>
              <dt>Category</dt>
              <dd>{humanize(state.data.category)}</dd>
            </div>
            <div>
              <dt>Reason</dt>
              <dd>{humanize(state.data.escalation_reason)}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDateTime(state.data.created_at)}</dd>
            </div>
            {state.data.related_claim_number && (
              <div>
                <dt>Related claim</dt>
                <dd className="mono">{state.data.related_claim_number}</dd>
              </div>
            )}
          </dl>
          <p className="record-title">Summary</p>
          <p className="message-text">{state.data.summary}</p>
          {state.data.resolution_note && (
            <Alert tone="success" title="Resolution">
              {state.data.resolution_note}
            </Alert>
          )}
          <p className="record-title">History</p>
          <ol className="record-list">
            {state.data.events.map((e, i) => (
              <li key={i}>
                {formatDateTime(e.created_at)}: {humanize(e.event_type)}
                {e.to_status && ` (${humanize(e.to_status)})`} by {e.actor_display_name}
                {e.note && <span className="muted"> · {e.note}</span>}
              </li>
            ))}
          </ol>
        </>
      )}
      <Button variant="secondary" onClick={onClose}>
        Close
      </Button>
    </section>
  );
}

export function CasesPage() {
  const { can } = useSession();
  const canCreate = can("cases:create");
  const [params, setParams] = useSearchParams();
  const selected = params.get("case");
  const [status, setStatus] = useState<CaseStatus | "">("");
  const [creating, setCreating] = useState(false);
  const [justCreated, setJustCreated] = useState<CaseDetail | null>(null);
  const list = useRequest((signal) => supportCasesService.list({ status: status ? [status] : undefined }, signal));

  useEffect(() => {
    void list.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload on filter change or after creation
  }, [status, justCreated?.case_id]);

  const select = (id: string | null) => setParams(id ? { case: id } : {});

  return (
    <>
      <PageHeader
        title="Support cases"
        description="Ask a support agent for help and track your requests."
        actions={
          canCreate && !creating ? (
            <Button onClick={() => setCreating(true)}>New case</Button>
          ) : undefined
        }
      />
      {justCreated && (
        <Alert tone="success" title={`Support case ${justCreated.case_number} created`}>
          It's {humanize(justCreated.status).toLowerCase()} and waiting for a support agent.
        </Alert>
      )}
      {creating && (
        <NewCaseForm
          onCancel={() => setCreating(false)}
          onCreated={(c) => {
            setCreating(false);
            setJustCreated(c);
            select(c.case_id);
          }}
        />
      )}
      {selected && <CaseDetailView caseId={selected} onClose={() => select(null)} />}

      <section className="section" aria-labelledby="cases-heading">
        <div className="card-head">
          <h2 id="cases-heading">Your cases</h2>
          <div className="field field-inline">
            <label htmlFor="case-status-filter">Status</label>
            <select id="case-status-filter" value={status} onChange={(e) => setStatus(e.target.value as CaseStatus | "")}>
              <option value="">All</option>
              {CASE_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {humanize(s)}
                </option>
              ))}
            </select>
          </div>
        </div>
        {list.state.status === "loading" && <LoadingState label="Loading cases…" />}
        {list.state.status === "error" && <ErrorState error={list.state.error} onRetry={() => void list.run()} />}
        {list.state.status === "success" && list.state.data.items.length === 0 && (
          <EmptyState title="No cases to show">
            {status ? "No cases have this status." : "Cases you create here or from the assistant are listed here."}
          </EmptyState>
        )}
        {list.state.status === "success" && list.state.data.items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Status</th>
                  <th scope="col">Category</th>
                  <th scope="col">Summary</th>
                  <th scope="col">Updated</th>
                </tr>
              </thead>
              <tbody>
                {list.state.data.items.map((c) => (
                  <tr key={c.case_id} aria-current={c.case_id === selected ? "true" : undefined}>
                    <td>
                      <button type="button" className="link-button mono" onClick={() => select(c.case_id)}>
                        {c.case_number}
                      </button>
                    </td>
                    <td>
                      <CaseStatusBadge status={c.status} />
                    </td>
                    <td>{humanize(c.category)}</td>
                    <td>{c.summary_preview}</td>
                    <td>{formatDateTime(c.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
