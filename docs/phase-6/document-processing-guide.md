# Phase 6 — Document Processing Guide

How to configure, run and troubleshoot document upload, analysis and readiness checks. The design is in [document-ai-architecture.md](document-ai-architecture.md). Synthetic documents only.

## 1. Supported files and limits

| Setting (`backend/.env`) | Default | Meaning |
|---|---|---|
| `MAX_UPLOAD_BYTES` | 10485760 | Larger uploads → 413 (checked before the body is read) |
| `MAX_PDF_PAGES` | 20 | More pages → 422 `MALFORMED_FILE` / `PAGE_LIMIT_EXCEEDED` |
| `MAX_IMAGE_MEGAPIXELS` | 25 | Larger images → 422 / `IMAGE_TOO_LARGE` |
| `JOB_TIMEOUT_SECONDS` | 120 | Whole-job deadline → `FAILED` / `TIMEOUT` |
| `MAX_CONCURRENT_DOCUMENT_JOBS` | 1 | In-process worker slots |
| `DOCUMENT_UPLOADS_PER_HOUR`, `DOCUMENT_ANALYSES_PER_HOUR` | 30 | Per-user limits → 429 |
| `DOCUMENT_RETENTION_DAYS` | 30 | Provisional; sets `expires_at` |
| `DOCUMENT_STORAGE_DIR` | `.local/uploads` | Private directory (git-ignored); must not be inside a served directory |
| `OCR_ENGINE` | `tesseract` | `tesseract` or `disabled` |
| `OCR_TESSERACT_PATH` | `tesseract` | Executable on PATH, or an absolute path |
| `OCR_LANGUAGES` | `eng` | Allowlisted pattern `eng` / `eng+deu` |
| `OCR_DPI`, `OCR_PAGE_TIMEOUT_SECONDS` | 300, 30 | Rendering and per-page limit |
| `OCR_MIN_TEXT_CHARS_PER_PAGE` | 50 | Pages with less native text go to OCR |
| `OCR_MIN_WORD_CONFIDENCE`, `EXTRACTION_LOW_CONFIDENCE` | 60, 0.70 | Provisional thresholds |

Formats: `.pdf` (`application/pdf`), `.png` (`image/png`), `.jpg`/`.jpeg` (`image/jpeg`). The extension, the declared type and the file signature must agree. Encrypted PDFs are rejected.

## 2. Installing OCR (not installed in the development environment used for Phase 6)

1. Install Tesseract with the English language data. On Windows, for example, use the UB Mannheim build: `winget install UB-Mannheim.TesseractOCR`.
2. Set `OCR_TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe` in `backend/.env` and restart the API.
3. Check it works: `python -m scripts.evaluate_documents`. The report header should show `available: True`, and the scanned samples are then scored.

Without OCR:
- a page with no text layer is reported `UNREADABLE` (`OCR_UNAVAILABLE`);
- a fully scanned file's job is `FAILED` / `OCR_FAILED` ("…the OCR engine is not available");
- fields that might be on unreadable pages are `ILLEGIBLE`, never `ABSENT`.

