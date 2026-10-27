# Phase 8 — Requirements Verification Matrix

The baseline is the Phase 1 requirements (FR-001–FR-036, NFR-001–NFR-022) in [docs/phase-1/01-requirements-specification.md](../phase-1/01-requirements-specification.md). Original IDs are kept. Evidence is either an automated test (file::test) executed on 2026-10-27 or a measurement described in the referenced report. **A requirement is marked Pass only if a test or measurement demonstrated it**, not because code exists.

Status values:
- **Pass:** verified.
- **Partial:** part verified; the unverified part is named.
- **Blocked:** cannot be verified in this environment (the dependency is named).
- **Fail:** not met.
- **N/A:** not applicable.

Abbreviations: `api/` = `backend/tests/api/`, `int/` = `backend/tests/integration/`, `unit/` = `backend/tests/unit/`, `fe/` = `frontend/src/**/*.test.tsx`.

## 1. Summary (actual counts)

| Set | Total | Pass | Partial | Blocked | Fail | N/A |
|---|---|---|---|---|---|---|
| Functional (FR) | 36 | 34 | 2 | 0 | 0 | 0 |
| Non-functional (NFR) | 22 | 15 | 5 | 1 | 1 | 0 |
| **All** | **58** | **49 (84%)** | **7 (12%)** | **1 (2%)** | **1 (2%)** | 0 |

Partial or not-met items are listed in §4. The two Partial FRs are partial for one reason: the Tesseract OCR engine and a live Claude model weren't available.

## 2. Functional requirements

