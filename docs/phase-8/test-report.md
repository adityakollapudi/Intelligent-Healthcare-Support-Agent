# Phase 8 — Test Report

Final verification of the integrated IHSA prototype. All results below were produced by commands that were actually executed on 2026-10-27. Nothing here is projected or estimated.

## 1. Environment

| Item | Value |
|---|---|
| Machine | Windows 11 Home, 13th Gen Intel Core i5-1335U, 15.6 GB RAM (laptop, local only) |
| Backend | Python 3.12.0, FastAPI, SQLAlchemy 2.1, PostgreSQL 18 (local cluster `127.0.0.1:55432`, `scripts/local_postgres.ps1`) |
| Frontend | Node.js 24.13.0, npm 11.6.2, Vite 6.4.5, Vitest 4.1.12 |
| AI | fastembed `BAAI/bge-small-en-v1.5` (CPU); `LLM_PROVIDER=extractive` (no LLM) |
| Not available | Tesseract OCR, an approved Anthropic API key, Docker, Firefox/Edge |
| Test database | `ihsa_test`, dropped and rebuilt from all Alembic migrations at the start of every run (fresh-install path) |

## 2. Results

| Suite | Command (from the folder shown) | Total | Passed | Failed | Skipped |
|---|---|---|---|---|---|
| Backend lint | `backend> .venv\Scripts\ruff check app tests scripts` | — | clean | 0 | — |
| Backend tests (unit, API, integration, workflows, security) | `backend> .venv\Scripts\python -m pytest -ra` | **453** | **453** | 0 | 0 |
| Backend coverage | `backend> .venv\Scripts\python -m pytest --cov=app` | — | 95% lines | — | — |
| Migrations | `backend> .venv\Scripts\alembic check`; dev `downgrade 0005` → `upgrade head` | — | no drift; reversible | 0 | — |
| Frontend lint | `frontend> npm run lint` | — | clean | 0 | — |
| Frontend types | `frontend> npx tsc --noEmit` | — | clean | 0 | — |
| Frontend tests (components, pages, a11y) | `frontend> npx vitest run` | **104** (8 files) | **104** | 0 | 0 |
| Frontend production build | `frontend> npm run build` | — | built (286 kB JS, 88 kB gzip) | 0 | — |
| Python dependency audit | `backend> .venv\Scripts\pip-audit -r requirements.txt` | — | no known vulnerabilities | — | — |
| npm audit | `frontend> npm audit` | — | 0 vulnerabilities (after D8-10) | — | — |
| Secret scan | `> backend\.venv\Scripts\python backend\scripts\secret_scan.py` | 276 files, 5 commits | 0 findings | — | — |
| RAG evaluation (131 items) | `backend> .venv\Scripts\python -m scripts.evaluate_rag` | 131 | 115 behavior matches | 16 mismatches (analysed) | — |
| Document evaluation (13 docs, 10 scenarios) | `backend> .venv\Scripts\python -m scripts.evaluate_documents` | 10 scored docs / 9 scored scenarios | 100% | 0 | 3 docs not scored (need OCR) |
| Load test | `backend> .venv\Scripts\python -m scripts.perf_smoke [--users 50 --requests 500]` | 1,430 / 3,530 requests | 0% errors | 0 | — |
| Production-mode smoke | APP_ENV=production with a DML-only DB role (deployment guide §5) | 10 config + 5 DB-privilege checks | 15 | 0 | — |
| Browser end-to-end | in-app browser against the live API (§5) | 6 journeys + responsive/a11y | executed | 0 open | — |

**Skips are reported explicitly.** pytest runs with `-ra`, and with PostgreSQL available nothing was skipped. If the database is unreachable, the database-backed tests are *skipped* and listed, never counted as passed (`tests/conftest.py`).

## 3. What the backend suite covers (453 tests)

| Area | Main files | Notes |
|---|---|---|
| Config, security, permissions | `unit/test_config`, `test_security`, `test_permissions` | Production guards (example JWT secret, wildcard CORS, DEBUG logs, dev superuser) |
| Auth, health, error format, route inventory | `api/test_auth`, `test_health`, `test_security_baseline`, `test_app`, `test_startup` | 26 authenticated routes; DB outage → 503 |
| Claims, benefits | `api/test_claims`, `test_benefits` | Cross-member access, unknown IDs, outages |
| RAG and chat | `unit/test_rag_units`, `int/test_rag_ingest`, `api/test_chat` | Grounding, citation validation, insufficient evidence, conflicts, LLM/embedding failures, idempotent retry |
| Tools | `unit/test_tools_unit`, `int/test_tools`, `api/test_chat_tools` | Allowlist, schemas, permission, budget, scripted Claude tool loop, false-success guard |
| Support cases | `api/test_support_cases`, `unit/test_case_workflow`, `api/test_case_review` | Idempotency, atomic audit, lifecycle, scopes, versions, assignment, linked resources |
| Documents and readiness | `unit/test_documents_unit`, `api/test_documents` | Validation, storage, OCR handling (fake engine), fields, rules, checklists, privacy |
| Audit, metrics, knowledge gaps | `api/test_case_review` | Hand-computed metrics, suppression, admin-only read-only API |
| **Phase 8** | `api/test_phase8.py` (23) | Feedback, retention, **Workflows A–F**, forged/expired tokens, unsafe pagination, error leakage, prompt injection, pool regressions |
| Database | `int/test_migrations`, `test_constraints`, `test_seed` | Fresh migration, downgrade/upgrade round trip, constraints, seed repeatability |