## 3. API (base `/api/v1`, bearer token)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/documents -H "Authorization: Bearer $TOKEN" -F "file=@data/samples/documents/pa_request_mri_incomplete.pdf;type=application/pdf" -F "declared_purpose=PA_REQUEST"
```

| Call | Permission | Result |
|---|---|---|
| `POST /documents` (multipart `file`, optional `declared_purpose`) | `documents:upload` (member, provider) | 201 document (`latest_job: null`, i.e. **not analyzed**); 200 if you already uploaded the identical file; 411/413/415/422/429 |
| `GET /documents` | `documents:read:own` | Your documents, newest first, with latest job status |
| `GET /documents/{id}` | owner | Metadata + latest job: status, pages, warnings, fields (raw/normalized value, status, message, page, method, OCR confidence) |
| `POST /documents/{id}/analyze` | `documents:upload` + owner | 202 `{job_id, status: "QUEUED"}`; 409 `JOB_ALREADY_RUNNING` (job ID in `details`) |
| `GET /authorization/requirement-sets` | `requirements:read` | Active fictional sets |
| `POST /authorization/readiness` `{procedure_code, document_ids[1–10], provider_note?}` | `readiness:create` (provider) | 201 checklist; 404 `REQUIREMENT_SET_NOT_FOUND` / `REQUIREMENTS_SOURCE_UNAVAILABLE` / document not yours; 409 `DOCUMENT_NOT_ANALYZED`; 422 |
| `GET /authorization/checklists`, `GET /authorization/checklists/{id}` | `readiness:read:own` | Your checklists |

**Polling:** after `analyze`, poll `GET /documents/{id}` until `latest_job.status` is no longer `QUEUED`/`RUNNING`. The UI polls every 2 s for up to 150 s.

**Retry:** call `analyze` again. Every run is a new job; earlier results are kept. If a job was interrupted (for example, the API restarted), the next `analyze` closes it as `FAILED`/`TIMEOUT` and starts a new one.

## 4. In the app

- **Documents** (members and providers): choose a file → **Upload** (stored, not analyzed) → **Analyze document**. The page shows each page's reading method and result, the field table (value in the document, normalized value, check status and message, source page, method, OCR confidence) and warnings.
- **PA readiness** (providers): choose a requirement set, tick analyzed documents (failed or unfinished ones aren't selectable), optionally add a note, then **Create checklist**. The checklist shows counts, each item's status with its explanation, evidence and requirement source, the draft reviewer summary, and the "Not an authorization decision" notice.
- From the assistant, "What documents are required for a lumbar MRI prior authorization?" now offers **Check my documents against these** to providers.

## 5. Synthetic samples and evaluation

```bash
python -m scripts.build_sample_documents
```

```bash
python -m scripts.evaluate_documents
```

The first command writes 13 documents and `expected.json` (ground truth: document type, field statuses and values, and 10 checklist scenarios) to `backend/data/samples/documents/`. The second writes `data/evaluation/results/document_eval_v1.{md,json}`.

| Sample | Purpose |
|---|---|
| `pa_request_mri_complete.pdf` + `referral_letter_mri.pdf` | Complete MRI packet |
| `pa_request_mri_incomplete.pdf` | NPI and therapy duration omitted → MISSING |
| `pa_request_mri_conflict.pdf` | Two member numbers, impossible date → NEEDS_MANUAL_REVIEW |
| `pa_request_mri_scanned.png` / `.pdf` | Need OCR |
| `pa_request_mri_mixed.pdf` | Page 2 scanned (holds the NPI) → UNREADABLE without OCR |
| `pt_request_form.pdf`, `pt_referral_letter(_late).pdf`, `clinical_note_summary.pdf` | PT set, 30-day window |
| `unrecognized_letter.pdf` | Unknown type → manual review for "referral included" |
| `pa_request_mri_injection.pdf` | Embedded instructions aimed at the AI |

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 415 on a valid-looking PDF | The browser/client sent a different MIME type, or the file isn't really a PDF (signature check) |
| 422 `ENCRYPTED_PDF` | Remove the password; encrypted PDFs aren't supported |
| 411 `LENGTH_REQUIRED` | The client used chunked upload; send `Content-Length` (browsers and curl do) |
| Job `FAILED` / `OCR_FAILED` | Scanned file and no OCR engine. See §2 |
| Fields `ILLEGIBLE` with "page(s) N could not be fully read" | That page needs OCR or is low quality |
| 409 `JOB_ALREADY_RUNNING` | Wait for the current job (poll) |
| 409 `DOCUMENT_NOT_ANALYZED` | Analyze each selected document first; failed jobs can't be used |
| 404 `REQUIREMENTS_SOURCE_UNAVAILABLE` | The set's source knowledge document isn't ingested/active. Run `python -m scripts.ingest_knowledge_base` |
| Uploads disappear after 30 days | `expires_at` (provisional retention) |