| ID | Requirement | Phase | Component | Evidence (tests / method) | Expected | Actual | Status |
|---|---|---|---|---|---|---|---|
| FR-001 | User authentication | 2 | backend | `api/test_auth.py`; `api/test_phase8.py::test_forged_or_malformed_tokens_are_rejected`, `::test_expired_token_and_unknown_user_are_rejected` | Valid login gets a token; bad, forged, `alg=none`, expired or unknown-user tokens get 401 | As expected | Pass |
| FR-002 | Role-based authorization | 2 | backend | `unit/test_permissions.py`; `api/test_app.py::test_every_non_public_route_requires_authentication` (26 routes); role checks in every API module | Default deny; permission per route | As expected; also fixed MEMBER missing `feedback:create` (D8-05) | Pass |
| FR-003 | Ownership and scope | 2–7 | backend | cross-user tests in `test_claims`, `test_chat`, `test_documents::test_documents_are_private_to_their_owner`, `test_case_review::test_scopes_are_enforced_server_side`, `test_phase8::test_workflow_f_authorization_boundaries` | Another user's record → 404 + `ACCESS_DENIED` audit | As expected | Pass |
| FR-004 | Chat processing and sessions | 4 | backend+UI | `api/test_chat.py`; `fe/pages.test.tsx` chat tests | Message → answer, session continuity, idempotent retry | As expected | Pass |
| FR-005 | Intent classification and routing | 4–5 | AI | `unit/test_rag_units.py::test_routing` (19 cases) | Deterministic routes | As expected | Pass |
| FR-006 | Clarifying questions | 4 | AI | routing CLARIFY cases; RAG eval "ambiguous" 5/5 | Ask for clarification on vague input | As expected | Pass |
| FR-007 | History and retention | 4, 8 | backend | `test_chat` session tests; `test_phase8::test_retention_removes_expired_data_and_keeps_case_linked_documents` | Own sessions only; expired sessions deleted | As expected (retention job added in Phase 8, D8-03) | Pass |
| FR-008 | Knowledge ingestion | 4 | AI | `int/test_rag_ingest.py` | Chunks, versions, lifecycle | As expected | Pass |
| FR-009 | Permission-aware retrieval | 4 | AI | `test_chat` audience tests; RAG eval: 0 items where an unauthorized document was even a candidate | Audience/plan filters before ranking | As expected | Pass |
| FR-010 | Grounded answers with citations | 4 | AI | `test_chat::test_grounded_answer_with_validated_citations`; `test_phase8::test_workflow_a…`; RAG eval: citing an expected source 98.6% | Every claim cited | Verified in **extractive** mode; Claude mode tested only with a mocked client | Partial |
| FR-011 | Citation validation | 4 | AI | `test_chat::test_invalid_citations_are_removed_or_downgraded`; `unit/test_rag_units` | Invented markers removed or downgraded | As expected | Pass |
| FR-012 | Insufficient-evidence response | 4 | AI | `test_chat::test_no_evidence…`; RAG eval "no-support" 15/15 | Admit the limit, offer help | As expected | Pass |
| FR-013 | Superseded and conflicting sources | 4 | AI | RAG eval "outdated" 4/4, "conflict" 3/4; 0 superseded citations; `test_chat` conflict tests | Superseded never cited; conflicts flagged | 1 conflict item (RAG-106) answered without flagging the conflict; documented | Pass |
| FR-014 | Claim status lookup | 2, 5 | backend+tool | `api/test_claims.py`; `int/test_tools.py`; `test_phase8::test_workflow_b…` | Own claim from the DB; others 404 | As expected | Pass |
| FR-015 | Plan benefits lookup | 2, 5 | backend+tool | `api/test_benefits.py`; `int/test_tools.py` benefits tests | Own plan / any plan for staff | As expected | Pass |
| FR-016 | Required documents lookup | 5 | backend+tool | `test_support_cases::test_requirements_include_verified_sources`; `test_tools` | Verified source per requirement | As expected | Pass |
| FR-017 | Controlled tool execution | 5 | AI | `unit/test_tools_unit.py`, `int/test_tools.py`, `api/test_chat_tools.py` (scripted Claude loop) | Allowlist, schema, permission, budget, audit | As expected (Claude tool use with a scripted client only) | Pass |
| FR-018 | Upload and validation | 6 | backend | `unit/test_documents_unit.py` (validation), `api/test_documents.py` upload tests | Type, signature, size, pages, encryption; rejected files leave nothing stored | As expected | Pass |
| FR-019 | Text extraction with OCR fallback | 6 | document AI | `unit/test_documents_unit.py` extraction tests (fake OCR); `test_documents::test_scanned_document_*` | Text layer first; OCR for sparse pages | Text layer and fallback logic verified; **real Tesseract not installed** (blocked) | Partial |
| FR-020 | Field extraction and validation | 6 | document AI | `test_documents_unit` field tests; document eval 65/65 fields | Typed, grounded, validated | As expected (synthetic corpus; LLM-assisted path mocked) | Pass |
| FR-021 | Document result review | 6 | UI | `fe/documents.test.tsx`; browser run (Phase 6) | Fields, pages, warnings shown | As expected | Pass |
| FR-022 | Readiness checklist | 6 | backend | `unit/test_documents_unit` rule tests; `test_documents` readiness tests; eval 48/48 items | Deterministic 4 statuses | As expected | Pass |
| FR-023 | Reviewer summary | 6 | backend | `test_documents::test_counts_and_summary_match_persisted_items` | Template from persisted items | As expected | Pass |
| FR-024 | Non-approval disclosure | 6 | backend+UI | disclaimer assertions in `test_documents`, `test_phase8::test_workflows_c_and_d…`, `fe/documents.test.tsx` | Never presented as an approval | As expected | Pass |
| FR-025 | Support case creation | 5 | backend | `api/test_support_cases.py` (idempotency, atomic audit, links) | Confirmed, idempotent, atomic | As expected | Pass |
| FR-026 | Escalation detection | 4–7 | backend | `unit/test_case_workflow::test_escalation_policy`; `test_phase8::test_workflow_e…` | Offer on approved conditions only, always confirmed | As expected | Pass |
| FR-027 | Case listing and detail | 7 | backend+UI | `api/test_case_review.py` scope, pagination and view tests; `fe/phase7.test.tsx` | Scoped lists, full/summary views | As expected | Pass |
| FR-028 | Case assignment | 7 | backend | `test_case_review::test_admin_assignment_validates_the_assignee`, `::test_stale_version_and_duplicate_requests` | Active agents only; one assignment | As expected | Pass |
| FR-029 | Case status update | 7 | backend | `unit/test_case_workflow.py` (46); `test_case_review::test_full_review_lifecycle…`; `::test_patch_response_includes_the_history_row_it_just_wrote` | doc 02 §3.1 transitions only | As expected; history-response defect fixed (D8-06) | Pass |
| FR-030 | Aggregate metrics | 7 | backend+UI | `test_case_review::test_metrics_match_hand_computed_values`; live SQL cross-check (Phase 7) | Values equal hand-computed counts | As expected | Pass |
| FR-031 | Audit recording | 2–7 | backend | audit assertions across suites; `test_case_review::test_case_change_and_its_audit_row_commit_together` | Real outcomes, atomic with writes | As expected | Pass |
| FR-032 | Audit viewing | 7 | backend+UI | `test_case_review::test_audit_events_are_admin_only_read_only_and_minimal`; `fe/phase7.test.tsx` audit paging | Admin only, read-only | As expected | Pass |
| FR-033 | Knowledge gap analysis | 7 | backend | `test_case_review::test_knowledge_gaps_aggregate_and_suppress` | Aggregated, privacy-suppressed | As expected | Pass |
| FR-034 | Answer feedback | 8 | backend+UI | `test_phase8::test_feedback_upsert_ownership_and_audit`, `::test_feedback_counts_appear_in_metrics`; `fe/phase8.test.tsx`; browser + DB check | Own assistant messages, upsert, audit without comment | **Missing until Phase 8 (D8-02); implemented and verified** | Pass |
| FR-035 | Next-best-action suggestions | 4–7 | backend+UI | `proposed_actions` tests in `test_chat`, `test_chat_tools`, `fe/pages.test.tsx` | Offer the relevant next step (view claim, create case, readiness check, view case) | As expected | Pass |
| FR-036 | Health check | 2 | backend | `api/test_health.py`; production smoke (deployment guide) | `ok` / `degraded` with no internals | As expected | Pass |