## 4. Defects found in Phase 8

| ID | Severity | Found by | Root cause | Fix | Retest |
|---|---|---|---|---|---|
| D8-07 | **High** (availability) | Load test: 10 concurrent requests to audited endpoints took 30 s and some returned 500 | Every request held one pool connection, and its audit write checked out a second from the same pool (5+5): 10 requests exhausted it and waited on each other until the pool timeout | Dedicated side-channel pool (`get_side_session_factory`) for audit and tool-log writes | Regression test; 10 users p95 ≤ 188 ms, 50 users 0% errors |
| D8-02 | Medium (missing requirement) | Requirements trace | FR-034 (Should, Phase 7) never implemented | Feedback API, table (migration 0006), metrics, UI | 5 tests + browser/DB |
| D8-03 | Medium | Requirements trace | NFR-021 cleanup job missing | Retention service + script | Retention test |
| D8-05 | Medium | Requirements trace | MEMBER lacked `feedback:create` (doc 03) | Permission map | Unit test |
| D8-06 | Medium (wrong response data) | Workflow E test | PATCH response reused the identity map's stale `events` collection | `expire_all()` before reload | Regression test |
| D8-09 | Low | Load test at 50 users (admin metrics) | Pool timeout fell through to the generic 500 handler | 503 + `Retry-After: 5` | Regression test |
| D8-08 | Low (usability) | Browser at 360 px | `<select>` width = longest option | `max-width: 100%` on controls | Re-measured, no overflow |
| D8-01 | Low | Requirements trace | Upload limit 30/h vs 20/h | Default changed | Config |
| D8-10 | Low (dev-only) | npm audit | vitest 3.2.7 advisories | vitest 4.1.12 | audit 0, tests pass |

Contract tests that changed on purpose: the route inventory (+1 feedback route, 26 authenticated), the migration table list (+`user_feedback`, revision 0006), and the metrics test (`unavailable` is now `[]`, and `feedback` counts were added). No test was deleted or weakened.

## 5. End-to-end journeys (browser, live API, dev database)

| Journey | How it was run | Result |
|---|---|---|
| A — question with citations; unanswerable question | Phase 4/7 browser runs + `test_phase8::test_workflow_a…` | Cited answer; "couldn't find", plus a support offer |
| B — claim lookup | Phase 5 browser run (record card) + `test_workflow_b…` | Record matches the API; unknown and other-member claims return 404 |
| C/D — document → readiness | Phase 6 browser run (mixed PDF, checklist 3/2/0/1) + `test_workflows_c_and_d…` | Statuses, sources and summary match; no approval wording |
| E — escalation → agent → audit → dashboard | Phase 7 browser run (CASE-2026-000003) + SQL cross-check + `test_workflow_e…` | Counts match SQL; history and audit exact |
| F — authorization boundaries | `test_workflow_f…`, scope tests, token tests | All refused and audited |
| Feedback (Phase 8) | Browser: admin rated an answer → "Thanks, your rating was recorded."; DB row and audit row checked | Pass |

The in-app browser automation could not drive clicks while emulating a phone viewport, because the hidden pane doesn't paint or run CSS transitions. So responsive checks were done by navigating with the app's router and measuring layout with read-only JavaScript (accessibility report in security-report.md §6). This is a limitation of the test tooling, not of the app: the menu's CSS rules were verified directly.

## 6. Not executed / blocked

| Item | Reason |
|---|---|
| Real OCR (Tesseract) and the 3 scanned evaluation documents | Engine not installed |
| Claude generation, tool use and extraction with a live model | No approved API key (mocked or scripted tests only) |
| Docker image build and `docker compose up` | Docker not installed. Compose and CI YAML were validated, and the production configuration was verified natively |
| CI workflow run | Not pushed or run on GitHub; it runs the same commands listed in §2 |
| Firefox / Edge | Only a Chromium engine was available |
| mypy (NFR-011) | Not configured |
