# Knowledge Base Guide

The knowledge base is a **trusted, administrator-controlled** corpus of synthetic documents. Users can't add documents to it; uploads (Phase 6) are a separate, untrusted path.

## Corpus

`backend/data/knowledge/` has 14 synthetic documents (13 Markdown, 1 two-page PDF) and `manifest.json`.

| document_key | Version(s) | Type | Audience | Notes |
|---|---|---|---|---|
| general-member-faq | 1.0 | FAQ | all | |
| gold-plan-benefit-guide | 1.0 | BENEFIT_GUIDE | all | scoped to `SYN-PLAN-GOLD-01` (members of other plans can't retrieve it) |
| bronze-plan-benefit-guide | 1.0 | BENEFIT_GUIDE | all | scoped to `SYN-PLAN-BRONZE-01` |
| claims-status-guide | 1.1 | CLAIMS_GUIDE | all | |
| claims-appeal-process | 1.0 | PROCESS_MANUAL | all | no effective date (stays null) |
| pa-imaging-guide | 1.0 (SUPERSEDED), 2.0 (ACTIVE) | PA_REQUIREMENTS | all | v1 says 4 weeks, v2 says 6 weeks: tests version handling |
| pa-physical-therapy-guide | 1.0 | PA_REQUIREMENTS | all | |
| claim-documentation-requirements | 1.0 | PROCESS_MANUAL | all | |
| support-case-process | 1.0 | SUPPORT_PROCEDURE | all | |
| support-agent-procedures | 1.0 | SUPPORT_PROCEDURE | SUPPORT_INTERNAL only | hidden from members and providers |
| virtual-care-faq / virtual-care-policy-summary | 1.0 / 1.0 | FAQ / BENEFIT_GUIDE | all | **deliberately contradict each other** ($0 vs $15/$30) |
| provider-admin-faq (PDF) | 1.0 | FAQ | PROVIDER, SUPPORT_INTERNAL | regenerate with `python -m scripts.build_sample_pdf` |

Every file starts with a "SYNTHETIC DEMONSTRATION DOCUMENT" notice. None describes a real insurer or any Evernorth policy.

## Supported formats

- `.md` (UTF-8): headings become `section_heading`.
- `.txt` (UTF-8).
- `.pdf` with a text layer: page numbers are kept.

Rejected with a recorded error code:

| Problem | Code |
|---|---|
| Other file types | `UNSUPPORTED_FILE_TYPE` |
| Not valid UTF-8 | `NOT_UTF8` |
| Empty or near-empty text | `EMPTY_DOCUMENT` |
| Scanned PDF without text | `NO_TEXT_LAYER` (OCR is Phase 6) |
| Corrupt PDF | `PDF_PARSE_ERROR` |
| Encrypted PDF | `PDF_ENCRYPTED` |
| File over 5 MB | `FILE_TOO_LARGE` |
| File not in the corpus folder | `FILE_NOT_FOUND_IN_CORPUS` |
| Unknown plan code | `UNKNOWN_PLAN_CODE` |
| Embedding model failure | `EMBEDDING_FAILED` |

## Manifest fields (required unless noted)

```json
{"file": "pa-imaging-guide-v2.md", "document_key": "pa-imaging-guide", "title": "Synthetic Imaging Prior Authorization Guide",
 "version": "2.0", "document_type": "PA_REQUIREMENTS", "audience": ["MEMBER", "PROVIDER", "SUPPORT_INTERNAL"],
 "plan_code": null, "effective_date": "2026-01-01"}
```

- `file` must be a bare file name inside the corpus folder. Paths and `..` are rejected, so nothing outside the folder can be ingested.
- `version` is a dotted number. The highest ingested version of a `document_key` is ACTIVE.
- `document_type` is one of `BENEFIT_GUIDE`, `FAQ`, `PROCESS_MANUAL`, `PA_REQUIREMENTS`, `CLAIMS_GUIDE`, `SUPPORT_PROCEDURE`.
- `audience` is a subset of `MEMBER`, `PROVIDER`, `SUPPORT_INTERNAL`. Retrieval only returns documents whose audience includes the caller's role (members: MEMBER; providers: + PROVIDER; agents and admins: all three).
- `plan_code` (optional) limits a member's retrieval to their own plan.
- `effective_date` (optional) stays null when the source states none; it is never guessed.

## Ingest

```powershell
cd backend
python -m scripts.ingest_knowledge_base
```

It prints counts: inserted, updated, skipped, failed, superseded, retired, and chunks written. It exits with 1 if any document failed. The first run downloads the embedding model (about 130 MB) into `EMBEDDING_CACHE_DIR`.

## Update and re-index behavior

| Change | Result |
|---|---|
| Nothing changed | `skipped` (SHA-256, embedding model, chunking config and metadata all match) |
| File content edited, same version | `updated`: old chunks deleted, new chunks embedded, in one savepoint |
| Chunk size/overlap or chunker version changed | Every document `updated` |
| Embedding model changed | Every document re-embedded. Vectors from different models are never compared |
| New version added to the manifest | New row. The previous version becomes `SUPERSEDED`: kept for past citations, never used as evidence |
| Entry removed from the manifest | Document becomes `RETIRED` (not retrieved) |
| File fails to process | `INGESTION_FAILED` with a code, chunks removed, `RETIRED`. A broken update never leaves stale content searchable |

Each document is processed in its own savepoint, and the whole run is a single transaction. Interrupting it rolls everything back, so re-running is the recovery.

## Add or remove a document safely

1. Put the file in `data/knowledge/` and add a manifest entry (synthetic content only).
2. Run the ingestion command and check its counts.
3. Ask a question in the chat, or run `python -m scripts.evaluate_rag`.
4. To change a document's rules, add a new `version` rather than editing the old file. That keeps history traceable.
5. To remove a document, delete its manifest entry and re-run. It is retired, not hard-deleted, because past answers may cite it.

## Inspect results

```sql
SELECT document_key, version, lifecycle_status, ingestion_status, ingestion_error_code, chunk_count, embedding_model
FROM knowledge_documents ORDER BY document_key, version;
```

Each run is also recorded as a `KNOWLEDGE_INGESTION_RUN` audit event with counts.