## 3. Non-functional requirements

| ID | Requirement (target) | Evidence | Actual | Status |
|---|---|---|---|---|
| NFR-001 | Auth on all but `/health`, `/auth/login` | Route inventory test (26 authenticated routes) | All protected | Pass |
| NFR-002 | Authorization in backend only | Prompt-injection and direct-API tests (`test_chat_tools`, `test_phase8::test_prompt_injection…`, Workflow F) | Model and UI can't bypass it | Pass |
| NFR-003 | Data minimization in logs/audit | Allowlisted audit keys; tests that summaries, notes, comments and message text are absent from audit | As expected | Pass |
| NFR-004 | argon2id passwords | `unit/test_security.py` | As expected | Pass |
| NFR-005 | Lookups p95 ≤ 500 ms at 10 users | `scripts/perf_smoke.py`: 200 requests per endpoint, 10 concurrent | p95 42–188 ms, 0% errors (local laptop) | Pass |
| NFR-006 | Chat p95 ≤ 10 s, p50 ≤ 5 s | perf_smoke chat sample (30 requests, 3 concurrent) | Extractive: p50 213 ms, p95 296 ms. **With Claude: not measurable (no key)** | Partial |
| NFR-007 | Text PDF ≤ 30 s; OCR ≤ 15 s/page | document evaluation timings | Text PDFs 8–62 ms. **OCR: not measurable (Tesseract not installed)** | Partial |
| NFR-008 | AI timeouts; failures not fabricated | `test_chat` 503 tests; `test_chat_tools::test_tool_loop_is_bounded`; OCR failure tests | As expected | Pass |
| NFR-009 | Standard error format, no internals | `assert_error` everywhere; `test_phase8::test_errors_never_leak_internals`; pool-exhaustion 503 (D8-09) | As expected | Pass |
| NFR-010 | Structured logs, DB-derived metrics | JSON request logs observed; metrics from SQL | As expected | Pass |
| NFR-011 | ruff, **mypy**, eslint, tsc pass | ruff, eslint, tsc: pass. **mypy is not configured or run** | Not met for mypy | Fail |
| NFR-012 | Test doubles; ≥ 80% service/authz coverage | `pytest --cov=app` | 95% total; services/authz ≥ 88% (OCR adapter 74%, pipeline 75%) | Pass |
| NFR-013 | Clean install with Docker Compose; pinned deps; deterministic seed | Dockerfiles, `compose.yaml`, CI written; YAML validated; production config verified natively. **Docker is not installed here, so images were never built** | Seed repeatable (`int/test_seed.py`) | Blocked |
| NFR-014 | Loading, success and error text; ≤ 3 clicks | Frontend tests of loading, empty and error states; navigation | As expected | Pass |
| NFR-015 | WCAG 2.1 AA target; status not by colour alone | axe-core on 9 screens (0 violations); measured contrast ≥ 5.75:1 on all text/badge pairs; focus-visible rule; text labels on every badge | Automated and spot checks pass; **full conformance not audited** | Partial |
| NFR-016 | ≤ 50 concurrent users | perf_smoke at 50 users (500 requests per endpoint) | 0% errors; p95 343–515 ms; admin metrics capped at 10 concurrent (at 50 it saturated the pool, now returns 503 Retry-After, D8-09) | Pass |
| NFR-017 | FKs, CHECKs, transactional multi-row writes | `int/test_constraints.py`; atomicity tests (cases, checklists, uploads) | As expected | Pass |
| NFR-018 | Source title, version, date, excerpt, evidence status | `test_chat` citation fields; UI citation rendering tests | As expected | Pass |
| NFR-019 | Secrets via env; `.env` ignored | `scripts/secret_scan.py` (0 findings in 276 files and all commits); `git check-ignore`; bundle check | As expected | Pass |
| NFR-020 | Login 5/15 min; chat 20/min; uploads 20/h; body ≤ 11 MB | `test_auth` lockout; chat limit; upload default fixed 30→20 (D8-01); body guard 10 MB + 64 KB | As expected | Pass |
| NFR-021 | Retention 30/30/365 days; cleanup job | `scripts/cleanup_expired.py` + `test_phase8` retention test | Conversations, files and fields handled; **audit 365-day purge not implemented** (append-only trigger needs a maintenance role) | Partial |
| NFR-022 | Chrome/Edge/Firefox; usable from 360 px | Browser checks at 360/768/1440 px (Chromium-based pane); overflow defect fixed (D8-08) | Layout verified in a Chromium engine only; Firefox/Edge not run | Partial |

