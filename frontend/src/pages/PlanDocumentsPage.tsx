// The documents the assistant answers from, so a customer can check an answer themselves.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Alert, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from "../components/ui";
import { useRequest } from "../hooks/useRequest";
import { formatDate } from "../lib/format";
import { knowledgeService } from "../services";
import type { PlanDocumentDetail } from "../types/api";

function DocumentView({ document, highlight }: { document: PlanDocumentDetail; highlight: string | null }) {
  const [search, setSearch] = useState("");
  const target = useRef<HTMLElement>(null);
  const term = search.trim().toLowerCase();
  const sections = document.sections.filter(
    (s) => !term || s.text.toLowerCase().includes(term) || (s.heading ?? "").toLowerCase().includes(term),
  );

  useEffect(() => {
    target.current?.scrollIntoView?.({ block: "center" });
  }, [document.document_id, highlight]);

  return (
    <article className="plan-document">
      <h2>{document.title}</h2>
      <p className="muted small">
        Version {document.version} ·{" "}
        {document.effective_date ? `Effective ${formatDate(document.effective_date)}` : "Effective date not stated"}
      </p>
      <label className="field">
        <span>Find in this document</span>
        <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} />
      </label>
      {sections.length === 0 && <p className="muted">No section contains that text.</p>}
      {sections.map((s) => {
        const cited = Boolean(highlight && s.chunk_ids.includes(highlight));
        return (
          <section key={s.chunk_ids[0]} ref={cited ? target : undefined} className={`plan-section ${cited ? "plan-section-cited" : ""}`}>
            {s.heading && <h3>{s.heading}</h3>}
            {cited && <p className="small"><strong>The assistant used this section.</strong></p>}
            {/* Plain text rendering: document content is never interpreted as HTML. */}
            <p className="message-text">{s.text}</p>
            {s.page !== null && <p className="muted small">Page {s.page}</p>}
          </section>
        );
      })}
    </article>
  );
}

export function PlanDocumentsPage() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("doc");
  const list = useRequest((signal) => docsList(signal));
  const detail = useRequest((signal, id: string) => knowledgeService.document(id, signal));

  useEffect(() => {
    void list.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once
  }, []);
  useEffect(() => {
    if (selected) void detail.run(selected);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when the selection changes
  }, [selected]);

  const documents = list.state.status === "success" ? list.state.data : null;
  const grouped = useMemo(
    () => ({ mine: documents?.filter((d) => d.is_my_plan) ?? [], other: documents?.filter((d) => !d.is_my_plan) ?? [] }),
    [documents],
  );

  const row = (d: NonNullable<typeof documents>[number]) => (
    <li key={d.document_id}>
      <button
        type="button"
        className={`recent-item ${d.document_id === selected ? "active" : ""}`}
        aria-current={d.document_id === selected ? "true" : undefined}
        onClick={() => setParams({ doc: d.document_id })}
      >
        <span className="recent-title">{d.title}</span>
        {d.is_my_plan && <StatusBadge label="Your plan" tone="info" icon="✓" />}
      </button>
    </li>
  );

  return (
    <div>
      <PageHeader
        title="Plan documents"
        description="These are the documents the assistant answers from. Open one to check an answer for yourself."
      />
      <Alert tone="info" title="Think an answer is wrong?">
        Compare it with the document here. If they don't match, <Link to="/chat">tell the assistant</Link> you want to talk to a person. These are fictional documents for this prototype.
      </Alert>
      {list.state.status === "loading" && <LoadingState />}
      {list.state.status === "error" && <ErrorState error={list.state.error} onRetry={() => void list.run()} />}
      {documents?.length === 0 && <EmptyState title="No documents available" />}
      {documents && documents.length > 0 && (
        <div className="plan-documents">
          <nav aria-label="Documents" className="plan-document-list">
            {grouped.mine.length > 0 && <ul>{grouped.mine.map(row)}</ul>}
            <ul>{grouped.other.map(row)}</ul>
          </nav>
          <div>
            {!selected && <p className="muted">Choose a document to read it.</p>}
            {selected && detail.state.status === "loading" && <LoadingState />}
            {selected && detail.state.status === "error" && <ErrorState error={detail.state.error} onRetry={() => void detail.run(selected)} />}
            {selected && detail.state.status === "success" && (
              <DocumentView key={detail.state.data.document_id} document={detail.state.data} highlight={params.get("chunk")} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const docsList = (signal: AbortSignal) => knowledgeService.documents(signal);
