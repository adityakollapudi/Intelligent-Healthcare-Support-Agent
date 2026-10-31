// Structured tool output shown next to an assistant answer. Everything rendered here came back from a
// backend tool call and passed the response validator; nothing is derived from the answer text.
import { formatDate, formatDateTime, humanize } from "../lib/format";
import type { BenefitsResponse, ChatRecord, DocumentSource, RequirementSet, ToolExecution } from "../types/api";
import { CLAIM_STATUS_META, MetaBadge } from "./status";
import { StatusBadge } from "./ui";

const TOOL_LABELS: Record<string, string> = {
  get_claim_status: "Claim lookup",
  get_plan_benefits: "Plan benefits lookup",
  get_required_documents: "Requirements lookup",
  read_my_documents: "Your uploaded documents",
  check_document_readiness: "Readiness check",
  create_support_case: "Support case preparation",
};

const OK = new Set(["SUCCEEDED", "CONFIRMATION_REQUIRED"]);

export function ToolExecutionList({ executions }: { executions: ToolExecution[] }) {
  if (executions.length === 0) return null;
  return (
    <ul className="tool-runs" aria-label="Lookups performed">
      {executions.map((t, i) => (
        <li key={`${t.tool_name}-${i}`}>
          <StatusBadge
            label={TOOL_LABELS[t.tool_name] ?? humanize(t.tool_name)}
            tone={OK.has(t.result_status) ? "info" : "warning"}
            icon={OK.has(t.result_status) ? "⚙" : "⚠"}
          />
          <span className="muted small">{t.summary}</span>
        </li>
      ))}
    </ul>
  );
}

function DocumentSources({ sources }: { sources: DocumentSource[] }) {
  if (sources.length === 0) return null;
  return (
    <section className="record" aria-label="Uploaded document sources">
      <p className="record-title">From your uploaded documents</p>
      <ul>
        {sources.map((s) => (
          <li key={s.marker}>
            <strong>[{s.marker}]</strong> {s.filename}, page {s.page}
            <p className="muted small">{s.excerpt}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ClaimsRecord({ claims }: { claims: Extract<ChatRecord, { kind: "claims" }>["data"]["claims"] }) {
  if (claims.length === 0) return null;
  return (
    <section className="record" aria-label="Claim records">
      <p className="record-title">Claim records (synthetic)</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Claim</th>
              <th scope="col">Status</th>
              <th scope="col">Service date</th>
              <th scope="col">Last updated</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((c) => (
              <tr key={c.claim_number}>
                <td className="mono">{c.claim_number}</td>
                <td>
                  <MetaBadge meta={CLAIM_STATUS_META[c.status]} />
                </td>
                <td>{formatDate(c.service_date)}</td>
                <td>{formatDateTime(c.last_status_change_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BenefitsRecord({ data }: { data: BenefitsResponse }) {
  return (
    <section className="record" aria-label="Plan benefits">
      <p className="record-title">
        {data.plan_name} <span className="muted mono">{data.plan_code}</span>
      </p>
      <ul className="record-list">
        {data.benefits.map((b) => (
          <li key={`${b.benefit_category}-${b.service_name}`}>
            <strong>{b.service_name}</strong>
            {b.in_network_cost_share && <span> · In network: {b.in_network_cost_share}</span>}
            {b.visit_limit && <span> · Limit: {b.visit_limit}</span>}
            {b.prior_auth_required && <span> · Prior authorization required</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function RequirementsRecord({ data }: { data: RequirementSet }) {
  return (
    <section className="record" aria-label="Documentation requirements">
      <p className="record-title">
        {data.display_name} <span className="muted mono">{data.procedure_code}</span>
      </p>
      <p className="muted small">
        From {data.source_document_title} v{data.source_document_version} (requirement set v{data.version})
      </p>
      <ol className="record-list">
        {data.requirements.map((r) => (
          <li key={r.requirement_code}>
            <span className="mono small">{r.requirement_code}</span> {r.description}
            {!r.is_mandatory && <span className="muted"> (if applicable)</span>}
            {!r.source && <span className="field-error"> Source passage not verified</span>}
          </li>
        ))}
      </ol>
      <p className="muted small">{data.disclaimer}</p>
    </section>
  );
}

export function ToolRecords({ records }: { records: ChatRecord[] }) {
  return (
    <>
      {records.map((r, i) => {
        switch (r.kind) {
          case "document_sources":
            return <DocumentSources key={i} sources={r.data.sources} />;
          case "claims":
            return <ClaimsRecord key={i} claims={r.data.claims} />;
          case "plan_benefits":
            return <BenefitsRecord key={i} data={r.data} />;
          case "requirements":
            return <RequirementsRecord key={i} data={r.data} />;
          default:
            return null; // proposals are rendered as a confirmation action, not a record
        }
      })}
    </>
  );
}
