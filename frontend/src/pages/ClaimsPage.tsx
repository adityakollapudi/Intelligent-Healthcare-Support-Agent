import { useEffect, useState, type FormEvent } from "react";

import { CLAIM_STATUS_META, MetaBadge } from "../components/status";
import { Alert, Button, EmptyState, ErrorState, LoadingState, PageHeader, TextField } from "../components/ui";
import { useRequest } from "../hooks/useRequest";
import { isApiError } from "../lib/errors";
import { formatDate, formatDateTime } from "../lib/format";
import { claimsService } from "../services";
import { CLAIM_STATUSES, type ClaimDetail, type ClaimStatus, type ClaimSummary } from "../types/api";

export const CLAIM_NUMBER_PATTERN = /^SYN-CLM-\d{4}-\d{6}$/;

function ClaimCard({ claim }: { claim: ClaimDetail }) {
  const meta = CLAIM_STATUS_META[claim.status];
  return (
    <article className="card" aria-labelledby="claim-title">
      <div className="card-head">
        <h2 id="claim-title" className="mono">
          {claim.claim_number}
        </h2>
        <MetaBadge meta={meta} />
      </div>
      <p className="muted small">From your claim record (synthetic data)</p>
      <dl className="facts">
        <div>
          <dt>Status meaning</dt>
          <dd>{meta.help}</dd>
        </div>
        {claim.status_description && (
          <div>
            <dt>Details</dt>
            <dd>{claim.status_description}</dd>
          </div>
        )}
        <div>
          <dt>Provider</dt>
          <dd>{claim.provider_name ?? "Not recorded"}</dd>
        </div>
        <div>
          <dt>Service date</dt>
          <dd>{formatDate(claim.service_date)}</dd>
        </div>
        <div>
          <dt>Submitted</dt>
          <dd>{formatDate(claim.submission_date)}</dd>
        </div>
        <div>
          <dt>Last updated</dt>
          <dd>{formatDateTime(claim.last_status_change_at)}</dd>
        </div>
        <div>
          <dt>Plan</dt>
          <dd className="mono">{claim.plan_code}</dd>
        </div>
      </dl>
    </article>
  );
}

function ClaimLookup({ initial }: { initial: string | null }) {
  const [value, setValue] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const lookup = useRequest((signal, number: string) => claimsService.get(number, signal));

  useEffect(() => {
    if (initial) {
      setValue(initial);
      setInputError(null);
      void lookup.run(initial);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run is stable
  }, [initial]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const number = value.trim().toUpperCase();
    if (!CLAIM_NUMBER_PATTERN.test(number)) {
      setInputError("Use the format SYN-CLM-2026-000101.");
      lookup.reset(); // don't leave an earlier result next to the new, invalid input
      return;
    }
    setInputError(null);
    void lookup.run(number);
  };

  const { state } = lookup;
  return (
    <section aria-labelledby="lookup-heading" className="section">
      <h2 id="lookup-heading">Look up a claim</h2>
      <form className="inline-form" onSubmit={onSubmit} noValidate>
        <TextField
          label="Claim number"
          hint="Shown on your claim documents, e.g. SYN-CLM-2026-000101"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          error={inputError}
          autoComplete="off"
          spellCheck={false}
        />
        <Button type="submit" busy={state.status === "loading"}>
          Look up
        </Button>
      </form>
      <div aria-live="polite">
        {state.status === "loading" && <LoadingState label="Looking up claim…" />}
        {state.status === "error" &&
          (isApiError(state.error) && state.error.isNotFound ? (
            <Alert tone="warning" title="No claim found">
              We couldn't find a claim with that number on your account. Check the number and try again.
            </Alert>
          ) : (
            <ErrorState error={state.error} onRetry={() => void lookup.run(value.trim().toUpperCase())} />
          ))}
        {state.status === "success" && <ClaimCard claim={state.data} />}
      </div>
    </section>
  );
}

function ClaimList({ onSelect }: { onSelect: (claimNumber: string) => void }) {
  const [statusFilter, setStatusFilter] = useState<ClaimStatus | "">("");
  const [items, setItems] = useState<ClaimSummary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const page = useRequest((signal, filter: ClaimStatus | "", after: string | null) =>
    claimsService.list({ status: filter ? [filter] : undefined, limit: 10, cursor: after }, signal),
  );

  const load = async (filter: ClaimStatus | "", after: string | null) => {
    const result = await page.run(filter, after);
    if (result) {
      setItems((prev) => (after ? [...prev, ...result.items] : result.items));
      setCursor(result.next_cursor);
    }
  };

  useEffect(() => {
    void load(statusFilter, null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload only when the filter changes
  }, [statusFilter]);

  const loading = page.state.status === "loading";
  return (
    <section aria-labelledby="list-heading" className="section">
      <div className="section-head">
        <h2 id="list-heading">Your claims</h2>
        <div className="field field-inline">
          <label htmlFor="status-filter">Status</label>
          <select id="status-filter" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as ClaimStatus | "")}>
            <option value="">All statuses</option>
            {CLAIM_STATUSES.map((s) => (
              <option key={s} value={s}>
                {CLAIM_STATUS_META[s].label}
              </option>
            ))}
          </select>
        </div>
      </div>
      {page.state.status === "error" && <ErrorState error={page.state.error} onRetry={() => void load(statusFilter, null)} />}
      {loading && items.length === 0 && <LoadingState label="Loading claims…" />}
      {page.state.status === "success" && items.length === 0 && (
        <EmptyState title="No claims to show">{statusFilter ? "No claims have this status." : "You have no claims on record."}</EmptyState>
      )}
      {items.length > 0 && (
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Your claims, newest first</caption>
            <thead>
              <tr>
                <th scope="col">Claim number</th>
                <th scope="col">Status</th>
                <th scope="col">Submitted</th>
                <th scope="col">Last updated</th>
                <th scope="col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.claim_number}>
                  <td className="mono" data-label="Claim">{c.claim_number}</td>
                  <td data-label="Status">
                    <MetaBadge meta={CLAIM_STATUS_META[c.status]} />
                  </td>
                  <td data-label="Submitted">{formatDate(c.submission_date)}</td>
                  <td data-label="Updated">{formatDateTime(c.last_status_change_at)}</td>
                  <td>
                    <Button variant="ghost" className="btn-sm" onClick={() => onSelect(c.claim_number)}>
                      View<span className="sr-only"> claim {c.claim_number}</span>
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {cursor && (
        <Button variant="secondary" busy={loading} onClick={() => void load(statusFilter, cursor)}>
          Load more
        </Button>
      )}
    </section>
  );
}

export function ClaimsPage() {
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <>
      <PageHeader
        title="My claims"
        description="Claim statuses come directly from the claim records. IHSA doesn't change or decide claims."
      />
      <div className="two-col">
        <ClaimLookup initial={selected} />
        <ClaimList onSelect={setSelected} />
      </div>
    </>
  );
}
