// Phase 6 document workspace: upload (POST /documents), list, analysis (POST /documents/{id}/analyze)
// and results polled from GET /documents/{id}. Everything shown comes from the backend; nothing here
// computes a field status, and upload success is never presented as analysis success.
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { FileDropzone, type FileCheck } from "../components/FileDropzone";
import { FIELD_STATUS_META, JOB_STATUS_META, MetaBadge } from "../components/status";
import { Alert, Button, EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui";
import { useSession } from "../features/auth/session";
import { useRequest } from "../hooks/useRequest";
import { formatBytes, formatDateTime, humanize } from "../lib/format";
import { documentsService } from "../services";
import type { DeclaredPurpose, DocumentDetail, DocumentField, DocumentText, JobDetail } from "../types/api";

const POLL_MS = 2000;
const POLL_LIMIT_MS = 150_000; // backend job timeout (120 s) plus margin
const ACTIVE = new Set(["QUEUED", "RUNNING"]);

const PAGE_STATUS_TEXT: Record<string, string> = {
  OK: "Read",
  EMPTY: "Blank page",
  PARTIAL: "Partly read",
  LOW_QUALITY: "Low OCR quality",
  UNREADABLE: "Could not be read",
};

const PAGE_WARNING_TEXT: Record<string, string> = {
  OCR_HANDWRITING_NEEDS_CHECK: "Handwriting: please check the text below",
};

function UnclearText({ text, unclear }: { text: string; unclear: string[] }) {
  const wanted = new Set(unclear);
  return (
    <p className="message-text read-text">
      {/* Plain text rendering: document content is never interpreted as HTML. */}
      {text.split(/(\s+)/).map((part, index) =>
        wanted.has(part.toLowerCase()) ? (
          <mark key={index} title="The system wasn't sure of this word">{part}</mark>
        ) : (
          part
        ),
      )}
    </p>
  );
}

function ReadTextPages({ pages }: { pages: DocumentText["pages"] }) {
  const handwritten = pages.some((p) => p.handwritten);
  const unclear = pages.some((p) => p.unclear_words.length > 0);
  if (!pages.some((p) => p.text)) return <p className="muted">No text could be read from this document.</p>;
  return (
    <>
      <p className="muted small">
        Compare this with your original document.
        {handwritten && " It includes handwriting, which the system can misread, even when it seems confident."}
        {unclear && " Highlighted words were especially unclear."}
      </p>
      {pages.map((p) => (
        <section key={p.page_number} className="read-page" aria-label={`Page ${p.page_number}`}>
          {pages.length > 1 && <h4>Page {p.page_number}</h4>}
          {p.text ? <UnclearText text={p.text} unclear={p.unclear_words} /> : <p className="muted">Nothing could be read on this page.</p>}
        </section>
      ))}
    </>
  );
}

function ReadText({ documentId, jobId }: { documentId: string; jobId: string }) {
  const text = useRequest((signal) => documentsService.text(documentId, signal));
  useEffect(() => {
    void text.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- read again after each analysis
  }, [documentId, jobId]);
  return (
    <section className="section" aria-label="What we read">
      <h3>What we read from your document</h3>
      {text.state.status === "loading" && <LoadingState label="Reading your document. Handwriting can take up to a minute…" />}
      {text.state.status === "error" && <ErrorState error={text.state.error} onRetry={() => void text.run()} />}
      {text.state.status === "success" && <ReadTextPages pages={text.state.data.pages} />}
    </section>
  );
}

function FieldValue({ field }: { field: DocumentField }) {
  if (field.raw_value === null) {
    return <span className="muted">{field.validation_status === "ABSENT" ? "Not found" : "Not readable"}</span>;
  }
  return (
    <>
      <span className="mono">{field.raw_value}</span>
      {field.normalized_value && field.normalized_value !== field.raw_value && (
        <span className="muted small"> → {field.normalized_value}</span>
      )}
    </>
  );
}

export function FieldTable({ fields }: { fields: DocumentField[] }) {
  if (fields.length === 0) {
    return <p className="muted">This isn't a form with set fields, so no fields were picked out.</p>;
  }
  return (
    <div className="table-wrap">
      <table aria-label="Extracted fields">
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Value in document</th>
            <th scope="col">Check</th>
            <th scope="col">Source</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((f) => (
            <tr key={f.field_id}>
              <td>{humanize(f.field_name)}</td>
              <td>
                <FieldValue field={f} />
              </td>
              <td>
                <MetaBadge meta={FIELD_STATUS_META[f.validation_status]} />
                {f.validation_message && <p className="muted small">{f.validation_message}</p>}
              </td>
              <td className="small">
                {f.source_page ? `Page ${f.source_page}` : "—"}
                {f.extraction_method && <span className="muted"> · {f.extraction_method === "OCR" ? "OCR" : "Text"}</span>}
                {f.confidence !== null && <span className="muted"> · OCR {Math.round(f.confidence * 100)}%</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function JobResult({ job, canCheckReadiness, documentId }: { job: JobDetail; canCheckReadiness: boolean; documentId: string }) {
  const meta = JOB_STATUS_META[job.status];
  return (
    <>
      <div className="card-head">
        <MetaBadge meta={meta} />
        {job.detected_document_type && <span className="muted small">Detected type: {humanize(job.detected_document_type)}</span>}
      </div>
      <p className="muted small">{meta.help}</p>
      {job.status === "FAILED" && (
        <Alert tone="danger" title="No results">
          {job.error_detail ?? "The analysis failed."} No fields were extracted, so nothing is reported as present or missing.
        </Alert>
      )}
      {job.pages.length > 0 && (
        <div className="table-wrap">
          <table aria-label="Pages">
            <thead>
              <tr>
                <th scope="col">Page</th>
                <th scope="col">How it was read</th>
                <th scope="col">Result</th>
              </tr>
            </thead>
            <tbody>
              {job.pages.map((p) => (
                <tr key={p.page_number}>
                  <td>{p.page_number}</td>
                  <td>
                    {p.method === "OCR" ? "OCR" : p.method === "TEXT_LAYER" ? "Text layer" : "—"}
                    {p.ocr_confidence !== null && <span className="muted small"> · mean confidence {p.ocr_confidence}</span>}
                  </td>
                  <td>
                    {PAGE_STATUS_TEXT[p.status] ?? p.status}
                    {p.warning && <span className="muted small"> · {PAGE_WARNING_TEXT[p.warning] ?? humanize(p.warning)}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {job.status !== "FAILED" && (
        <>
          <Alert tone="info" title="Check every value">
            Values are copied from the document and checked for format only. They aren't verified as correct, and a
            missing or unreadable value isn't guessed.
          </Alert>
          <ReadText documentId={documentId} jobId={job.job_id} />
          <FieldTable fields={job.fields} />
          {job.warnings.length > 0 && (
            <details className="section">
              <summary>Warnings ({job.warnings.length})</summary>
              <ul className="small">
                {job.warnings.map((w) => (
                  <li key={w} className="mono">
                    {w}
                  </li>
                ))}
              </ul>
            </details>
          )}
          {canCheckReadiness && (
            <Link className="btn btn-secondary" to={`/readiness?doc=${encodeURIComponent(documentId)}`}>
              Use in a readiness check
            </Link>
          )}
        </>
      )}
    </>
  );
}

function DocumentPanel({ documentId, onChanged }: { documentId: string; onChanged: () => void }) {
  const { can } = useSession();
  const detail = useRequest((signal) => documentsService.get(documentId, signal));
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<unknown>(null);
  const [pollExpired, setPollExpired] = useState(false);
  const pollStarted = useRef<number | null>(null);

  useEffect(() => {
    pollStarted.current = null;
    setPollExpired(false);
    void detail.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when another document is selected
  }, [documentId]);

  const doc: DocumentDetail | null = detail.state.status === "success" ? detail.state.data : null;
  const job = doc?.latest_job ?? null;
  const active = Boolean(job && ACTIVE.has(job.status));

  // Poll only while the backend reports a queued/running job, and stop after the job time limit.
  useEffect(() => {
    if (!active) {
      if (pollStarted.current !== null) onChanged();
      pollStarted.current = null;
      return;
    }
    pollStarted.current ??= Date.now();
    if (Date.now() - pollStarted.current > POLL_LIMIT_MS) {
      setPollExpired(true);
      return;
    }
    const timer = setTimeout(() => void detail.refresh(), POLL_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-arm on every new result
  }, [doc]);

  const analyze = async () => {
    setStarting(true);
    setStartError(null);
    try {
      await documentsService.analyze(documentId);
      pollStarted.current = Date.now();
      setPollExpired(false);
      await detail.refresh();
    } catch (err) {
      setStartError(err);
    } finally {
      setStarting(false);
    }
  };

  if (detail.state.status === "loading" && !doc) return <LoadingState label="Loading document…" />;
  if (detail.state.status === "error") return <ErrorState error={detail.state.error} onRetry={() => void detail.run()} />;
  if (!doc) return null;

  return (
    <section className="card section" aria-label="Document analysis">
      <div className="card-head">
        <h2>{doc.original_filename}</h2>
        <span className="muted small">
          {formatBytes(doc.size_bytes)} · {doc.page_count} page{doc.page_count === 1 ? "" : "s"} · uploaded{" "}
          {formatDateTime(doc.created_at)}
        </span>
      </div>
      {!job && <p>Stored privately. It hasn't been analyzed yet.</p>}
      {job && active && (
        <p role="status">
          <MetaBadge meta={JOB_STATUS_META[job.status]} /> Checking again every few seconds…
        </p>
      )}
      {pollExpired && (
        <Alert tone="warning" title="Still not finished">
          The analysis is taking longer than expected. Refresh later to see its result.
        </Alert>
      )}
      {job && !active && <JobResult job={job} canCheckReadiness={can("readiness:create")} documentId={doc.document_id} />}
      {Boolean(startError) && <ErrorState error={startError} />}
      {!active && (
        <Button variant={job ? "secondary" : "primary"} busy={starting} onClick={() => void analyze()}>
          {job ? "Analyze again" : "Analyze document"}
        </Button>
      )}
    </section>
  );
}

export function DocumentsPage() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("doc");
  const [file, setFile] = useState<File | null>(null);
  const [check, setCheck] = useState<FileCheck | null>(null);
  const [purpose, setPurpose] = useState<DeclaredPurpose | "">("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<unknown>(null);
  const [uploaded, setUploaded] = useState<string | null>(null);
  const list = useRequest((signal) => documentsService.list(signal));

  useEffect(() => {
    void list.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial load
  }, []);

  const upload = async () => {
    if (!file || !check?.ok) return;
    setUploading(true);
    setUploadError(null);
    try {
      const doc = await documentsService.upload(file, purpose || undefined);
      setUploaded(doc.original_filename);
      setFile(null);
      setCheck(null);
      setParams({ doc: doc.document_id });
      void list.refresh();
    } catch (err) {
      setUploadError(err);
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Documents"
        description="Upload a synthetic sample document, then analyze it to extract and check its fields. Every extracted value must be reviewed by you."
      />
      <section className="section card" aria-labelledby="upload-heading">
        <h2 id="upload-heading">Upload a document</h2>
        <Alert tone="info">Synthetic sample documents only. Don't upload real personal or health information.</Alert>
        <FileDropzone
          onSelect={(f, c) => {
            setFile(f);
            setCheck(c);
            setUploaded(null);
            setUploadError(null);
          }}
        />
        {file && check && (
          <div className="selected-file" aria-live="polite">
            <p>
              <strong>{file.name}</strong> <span className="muted">· {formatBytes(file.size)}</span>
            </p>
            {!check.ok && (
              <Alert tone="danger" title="This file can't be used">
                {check.reason}
              </Alert>
            )}
            <div className="field field-inline">
              <label htmlFor="doc-purpose">Purpose (optional)</label>
              <select id="doc-purpose" value={purpose} onChange={(e) => setPurpose(e.target.value as DeclaredPurpose | "")}>
                <option value="">Not specified</option>
                <option value="PA_REQUEST">Prior authorization request</option>
                <option value="SUPPORTING_DOCUMENT">Supporting document</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
            <div className="row">
              <Button disabled={!check.ok} busy={uploading} onClick={() => void upload()}>
                Upload
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setFile(null);
                  setCheck(null);
                }}
              >
                Remove file
              </Button>
            </div>
          </div>
        )}
        {uploaded && (
          <Alert tone="success" title="Uploaded">
            {uploaded} was stored. It hasn't been analyzed yet.
          </Alert>
        )}
        {Boolean(uploadError) && <ErrorState error={uploadError} />}
      </section>

      {selected && <DocumentPanel key={selected} documentId={selected} onChanged={() => void list.refresh()} />}

      <section className="section" aria-labelledby="docs-heading">
        <h2 id="docs-heading">Your documents</h2>
        {list.state.status === "loading" && <LoadingState label="Loading documents…" />}
        {list.state.status === "error" && <ErrorState error={list.state.error} onRetry={() => void list.run()} />}
        {list.state.status === "success" && list.state.data.items.length === 0 && (
          <EmptyState title="No documents yet">Documents you upload are listed here for 30 days.</EmptyState>
        )}
        {list.state.status === "success" && list.state.data.items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col">Uploaded</th>
                  <th scope="col">Analysis</th>
                </tr>
              </thead>
              <tbody>
                {list.state.data.items.map((d) => (
                  <tr key={d.document_id} aria-current={d.document_id === selected ? "true" : undefined}>
                    <td>
                      <button type="button" className="link-button" onClick={() => setParams({ doc: d.document_id })}>
                        {d.original_filename}
                      </button>
                    </td>
                    <td>{formatDateTime(d.created_at)}</td>
                    <td>{d.latest_job ? <MetaBadge meta={JOB_STATUS_META[d.latest_job.status]} /> : <span className="muted">Not analyzed</span>}</td>
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
