// Phase 7 support-agent workspace: the unassigned queue and "assigned to me", filtered and paged by
// the backend (GET /support-cases?scope=queue|assigned), with the shared case panel for review.
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Button, EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui";
import { CasePanel, CaseStatusBadge } from "../features/cases/CasePanel";
import { formatDateTime, humanize } from "../lib/format";
import { supportCasesService } from "../services";
import { CASE_CATEGORIES, CASE_STATUSES, type CaseStatus, type CaseSummary } from "../types/api";

type Scope = "queue" | "assigned" | "all";

export function CaseQueue({ scopes, isAdmin = false }: { scopes: { scope: Scope; label: string }[]; isAdmin?: boolean }) {
  const [params, setParams] = useSearchParams();
  const selected = params.get("case");
  const [scope, setScope] = useState<Scope>(scopes[0]!.scope);
  const [status, setStatus] = useState<CaseStatus | "">("");
  const [category, setCategory] = useState("");
  const [caseNumber, setCaseNumber] = useState("");
  const [applied, setApplied] = useState("");
  const [items, setItems] = useState<CaseSummary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [version, setVersion] = useState(0);

  const load = async (from: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const page = await supportCasesService.list({
        scope,
        status: status ? [status] : undefined,
        category: category || undefined,
        case_number: applied || undefined,
        cursor: from,
      });
      setItems((prev) => (from ? [...prev, ...page.items] : page.items));
      setCursor(page.next_cursor);
    } catch (err) {
      setError(err);
      if (!from) setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when the scope, a filter or a case changes
  }, [scope, status, category, applied, version]);

  const numberValid = !caseNumber || /^CASE-\d{4}-\d{6}$/i.test(caseNumber.trim());

  return (
    <>
      {selected && (
        <CasePanel
          key={selected}
          caseId={selected}
          isAdmin={isAdmin}
          onChanged={() => setVersion((v) => v + 1)}
          onClose={() => setParams({})}
        />
      )}
      <section className="section" aria-labelledby="queue-heading">
        <div className="card-head">
          <h2 id="queue-heading">Cases</h2>
          {scopes.length > 1 && (
            <div className="row" role="tablist" aria-label="Case list">
              {scopes.map((s) => (
                <button
                  key={s.scope}
                  type="button"
                  role="tab"
                  aria-selected={scope === s.scope}
                  className={`btn btn-sm ${scope === s.scope ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => setScope(s.scope)}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
        </div>
        <form
          className="row filters"
          onSubmit={(e) => {
            e.preventDefault();
            if (numberValid) setApplied(caseNumber.trim().toUpperCase());
          }}
        >
          {scope !== "queue" && (
            <div className="field field-inline">
              <label htmlFor="q-status">Status</label>
              <select id="q-status" value={status} onChange={(e) => setStatus(e.target.value as CaseStatus | "")}>
                <option value="">All</option>
                {CASE_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {humanize(s)}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="field field-inline">
            <label htmlFor="q-category">Category</label>
            <select id="q-category" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All</option>
              {CASE_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {humanize(c)}
                </option>
              ))}
            </select>
          </div>
          <div className="field field-inline">
            <label htmlFor="q-number">Case number</label>
            <input id="q-number" value={caseNumber} placeholder="CASE-2026-000001" aria-invalid={!numberValid || undefined} onChange={(e) => setCaseNumber(e.target.value)} />
          </div>
          <Button type="submit" variant="secondary" className="btn-sm" disabled={!numberValid}>
            Search
          </Button>
          {applied && (
            <Button type="button" variant="ghost" className="btn-sm" onClick={() => { setCaseNumber(""); setApplied(""); }}>
              Clear
            </Button>
          )}
        </form>
        {!numberValid && <p className="field-error">Case numbers look like CASE-2026-000001.</p>}
        {Boolean(error) && <ErrorState error={error} onRetry={() => void load(null)} />}
        {!error && !loading && items.length === 0 && (
          <EmptyState title={scope === "queue" ? "The queue is empty" : "No cases to show"}>
            {scope === "queue" ? "There are no unassigned open cases right now." : "No cases match these filters."}
          </EmptyState>
        )}
        {items.length > 0 && (
          <div className="table-wrap">
            <table aria-label="Case list">
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Status</th>
                  <th scope="col">Category</th>
                  <th scope="col">Escalation reason</th>
                  <th scope="col">Summary</th>
                  <th scope="col">Assigned</th>
                  <th scope="col">Updated</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.case_id} aria-current={c.case_id === selected ? "true" : undefined}>
                    <td>
                      <button type="button" className="link-button mono" onClick={() => setParams({ case: c.case_id })}>
                        {c.case_number}
                      </button>
                    </td>
                    <td>
                      <CaseStatusBadge status={c.status} />
                    </td>
                    <td>{humanize(c.category)}</td>
                    <td>{humanize(c.escalation_reason)}</td>
                    <td>{c.summary_preview}</td>
                    <td>{c.assigned_to?.display_name ?? <span className="muted">Unassigned</span>}</td>
                    <td>{formatDateTime(c.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {loading && <LoadingState label="Loading cases…" />}
        {cursor && !loading && (
          <Button variant="secondary" onClick={() => void load(cursor)}>
            Load more
          </Button>
        )}
      </section>
    </>
  );
}

export function AgentPage() {
  return (
    <>
      <PageHeader
        title="Case queue"
        description="Pick up unassigned cases, then work the cases assigned to you. Every status change is checked by the server and recorded in the case history and audit log."
      />
      <CaseQueue scopes={[{ scope: "queue", label: "Unassigned queue" }, { scope: "assigned", label: "Assigned to me" }]} />
    </>
  );
}
