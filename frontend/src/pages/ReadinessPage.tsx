// Phase 6 prior-authorization documentation readiness. Checklists come only from the backend's
// deterministic evaluator (POST /authorization/readiness); this screen never computes a status.
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ChecklistLegend, READINESS_DISCLAIMER } from "../components/Checklist";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { CHECKLIST_STATUS_META, JOB_STATUS_META, MetaBadge, READINESS_STATUS_META } from "../components/status";
import { Alert, Button, EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui";
import { useSession } from "../features/auth/session";
import { useRequest } from "../hooks/useRequest";
import { formatDateTime, humanize } from "../lib/format";
import { documentsService, readinessService, supportCasesService } from "../services";
import type { CaseDetail, ChecklistDetail } from "../types/api";

const USABLE = new Set(["COMPLETED", "COMPLETED_WITH_WARNINGS"]);

/** Sends the checklist to a support agent. The case is created only when the user confirms, with a
 * per-attempt Idempotency-Key so a retry can't create a duplicate; the case number shown is the
 * backend's. Creating a case doesn't mean anyone has reviewed it yet. */
function SendForReview({ checklist }: { checklist: ChecklistDetail }) {
  const offer = checklist.escalation_offer!;
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [created, setCreated] = useState<CaseDetail | null>(null);
  const [key] = useState(() => crypto.randomUUID());

  if (created) {
    return (
      <Alert tone="success" title={`Support case ${created.case_number} created`}>
        It's waiting for a support agent; nobody has reviewed it yet. <Link to={`/cases?case=${encodeURIComponent(created.case_id)}`}>Track the case</Link>
      </Alert>
    );
  }
  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      setCreated(await supportCasesService.create(
        { category: offer.category, escalation_reason: offer.escalation_reason, summary: offer.summary, related_checklist_id: offer.related_checklist_id, document_ids: offer.document_ids },
        key,
      ));
      setOpen(false);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Send to a support agent for review
      </Button>
      <ConfirmDialog open={open} title="Send this checklist for human review?" confirmLabel={error ? "Try again" : "Create case"} busy={busy} onCancel={() => setOpen(false)} onConfirm={() => void confirm()}>
        <p>A support case will be created. The assigned agent will be able to see this checklist and the {offer.document_ids.length} linked document(s).</p>
        <p className="message-text small">{offer.summary}</p>
        {Boolean(error) && <ErrorState error={error} />}
      </ConfirmDialog>
    </>
  );
}

