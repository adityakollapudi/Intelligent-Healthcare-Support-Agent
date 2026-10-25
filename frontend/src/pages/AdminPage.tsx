// Phase 7 administrator dashboard. Every number comes from GET /admin/metrics, /admin/knowledge-gaps
// or /admin/audit-events (database aggregates). A failed request shows an error, never zeros; a value
// with no underlying data (e.g. a median with no resolved cases) shows "—", not 0.
import { useEffect, useState } from "react";

import { Alert, Button, EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui";
import { useRequest } from "../hooks/useRequest";
import { formatDateTime, humanize } from "../lib/format";
import { adminService } from "../services";
import type { AdminMetrics, AuditEvent, Counted } from "../types/api";
import { CaseQueue } from "./AgentPage";

const isoDay = (d: Date) => d.toISOString().slice(0, 10);
const daysAgo = (n: number) => isoDay(new Date(Date.now() - n * 86_400_000));
const dash = (v: number | null | undefined, unit = "") => (v === null || v === undefined ? "—" : `${v}${unit}`);

function Stat({ label, value, help }: { label: string; value: string | number; help: string }) {
  return (
    <div className="stat card">
      <p className="stat-value">{value}</p>
      <p className="stat-label">{label}</p>
      <p className="muted small">{help}</p>
    </div>
  );
}

/** Horizontal bars with the exact numbers in a table, so nothing depends on reading a chart. */
function Distribution({ title, data, caption }: { title: string; data: Counted; caption: string }) {
  const rows = Object.entries(data).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...rows.map(([, n]) => n));
  return (
    <section className="card" aria-label={title}>
      <h3>{title}</h3>
      <p className="muted small">{caption}</p>
      {rows.length === 0 ? (
        <p className="muted">No records in this period.</p>
      ) : (
        <table className="bars">
          <tbody>
            {rows.map(([k, n]) => (
              <tr key={k}>
                <th scope="row">{humanize(k)}</th>
                <td>
                  <span className="bar" style={{ width: `${(n / max) * 100}%` }} aria-hidden="true" />
                </td>
                <td className="num">{n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Overview({ m }: { m: AdminMetrics }) {
  const jobs = m.documents.jobs_by_status;
  const toolFailures = Object.values(m.tools).reduce((sum, t) => sum + (t.EXECUTION_ERROR ?? 0), 0);
  return (
    <>
      <div className="stats">
        <Stat label="Open workload now" value={m.cases.current_open_workload} help="Open, assigned, in progress or awaiting the requester (current, not period-bound)" />
        <Stat label="Unassigned in queue" value={m.cases.current_unassigned_open} help="Open cases nobody has taken yet (current)" />
        <Stat label="Cases created" value={m.cases.created} help={`In the period; ${m.cases.escalated_from_chat} came from the assistant`} />
        <Stat label="Resolved in period" value={m.cases.resolved_in_period} help={`Median time to resolution: ${dash(m.cases.median_hours_to_resolution, " h")}`} />
        <Stat label="Questions asked" value={m.chat.user_messages} help={`${m.chat.escalations_offered} answers offered human help`} />
        <Stat label="Document analyses failed" value={jobs.FAILED ?? 0} help={`Of ${Object.values(jobs).reduce((a, b) => a + b, 0)} analysis jobs in the period`} />
        <Stat label="Tool execution errors" value={toolFailures} help="Lookups that failed inside the backend (not 'not found')" />
        <Stat label="Access denied events" value={m.security.access_denied_events} help={`${m.security.rejected_case_updates} case updates were rejected`} />
      </div>
      <div className="grid-2">
        <Distribution title="Cases by current status" data={m.cases.current_by_status} caption="All cases, current snapshot" />
        <Distribution title="New cases by category" data={m.cases.created_by_category} caption="Cases created in the period" />
        <Distribution title="Why cases were escalated" data={m.cases.created_by_escalation_reason} caption="Cases created in the period" />
        <Distribution title="Answer evidence" data={m.chat.by_evidence_status} caption="Assistant answers in the period" />
        <Distribution title="Document analysis jobs" data={jobs} caption="Jobs created in the period" />
        <Distribution title="Readiness checklists" data={m.readiness.by_status} caption="Checklists created in the period" />
      </div>
      <section className="card section" aria-label="Cases per day">
        <h3>Cases per day (UTC)</h3>
        {m.cases.created_per_day.length === 0 && m.cases.resolved_per_day.length === 0 ? (
          <p className="muted">No cases were created or resolved in this period.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Created</th>
                  <th scope="col">Resolved</th>
                </tr>
              </thead>
              <tbody>
                {[...new Set([...m.cases.created_per_day, ...m.cases.resolved_per_day].map((d) => d.date))].sort().map((d) => (
                  <tr key={d}>
                    <td>{d}</td>
                    <td className="num">{m.cases.created_per_day.find((x) => x.date === d)?.count ?? 0}</td>
                    <td className="num">{m.cases.resolved_per_day.find((x) => x.date === d)?.count ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section className="card section" aria-label="Workflow health">
        <h3>Workflow health</h3>
        <dl className="facts">
          <div>
            <dt>Answer latency p50 / p95</dt>
            <dd>
              {dash(m.chat.latency_ms.p50, " ms")} / {dash(m.chat.latency_ms.p95, " ms")} <span className="muted small">({m.chat.latency_ms.sample_size} answers)</span>
            </dd>
          </div>
          <div>
            <dt>Document failures by cause</dt>
            <dd>
              {Object.keys(m.documents.failures_by_error_code).length === 0
                ? "None"
                : Object.entries(m.documents.failures_by_error_code).map(([k, n]) => `${humanize(k)}: ${n}`).join(", ")}
            </dd>
          </div>
          <div>
            <dt>Most common field problems</dt>
            <dd>
              {m.documents.top_field_issues.length === 0
                ? "None"
                : m.documents.top_field_issues.slice(0, 5).map((f) => `${humanize(f.field_name)} ${humanize(f.status)} (${f.count})`).join("; ")}
            </dd>
          </div>
          <div>
            <dt>Checklists by review state</dt>
            <dd>{Object.entries(m.readiness.by_review_state).map(([k, n]) => `${humanize(k)}: ${n}`).join(", ") || "None"}</dd>
          </div>
        </dl>
        {m.unavailable.length > 0 && <p className="muted small">Not collected in this build: {m.unavailable.join(", ")}.</p>}
      </section>
    </>
  );
}

function KnowledgeGapsPanel({ range }: { range: { from: string; to: string } }) {
  const req = useRequest((signal) => adminService.knowledgeGaps(range, signal));
  useEffect(() => {
    void req.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload on range change
  }, [range.from, range.to]);
  if (req.state.status === "loading" || req.state.status === "idle") return <LoadingState label="Loading knowledge gaps…" />;
  if (req.state.status === "error") return <ErrorState error={req.state.error} onRetry={() => void req.run()} />;
  const g = req.state.data;
  return (
    <section className="section" aria-label="Knowledge gaps">
      <Alert tone="info">{g.note}</Alert>
      <h3>Questions without a supported answer</h3>
      {g.items.length === 0 ? (
        <EmptyState title="No recurring gaps">
          No topic was left unanswered for two or more people in this period.{g.suppressed_topics > 0 && ` ${g.suppressed_topics} single-person topic(s) are hidden for privacy.`}
        </EmptyState>
      ) : (
        <div className="table-wrap">
          <table aria-label="Gap topics">
            <thead>
              <tr>
                <th scope="col">Topic</th>
                <th scope="col">Evidence</th>
                <th scope="col">Times</th>
                <th scope="col">People</th>
                <th scope="col">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {g.items.map((i) => (
                <tr key={`${i.gap_topic}-${i.evidence_status}`}>
                  <td>{i.gap_topic}</td>
                  <td>{humanize(i.evidence_status)}</td>
                  <td className="num">{i.occurrences}</td>
                  <td className="num">{i.distinct_users}</td>
                  <td>{formatDateTime(i.last_seen_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {g.items.length > 0 && g.suppressed_topics > 0 && <p className="muted small">{g.suppressed_topics} single-person topic(s) hidden for privacy.</p>}
      <div className="grid-2">
        <section className="card">
          <h3>By question type</h3>
          {g.by_intent.length === 0 ? <p className="muted">None.</p> : (
            <ul className="record-list">{g.by_intent.map((r) => <li key={`${r.intent}-${r.evidence_status}`}>{humanize(r.intent)} · {humanize(r.evidence_status)}: {r.occurrences}</li>)}</ul>
          )}
        </section>
        <section className="card">
          <h3>Requested procedures with no requirement set</h3>
          {g.requirement_set_misses.length === 0 ? <p className="muted">None.</p> : (
            <ul className="record-list">{g.requirement_set_misses.map((r) => <li key={r.requested_procedure_code}><span className="mono">{r.requested_procedure_code}</span>: {r.occurrences}</li>)}</ul>
          )}
        </section>
        <section className="card">
          <h3>Tool failures</h3>
          {g.tool_failures.length === 0 ? <p className="muted">None.</p> : (
            <ul className="record-list">{g.tool_failures.map((r) => <li key={r.tool_name}>{r.tool_name}: {r.occurrences}</li>)}</ul>
          )}
        </section>
      </div>
    </section>
  );
}

function AuditPanel() {
  const [action, setAction] = useState("");
  const [outcome, setOutcome] = useState("");
  const [ref, setRef] = useState("");
  const [applied, setApplied] = useState({ action: "", outcome: "", ref: "" });
  const [items, setItems] = useState<AuditEvent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const load = async (from: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const page = await adminService.auditEvents({
        action: applied.action || undefined,
        outcome: applied.outcome || undefined,
        resource_ref: applied.ref || undefined,
        cursor: from,
      });
      setItems((prev) => (from ? [...prev, ...page.items] : page.items));
      setCursor(page.next_cursor);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void load(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when filters are applied
  }, [applied]);
  const actionValid = !action || /^[A-Z_]{3,60}$/.test(action);

  return (
    <section className="section" aria-label="Audit log">
      <p className="muted small">Read-only. Audit records hold identifiers, outcomes and allowlisted codes, never document or message content.</p>
      <form className="row filters" onSubmit={(e) => { e.preventDefault(); if (actionValid) setApplied({ action, outcome, ref: ref.trim() }); }}>
        <div className="field field-inline">
          <label htmlFor="a-action">Action</label>
          <input id="a-action" value={action} placeholder="SUPPORT_CASE_STATUS_CHANGED" onChange={(e) => setAction(e.target.value.toUpperCase())} />
        </div>
        <div className="field field-inline">
          <label htmlFor="a-outcome">Outcome</label>
          <select id="a-outcome" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
            <option value="">All</option>
            <option value="SUCCESS">Success</option>
            <option value="DENIED">Denied</option>
            <option value="FAILURE">Failure</option>
          </select>
        </div>
        <div className="field field-inline">
          <label htmlFor="a-ref">Resource</label>
          <input id="a-ref" value={ref} placeholder="CASE-2026-000001" maxLength={80} onChange={(e) => setRef(e.target.value)} />
        </div>
        <Button type="submit" variant="secondary" className="btn-sm" disabled={!actionValid}>
          Filter
        </Button>
      </form>
      {Boolean(error) && <ErrorState error={error} onRetry={() => void load(null)} />}
      {!error && !loading && items.length === 0 && <EmptyState title="No audit events">No events match these filters.</EmptyState>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table aria-label="Audit events">
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Actor</th>
                <th scope="col">Action</th>
                <th scope="col">Outcome</th>
                <th scope="col">Resource</th>
                <th scope="col">Details</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id}>
                  <td>{formatDateTime(e.occurred_at)}</td>
                  <td>{e.actor ? `${e.actor.display_name} (${humanize(e.actor.role ?? "")})` : <span className="muted">Anonymous</span>}</td>
                  <td className="mono small">{e.action}</td>
                  <td>{humanize(e.outcome)}{e.reason_code && <span className="muted small"> · {e.reason_code}</span>}</td>
                  <td className="small">{e.resource_type && `${e.resource_type} `}<span className="mono">{e.resource_ref}</span></td>
                  <td className="small mono">{Object.keys(e.metadata).length ? JSON.stringify(e.metadata) : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {loading && <LoadingState label="Loading audit events…" />}
      {cursor && !loading && <Button variant="secondary" onClick={() => void load(cursor)}>Load older events</Button>}
    </section>
  );
}

const TABS = ["Overview", "Knowledge gaps", "Audit log", "Cases"] as const;

export function AdminPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [from, setFrom] = useState(daysAgo(29));
  const [to, setTo] = useState(isoDay(new Date()));
  const [range, setRange] = useState({ from: daysAgo(29), to: isoDay(new Date()) });
  const metrics = useRequest((signal) => adminService.metrics(range, signal));
  useEffect(() => {
    if (tab === "Overview") void metrics.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload on range change or when returning to the tab
  }, [range, tab]);
  const rangeError = from > to ? "'From' must be on or before 'to'." : null;

  return (
    <>
      <PageHeader
        title="Admin dashboard"
        description="Counts from the synthetic prototype's own records: cases, assistant answers, tool calls, document analyses and audit events. Nothing here is estimated or sample data."
      />
      <div className="row" role="tablist" aria-label="Dashboard sections">
        {TABS.map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} className={`btn btn-sm ${tab === t ? "btn-primary" : "btn-secondary"}`} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      {(tab === "Overview" || tab === "Knowledge gaps") && (
        <form className="row filters section" onSubmit={(e) => { e.preventDefault(); if (!rangeError) setRange({ from, to }); }}>
          <div className="field field-inline">
            <label htmlFor="m-from">From</label>
            <input id="m-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </div>
          <div className="field field-inline">
            <label htmlFor="m-to">To</label>
            <input id="m-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
          <Button type="submit" variant="secondary" className="btn-sm" disabled={Boolean(rangeError)}>
            Apply
          </Button>
          <span className="muted small">Whole days in UTC, up to 366 days.</span>
        </form>
      )}
      {rangeError && <p className="field-error">{rangeError}</p>}
      {tab === "Overview" && (
        <>
          {(metrics.state.status === "loading" || metrics.state.status === "idle") && <LoadingState label="Loading metrics…" />}
          {metrics.state.status === "error" && <ErrorState error={metrics.state.error} onRetry={() => void metrics.run()} />}
          {metrics.state.status === "success" && (
            <>
              <p className="muted small" role="status">
                {metrics.state.data.period.from} to {metrics.state.data.period.to} (UTC) · calculated {formatDateTime(metrics.state.data.generated_at)} when this page loaded (not live)
              </p>
              <Overview m={metrics.state.data} />
            </>
          )}
        </>
      )}
      {tab === "Knowledge gaps" && <KnowledgeGapsPanel range={range} />}
      {tab === "Audit log" && <AuditPanel />}
      {tab === "Cases" && <CaseQueue scopes={[{ scope: "all", label: "All cases" }]} isAdmin />}
    </>
  );
}
