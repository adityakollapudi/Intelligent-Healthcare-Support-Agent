// Phase 6 UI: upload vs analysis, polling, field review, readiness checklist rendering and safety.
import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { isChecklistDetail } from "../lib/validators";
import { apiError, authRoutes, json, mockApi } from "../test/fetch-mock";
import { renderSignedIn } from "../test/render";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const DOC = {
  document_id: "d-1",
  original_filename: "pa_form.pdf",
  mime_type: "application/pdf",
  size_bytes: 3200,
  page_count: 1,
  declared_purpose: null,
  created_at: "2026-10-25T12:00:00Z",
  expires_at: "2026-11-24T12:00:00Z",
  latest_job: null,
  data_environment: "SYNTHETIC_PROTOTYPE",
};
const JOB = {
  job_id: "j-1",
  status: "COMPLETED_WITH_WARNINGS",
  detected_document_type: "PA_REQUEST_FORM",
  pages_text_layer: 1,
  pages_ocr: 1,
  ocr_mean_confidence: 88.5,
  warning_count: 2,
  error_code: null,
  error_detail: null,
  created_at: "2026-10-25T12:00:01Z",
  started_at: "2026-10-25T12:00:01Z",
  completed_at: "2026-10-25T12:00:02Z",
  extraction_schema_version: "1.0",
  pipeline_version: "6.0.0",
  warnings: ["PAGE_2_OCR_LOW_CONFIDENCE", "FIELD_ordering_provider_npi_ABSENT"],
  pages: [
    { page_number: 1, method: "TEXT_LAYER", status: "OK", char_count: 600, ocr_confidence: null, warning: null },
    { page_number: 2, method: "OCR", status: "LOW_QUALITY", char_count: 80, ocr_confidence: 55.2, warning: "OCR_LOW_CONFIDENCE" },
  ],
  fields: [
    { field_id: "f1", field_name: "member_number", raw_value: "SYN-M-000001", normalized_value: "SYN-M-000001", validation_status: "VALID", validation_message: null, source_page: 1, extraction_method: "TEXT_LAYER", confidence: null },
    { field_id: "f2", field_name: "requested_service_date", raw_value: "11/04/2026", normalized_value: "2026-11-04", validation_status: "VALID", validation_message: null, source_page: 1, extraction_method: "TEXT_LAYER", confidence: null },
    { field_id: "f3", field_name: "ordering_provider_npi", raw_value: null, normalized_value: null, validation_status: "ABSENT", validation_message: "Not found in document", source_page: null, extraction_method: null, confidence: null },
    { field_id: "f4", field_name: "facility_name", raw_value: null, normalized_value: null, validation_status: "ILLEGIBLE", validation_message: "Not found on readable pages; page(s) 2 could not be fully read", source_page: null, extraction_method: null, confidence: null },
  ],
};
const CHECKLIST = {
  checklist_id: "c-1",
  procedure_code: "SYN-PROC-MRI-LUMBAR",
  display_name: "Lumbar spine MRI (fictional requirement set)",
  requirement_set_version: "2.0",
  requirement_source_document: "Synthetic Imaging Prior Authorization Guide v2.0",
  rules_version: "1.0",
  readiness_status: "DOCUMENTATION_INCOMPLETE",
  review_state: "NOT_SUBMITTED",
  counts: { SATISFIED: 1, MISSING: 1, UNREADABLE: 1, NEEDS_MANUAL_REVIEW: 1 },
  documents: [{ document_id: "d-1", original_filename: "pa_form.pdf", job_id: "j-1", detected_document_type: "PA_REQUEST_FORM" }],
  items: [
    { requirement_code: "REQ-MRI-01", description: "Requested service date present", rule_type: "FIELD_PRESENT", is_mandatory: true, item_status: "SATISFIED", explanation: "requested_service_date = 2026-11-04 (VALID) in pa_form.pdf p.1", evidence: [{ field_id: "f2", document_id: "d-1", field_name: "requested_service_date", validation_status: "VALID", normalized_value: "2026-11-04", source_page: 1 }], requirement_source: { document_id: "k", document_title: "Synthetic Imaging Prior Authorization Guide", document_version: "2.0", effective_date: null, section_heading: "Required documentation", page_start: null, chunk_id: "ch", excerpt: "x" } },
    { requirement_code: "REQ-MRI-02", description: "Ordering provider identifier present", rule_type: "FIELD_PATTERN", is_mandatory: true, item_status: "MISSING", explanation: "Field ordering_provider_npi ABSENT in all submitted documents", evidence: [], requirement_source: null },
    { requirement_code: "REQ-MRI-03", description: "Conservative therapy duration is documented", rule_type: "FIELD_PRESENT", is_mandatory: true, item_status: "UNREADABLE", explanation: "conservative_therapy_duration could not be read reliably", evidence: [], requirement_source: null },
    { requirement_code: "REQ-MRI-06", description: "Supporting rationale reviewed by authorized staff", rule_type: "MANUAL_ONLY", is_mandatory: true, item_status: "NEEDS_MANUAL_REVIEW", explanation: "Rule type MANUAL_ONLY: requires human verification", evidence: [], requirement_source: null },
  ],
  warnings: [],
  provider_note: null,
  reviewer_summary: "DRAFT — Documentation readiness summary\nResult: DOCUMENTATION_INCOMPLETE — 1 satisfied, 1 missing, 1 unreadable, 1 need manual review",
  disclaimer: "This checklist reviews documentation completeness only. It is not an authorization approval, denial, medical-necessity determination, or guarantee of coverage.",
  created_at: "2026-10-25T12:01:00Z",
  data_environment: "SYNTHETIC_PROTOTYPE",
};