export function ChecklistReport({ checklist }: { checklist: ChecklistDetail }) {
  const { can } = useSession();
  const docName = new Map(checklist.documents.map((d) => [d.document_id, d.original_filename]));
  return (
    <section className="card section" aria-label="Readiness checklist">
      <Alert tone="warning" title="Not an authorization decision">
        {checklist.disclaimer}
      </Alert>
      <div className="card-head">
        <h2>
          {checklist.display_name} <span className="muted mono small">{checklist.procedure_code}</span>
        </h2>
        <MetaBadge meta={READINESS_STATUS_META[checklist.readiness_status]} />
      </div>
      <p className="muted small">
        Requirement set v{checklist.requirement_set_version} · source {checklist.requirement_source_document ?? "not available"}
        {" "}· rules v{checklist.rules_version} · created {formatDateTime(checklist.created_at)}
      </p>
      <dl className="facts" aria-label="Counts">
        {(Object.keys(checklist.counts) as (keyof typeof checklist.counts)[]).map((s) => (
          <div key={s}>
            <dt>{CHECKLIST_STATUS_META[s].label}</dt>
            <dd>{checklist.counts[s]}</dd>
          </div>
        ))}
      </dl>
      {checklist.warnings.length > 0 && (
        <Alert tone="warning" title="Warnings">
          <ul>
            {checklist.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Alert>
      )}
      <ul className="checklist" aria-label="Checklist items">
        {checklist.items.map((item) => (
          <li key={item.requirement_code} className="checklist-item">
            <MetaBadge meta={CHECKLIST_STATUS_META[item.item_status]} />
            <div>
              <p>
                <span className="mono">{item.requirement_code}</span> {item.description}
                {!item.is_mandatory && <span className="muted"> (if applicable)</span>}
              </p>
              <p className="muted small">{item.explanation}</p>
              {item.evidence.length > 0 && (
                <p className="small">
                  Evidence:{" "}
                  {item.evidence
                    .map((e) => `${humanize(e.field_name)} ${e.validation_status} in ${docName.get(e.document_id) ?? "document"}${e.source_page ? ` p.${e.source_page}` : ""}`)
                    .join("; ")}
                </p>
              )}
              <p className="muted small">
                Requirement source:{" "}
                {item.requirement_source
                  ? `${item.requirement_source.document_title} v${item.requirement_source.document_version}${item.requirement_source.section_heading ? `, ${item.requirement_source.section_heading}` : ""}`
                  : "not verified"}
              </p>
            </div>
          </li>
        ))}
      </ul>
      {checklist.escalation_offer && can("cases:create") && <SendForReview checklist={checklist} />}
      {checklist.review_state !== "NOT_SUBMITTED" && (
        <p className="muted small">Review state: {humanize(checklist.review_state)} (a support case is linked; this is not an approval).</p>
      )}
      <details open>
        <summary>Reviewer summary (draft)</summary>
        {/* Plain text: the summary contains document-derived values. */}
        <pre className="summary">{checklist.reviewer_summary}</pre>
      </details>
    </section>
  );
}

export function ReadinessPage() {
  const [params, setParams] = useSearchParams();
  const openId = params.get("checklist");
  const preselect = params.get("doc");
  const sets = useRequest((signal) => readinessService.requirementSets(signal));
  const docs = useRequest((signal) => documentsService.list(signal));
  const recent = useRequest((signal) => readinessService.list(signal));
  const opened = useRequest((signal) => readinessService.get(openId ?? "", signal));
  const [code, setCode] = useState("");
  const [chosen, setChosen] = useState<string[]>(preselect ? [preselect] : []);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<ChecklistDetail | null>(null);

  useEffect(() => {
    void sets.run();
    void docs.run();
    void recent.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial load
  }, []);
  useEffect(() => {
    if (openId && openId !== result?.checklist_id) void opened.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reopen when the URL changes
  }, [openId]);

  const usable = docs.state.status === "success" ? docs.state.data.items.filter((d) => d.latest_job && USABLE.has(d.latest_job.status)) : [];
  const others = docs.state.status === "success" ? docs.state.data.items.filter((d) => !usable.includes(d)) : [];
  const toggle = (id: string) => setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length >= 10 ? c : [...c, id]));

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const checklist = await readinessService.create({ procedure_code: code, document_ids: chosen, provider_note: note.trim() || null });
      setResult(checklist);
      setParams({ checklist: checklist.checklist_id });
      void recent.run();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const shown = result && result.checklist_id === openId ? result : opened.state.status === "success" && openId ? opened.state.data : null;

  return (
    <>
      <PageHeader title="Prior authorization readiness" description="Check whether analyzed documents appear to contain what a configured (fictional) requirement set lists." />
      <Alert tone="info" title="Readiness is not approval">
        {READINESS_DISCLAIMER}
      </Alert>

      <section className="section card" aria-labelledby="new-check">
        <h2 id="new-check">New readiness check</h2>
        <div className="field">
          <label htmlFor="procedure">Requirement set</label>
          {sets.state.status === "error" ? (
            <ErrorState error={sets.state.error} onRetry={() => void sets.run()} />
          ) : (
            <select id="procedure" value={code} onChange={(e) => setCode(e.target.value)}>
              <option value="">Choose a procedure…</option>
              {sets.state.status === "success" &&
                sets.state.data.map((s) => (
                  <option key={s.procedure_code} value={s.procedure_code}>
                    {s.display_name} ({s.procedure_code}, v{s.version})
                  </option>
                ))}
            </select>
          )}
        </div>
        <fieldset className="field">
          <legend>Analyzed documents (up to 10)</legend>
          {docs.state.status === "loading" && <LoadingState label="Loading documents…" />}
          {docs.state.status === "error" && <ErrorState error={docs.state.error} onRetry={() => void docs.run()} />}
          {docs.state.status === "success" && usable.length === 0 && (
            <p className="muted">
              No analyzed documents yet. <Link to="/documents">Upload and analyze documents</Link> first.
            </p>
          )}
          {usable.map((d) => (
            <label key={d.document_id} className="check-row">
              <input type="checkbox" checked={chosen.includes(d.document_id)} onChange={() => toggle(d.document_id)} />{" "}
              {d.original_filename} <MetaBadge meta={JOB_STATUS_META[d.latest_job!.status]} />
              {d.latest_job!.detected_document_type && <span className="muted small"> {humanize(d.latest_job!.detected_document_type)}</span>}
            </label>
          ))}
          {others.length > 0 && (
            <p className="muted small">
              {others.length} document(s) can't be used until their analysis finishes successfully.
            </p>
          )}
        </fieldset>
        <div className="field">
          <label htmlFor="provider-note">Note for the reviewer (optional)</label>
          <textarea id="provider-note" rows={2} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
        <Button disabled={!code || chosen.length === 0} busy={busy} onClick={() => void submit()}>
          Create checklist
        </Button>
        {Boolean(error) && <ErrorState error={error} />}
      </section>

      {openId && !shown && opened.state.status === "loading" && <LoadingState label="Loading checklist…" />}
      {openId && opened.state.status === "error" && !shown && <ErrorState error={opened.state.error} />}
      {shown && <ChecklistReport checklist={shown} />}

      <section className="section" aria-labelledby="recent-heading">
        <h2 id="recent-heading">Recent checklists</h2>
        {recent.state.status === "success" && recent.state.data.items.length === 0 && (
          <EmptyState title="No checklists yet">Checklists you create are listed here.</EmptyState>
        )}
        {recent.state.status === "success" && recent.state.data.items.length > 0 && (
          <ul className="record-list">
            {recent.state.data.items.map((c) => (
              <li key={c.checklist_id}>
                <button type="button" className="link-button" onClick={() => setParams({ checklist: c.checklist_id })}>
                  {c.procedure_code}
                </button>{" "}
                <MetaBadge meta={READINESS_STATUS_META[c.readiness_status]} />{" "}
                <span className="muted small">{formatDateTime(c.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="section card" aria-labelledby="legend-heading">
        <h2 id="legend-heading">What checklist statuses mean</h2>
        <ChecklistLegend />
      </section>
    </>
  );
}