## 4. Gaps and follow-ups

| Item | Why | Follow-up |
|---|---|---|
| FR-019, NFR-007 (OCR) | Tesseract isn't installed in this environment | Install it (or use the Docker image, which includes `tesseract-ocr-eng`), re-run `scripts.evaluate_documents` |
| FR-010, NFR-006 (live LLM) | No approved Anthropic key (decision D-01 open) | Run the RAG and tool evaluations with `LLM_PROVIDER=anthropic` once a key is approved |
| NFR-011 (mypy) | Type checker never configured | Add mypy to dev tooling and CI; fix reported issues |
| NFR-013 (Docker) | Docker unavailable here | `docker compose build && docker compose up` on a machine with Docker; CI could add an image build job |
| NFR-015 | Automated checks can't establish conformance | Manual screen-reader and keyboard audit |
| NFR-021 (audit purge) | Requires a separate maintenance DB role (SEC-17) | Provision a maintenance role; scheduled purge |
| NFR-022 | Only a Chromium engine tested | Run the UI checks in Firefox and Edge |

## 5. Defects found and fixed in Phase 8

| ID | Defect | Fix | Regression evidence |
|---|---|---|---|
| D8-01 | Upload rate default 30/h vs NFR-020 20/h | Default 20 (config and `.env.example`) | Config |
| D8-02 | FR-034 feedback missing | `user_feedback` table (migration 0006), `POST /chat/messages/{id}/feedback`, metrics counts, chat UI | 3 backend + 2 frontend tests, browser + DB check |
| D8-03 | NFR-021 cleanup job missing | `retention_service` + `scripts/cleanup_expired.py` | Retention test |
| D8-05 | MEMBER lacked `feedback:create` (doc 03 matrix) | Permission map fixed | `unit/test_permissions::test_every_role_can_rate_answers` |
| D8-06 | PATCH /support-cases response returned stale history | Expire the session before reload | `test_case_review::test_patch_response_includes_the_history_row_it_just_wrote` |
| D8-07 | **At 10 concurrent requests, audited endpoints deadlocked the DB pool (30 s, 500s)** | Separate side-channel pool for audit and tool-log writes | `test_phase8::test_audit_writes_never_wait_on_the_request_pool`; load test 0% errors |
| D8-08 | Readiness page overflowed at 360 px (`<select>` width) | Controls capped at container width | Browser re-measure: no overflow |
| D8-09 | Pool exhaustion under overload reported as 500 | Mapped to 503 + `Retry-After` | `test_phase8::test_pool_exhaustion_is_reported_as_busy_not_internal_error` |
| D8-10 | Dev dependency vitest 3.2.7 had 3 advisories (2 critical, dev-only) | vitest 4.1.12 | `npm audit`: 0; 104 tests pass |