const pdf = () => new File(["%PDF-1.7 synthetic"], "pa_form.pdf", { type: "application/pdf" });

describe("documents screen", () => {
  it("uploads through the API and says the file isn't analyzed yet", async () => {
    const { calls } = mockApi({
      ...authRoutes("PROVIDER"),
      "GET /documents": () => json(200, { items: [], next_cursor: null }),
      "POST /documents": () => json(201, DOC),
      "GET /documents/d-1": () => json(200, DOC),
    });
    const { navigate, user } = await renderSignedIn();
    navigate("/documents");
    await user.upload(await screen.findByLabelText("Choose file"), pdf());
    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText(/was stored. It hasn't been analyzed yet/)).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST" && c.path === "/documents")!;
    expect(post.headers.get("Content-Type")).toBeNull(); // the browser sets the multipart boundary
    expect(await screen.findByRole("button", { name: "Analyze document" })).toBeInTheDocument();
    expect(screen.queryByText("Analyzed")).not.toBeInTheDocument();
  });

  it("shows a server rejection without claiming the file was stored", async () => {
    mockApi({
      ...authRoutes("PROVIDER"),
      "GET /documents": () => json(200, { items: [], next_cursor: null }),
      "POST /documents": () => apiError(415, "UNSUPPORTED_FILE_TYPE", "Only PDF, PNG and JPEG files are supported."),
    });
    const { navigate, user } = await renderSignedIn();
    navigate("/documents");
    await user.upload(await screen.findByLabelText("Choose file"), pdf());
    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText(/was stored/)).not.toBeInTheDocument();
  });

  it("polls a running analysis and then shows fields, pages and warnings from the backend", async () => {
    let gets = 0;
    const { calls } = mockApi({
      ...authRoutes("PROVIDER"),
      "GET /documents": () => json(200, { items: [{ ...DOC, latest_job: null }], next_cursor: null }),
      "POST /documents/d-1/analyze": () => json(202, { job_id: "j-1", status: "QUEUED", created_at: JOB.created_at }),
      "GET /documents/d-1": () => {
        gets += 1;
        if (gets === 1) return json(200, DOC);
        if (gets === 2) return json(200, { ...DOC, latest_job: { ...JOB, status: "RUNNING", fields: [], pages: [], warnings: [] } });
        return json(200, { ...DOC, latest_job: JOB });
      },
    });
    const { navigate, user } = await renderSignedIn();
    navigate("/documents?doc=d-1");
    await user.click(await screen.findByRole("button", { name: "Analyze document" }));
    expect(await screen.findByText(/Checking again every few seconds/)).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: "Extracted fields" }, { timeout: 5000 });
    expect(within(table).getByText("SYN-M-000001")).toBeInTheDocument();
    expect(within(table).getByText("→ 2026-11-04")).toBeInTheDocument();
    expect(within(table).getByText("Not found")).toBeInTheDocument(); // ABSENT
    expect(within(table).getByText("Not readable")).toBeInTheDocument(); // ILLEGIBLE is not shown as missing
    expect(screen.getByText("Analyzed with warnings")).toBeInTheDocument();
    expect(within(screen.getByRole("table", { name: "Pages" })).getByText(/Low OCR quality/)).toBeInTheDocument();
    expect(calls.filter((c) => c.path === "/documents/d-1/analyze")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Use in a readiness check" })).toHaveAttribute("href", "/readiness?doc=d-1");
  });

  it("reports a failed analysis without inventing results", async () => {
    mockApi({
      ...authRoutes("MEMBER"),
      "GET /documents": () => json(200, { items: [], next_cursor: null }),
      "GET /documents/d-1": () =>
        json(200, { ...DOC, latest_job: { ...JOB, status: "FAILED", error_code: "OCR_FAILED", error_detail: "No text could be read: this file needs OCR, and the OCR engine is not available.", fields: [], pages: [], warnings: [] } }),
    });
    const { navigate } = await renderSignedIn();
    navigate("/documents?doc=d-1");
    expect(await screen.findByText(/OCR engine is not available/)).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Extracted fields" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Use in a readiness check" })).not.toBeInTheDocument();
  });
});

