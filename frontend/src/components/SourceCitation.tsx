// Renders only citations supplied by the backend; it never invents sources.
import type { Citation } from "../types/api";
import { formatDate } from "../lib/format";

export function SourceCitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <details className="citations" open>
      <summary>Sources ({citations.length})</summary>
      <ol>
        {citations.map((c) => (
          <li key={c.marker} id={`source-${c.marker}`}>
            <SourceCitation citation={c} />
          </li>
        ))}
      </ol>
    </details>
  );
}

export function SourceCitation({ citation }: { citation: Citation }) {
  const pages =
    citation.page_start === null
      ? null
      : citation.page_end && citation.page_end !== citation.page_start
        ? `pp. ${citation.page_start}–${citation.page_end}`
        : `p. ${citation.page_start}`;
  return (
    <article className="citation" aria-label={`Source ${citation.marker}: ${citation.document_title}`}>
      <p className="citation-title">
        <span className="citation-marker">[{citation.marker}]</span> {citation.document_title}{" "}
        <span className="muted">v{citation.document_version}</span>
      </p>
      <p className="citation-meta">
        {citation.section_heading && <span>{citation.section_heading}</span>}
        {pages && <span>{pages}</span>}
        <span>{citation.effective_date ? `Effective ${formatDate(citation.effective_date)}` : "Effective date not stated"}</span>
      </p>
      {/* Plain text rendering: excerpts are untrusted document content. */}
      <blockquote className="citation-excerpt">{citation.excerpt}</blockquote>
    </article>
  );
}