describe("readiness screen", () => {
  const routes = {
    ...authRoutes("PROVIDER"),
    "GET /authorization/requirement-sets": () =>
      json(200, [{ procedure_code: "SYN-PROC-MRI-LUMBAR", display_name: "Lumbar spine MRI (fictional requirement set)", version: "2.0" }]),
    "GET /documents": () =>
      json(200, { items: [{ ...DOC, latest_job: JOB }, { ...DOC, document_id: "d-2", original_filename: "scan.png", latest_job: { ...JOB, status: "FAILED" } }], next_cursor: null }),
    "GET /authorization/checklists": () => json(200, { items: [], next_cursor: null }),
  };

  it("creates a checklist from the backend and renders all four statuses with the disclaimer", async () => {
    const { calls } = mockApi({
      ...routes,
      "POST /authorization/readiness": () => json(201, CHECKLIST),
      "GET /authorization/checklists/c-1": () => json(200, CHECKLIST),
    });
    const { navigate, user } = await renderSignedIn();
    navigate("/readiness?doc=d-1");
    await user.selectOptions(await screen.findByLabelText("Requirement set"), "SYN-PROC-MRI-LUMBAR");
    expect(await screen.findByRole("checkbox", { name: /pa_form.pdf/ })).toBeChecked();
    expect(screen.queryByRole("checkbox", { name: /scan.png/ })).not.toBeInTheDocument(); // failed analysis
    await user.click(screen.getByRole("button", { name: "Create checklist" }));
    const report = await screen.findByRole("region", { name: "Readiness checklist" });
    expect(within(report).getByText("Not an authorization decision")).toBeInTheDocument();
    expect(within(report).getByText("Documentation incomplete")).toBeInTheDocument();
    const items = within(report).getByRole("list", { name: "Checklist items" });
    for (const label of ["Satisfied", "Missing", "Unreadable", "Needs manual review"]) {
      expect(within(items).getByText(label)).toBeInTheDocument();
    }
    expect(within(report).getByText(/Evidence: requested service date VALID in pa_form.pdf p.1/i)).toBeInTheDocument();
    expect(within(report).getByText(/1 satisfied, 1 missing, 1 unreadable/)).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST" && c.path === "/authorization/readiness")!;
    expect(post.body).toEqual({ procedure_code: "SYN-PROC-MRI-LUMBAR", document_ids: ["d-1"], provider_note: null });
  });

  it("rejects a checklist whose counts don't match its items", () => {
    expect(isChecklistDetail(CHECKLIST)).toBe(true);
    expect(isChecklistDetail({ ...CHECKLIST, counts: { ...CHECKLIST.counts, SATISFIED: 5 } })).toBe(false);
    expect(isChecklistDetail({ ...CHECKLIST, items: [{ ...CHECKLIST.items[0], item_status: "APPROVED" }] })).toBe(false);
  });

  it("shows a 409 for unanalyzed documents as an error, not a checklist", async () => {
    mockApi({ ...routes, "POST /authorization/readiness": () => apiError(409, "DOCUMENT_NOT_ANALYZED", "Every document must have a finished analysis.") });
    const { navigate, user } = await renderSignedIn();
    navigate("/readiness?doc=d-1");
    await user.selectOptions(await screen.findByLabelText("Requirement set"), "SYN-PROC-MRI-LUMBAR");
    await user.click(screen.getByRole("button", { name: "Create checklist" }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.queryByRole("region", { name: "Readiness checklist" })).not.toBeInTheDocument();
  });

  it("members can upload documents but don't get the readiness screen", async () => {
    mockApi(authRoutes("MEMBER"));
    const { navigate } = await renderSignedIn();
    navigate("/readiness");
    expect(await screen.findByRole("heading", { level: 1 })).not.toHaveTextContent("Prior authorization readiness");
  });
});
