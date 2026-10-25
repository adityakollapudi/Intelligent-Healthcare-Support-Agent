# IHSA Backend (Phases 2–6)

FastAPI + PostgreSQL backend for the **Intelligent Healthcare Support Agent**: an independent internship case-study prototype that uses **synthetic data only**. It is not an Evernorth product and connects to no real system.

Phase 2 provides the foundation: configuration, database schema and migrations, synthetic seed data, authentication, role-based authorization, audit logging, health, claim lookup and benefit lookup. The design source of truth is [`docs/phase-1`](../docs/phase-1/README.md). The decisions made while implementing it are in [`docs/phase-2/implementation-notes.md`](../docs/phase-2/implementation-notes.md).

## Prerequisites

- Python **3.12** (developed and tested on 3.12.0)
- PostgreSQL. Use one of:
  - **A. Private local cluster (no Docker).** An existing PostgreSQL install (tested with 18.0) plus `scripts/local_postgres.ps1`. This creates a separate cluster in `backend/.local/pgdata` and never touches other PostgreSQL services.
  - **B. Docker Compose.** `docker compose up -d db` (`docker-compose.yml`; not verified in Phase 2 because Docker was unavailable).
  - **C. Any PostgreSQL 13+ server** where you can create two databases, for example `ihsa_dev` and `ihsa_test`.

## Setup (PowerShell, from `backend/`)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt    # runtime only: requirements.txt

.\scripts\local_postgres.ps1 init                # option A: creates cluster + ihsa_dev + ihsa_test on 127.0.0.1:55432
Copy-Item .env.example .env                      # then edit .env (see below)

alembic upgrade head                              # apply migrations to DATABASE_URL
python -m scripts.seed_demo_data                  # insert synthetic demo data (safe to re-run)
python -m scripts.ingest_knowledge_base           # embed the synthetic knowledge corpus (first run downloads ~130 MB model)
uvicorn app.main:app --reload                     # http://127.0.0.1:8000
```

bash/macOS equivalents: `python3.12 -m venv .venv && source .venv/bin/activate`, then the same `pip`, `alembic`, `python -m` and `uvicorn` commands. The `local_postgres.ps1` helper is Windows-only. On other systems use option B or C.

Edit `.env` before seeding:
- `JWT_SECRET`: generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `SEED_USER_PASSWORD`: choose a password of at least 12 characters. Every demo account uses it.

Normal flow: **configure database → `alembic upgrade head` → seed → run**. The app never creates tables or runs migrations on startup.

## Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | yes | — | Must use `postgresql+psycopg://`. Never echoed in errors or logs |
| `JWT_SECRET` | yes | — | In `production`: at least 32 characters and not the example value |
| `APP_ENV` | no | `development` | `development` / `test` / `production`. `production` disables `/docs` and enforces the guards below |
| `APP_NAME`, `API_V1_PREFIX`, `LOG_LEVEL` | no | `intelligent-healthcare-support-agent`, `/api/v1`, `INFO` | `DEBUG` is refused in production |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_CONNECT_TIMEOUT_SECONDS` | no | 5, 5, 5 | |
| `DB_REQUIRED_AT_STARTUP` | no | `true` | Refuse to start when the DB is unreachable. Set `false` to start degraded (health reports 503) |
| `JWT_ACCESS_TOKEN_MINUTES` | no | 30 | |
| `LOGIN_MAX_FAILURES`, `LOGIN_FAILURE_WINDOW_MINUTES` | no | 5, 15 | Per-email login lockout |
| `CORS_ORIGINS` | no | `http://localhost:5173` | Comma-separated. `*` is refused in production |
| `SEED_USER_PASSWORD` | seed only | — | Read only by the seed script |
| `TEST_DATABASE_URL` | tests only | `…:55432/ihsa_test` | The database name **must end in `_test`**. The suite drops and rebuilds its schema |

Production guards (startup fails with a message that names the variable but not its value): weak or example JWT secret, wildcard CORS, DEBUG logging, or the development `postgres@localhost` superuser connection.

## API (base path `/api/v1`)

Interactive docs: `http://127.0.0.1:8000/docs`. OpenAPI JSON: `/api/v1/openapi.json`. Both are disabled in production.

| Method & route | Auth | Behavior |
|---|---|---|
| `GET /health` | public | `200 {"status":"ok","checks":{"api":"ok","database":"ok"},"time":…}`. `503` with `"degraded"` / `"database":"unavailable"` when the DB is unreachable. No versions or hosts are exposed |
| `POST /auth/login` | public | `{email,password}` → bearer token (30 min). Wrong password and unknown email return the same `401 INVALID_CREDENTIALS`. The 6th failure within 15 min returns `429` with `Retry-After` |
| `POST /auth/logout` | any role | Revokes the current token → `204` |
| `GET /auth/me` | any role | Profile, member number and plan (members), organization (staff), permission list for UI use |
| `GET /claims` | `MEMBER` | Your own claims, newest first. `?status=` (repeatable), `?limit=` 1–100, `?cursor=` |
| `GET /claims/{claim_number}` | `MEMBER` (own), `SUPPORT_AGENT` (case-linked; agent case linking arrives in Phase 7) | `claim_number` like `SYN-CLM-2026-000101`. Another member's claim and a nonexistent claim both return the same `404`. `PROVIDER` and `ADMIN` get `403` |
| `GET /benefits/{plan_code}` | `MEMBER` (own plan), `PROVIDER`, `SUPPORT_AGENT`, `ADMIN` (any active plan) | `plan_code` like `SYN-PLAN-GOLD-01`. Optional `?benefit_category=IMAGING`. `source` is `null` (per-benefit passage links are not implemented; documentation requirements carry verified sources) |
| `POST /chat` | any role (`chat:use`) | `{message, client_message_id, session_id?}` → a document-grounded answer with validated citations, or an explicit insufficient-evidence / clarification / not-supported response. Retrieval is filtered by role audience and (for members) own plan. A repeated `client_message_id` returns the stored answer. 503 `AI_SERVICE_UNAVAILABLE` on embedding/LLM failure (never reported as "no information"). See `docs/phase-4/rag-implementation.md` |
| `GET /chat/sessions`, `GET /chat/sessions/{id}` | any role (own sessions only) | Recent conversations and their messages (including `tool_executions` and `records`). Another user's session returns 404 |
| `POST /support-cases` | `MEMBER`, `PROVIDER` (`cases:create`) | Requires an `Idempotency-Key: <UUID>` header. `201` creates an `OPEN` case (`CASE-YYYY-NNNNNN`) with its event and audit row in one transaction; `200` is a replay of the same key and body; `409 IDEMPOTENCY_KEY_REUSED` means the same key was sent with a different body. Server-controlled fields are rejected (422). See `docs/phase-5/api-and-workflow-contracts.md` |
| `GET /support-cases`, `GET /support-cases/{id}` | `MEMBER`, `PROVIDER` (own cases only) | `?status=` (repeatable), `?limit=` 1–100. Another user's case returns 404 |
| `GET /authorization/requirements/{procedure_code}` | any role with `requirements:read` | Configured documentation requirements for a fictional procedure (e.g. `SYN-PROC-MRI-LUMBAR`), each with its verified source passage. Not an approval |

| `POST /documents` (multipart) | `MEMBER`, `PROVIDER` | Upload a synthetic PDF/PNG/JPEG (≤10 MB, ≤20 pages). Validated by extension, declared type, file signature and content. Stored privately (`.local/uploads`); `201` means stored, **not analyzed** |
| `GET /documents`, `GET /documents/{id}` | owner only | Documents with the latest analysis job: page details, warnings, extracted fields with validation status and source page |
| `POST /documents/{id}/analyze` | owner (`documents:upload`) | `202` + job; poll `GET /documents/{id}`. `409 JOB_ALREADY_RUNNING` |
| `GET /authorization/requirement-sets` | `requirements:read` | Active fictional requirement sets |
| `POST /authorization/readiness`, `GET /authorization/checklists[/{id}]` | `PROVIDER` | Deterministic documentation-readiness checklist (SATISFIED / MISSING / UNREADABLE / NEEDS_MANUAL_REVIEW) with evidence, sources and a reviewer summary. **Not an approval or denial.** See `docs/phase-6/` |

**Documents (Phase 6).** Text comes from the PDF text layer. OCR (Tesseract, configured via `OCR_TESSERACT_PATH`) is used only for scanned pages and images, and it is **not installed in the development environment**, so scanned pages are reported as unreadable rather than guessed. Samples: `python -m scripts.build_sample_documents`. Evaluation: `python -m scripts.evaluate_documents`. Guide: `docs/phase-6/document-processing-guide.md`.

**Chat tools (Phase 5).** `POST /chat` can call four allowlisted tools (`get_claim_status`, `get_plan_benefits`, `get_required_documents`, `create_support_case`) through one executor that validates arguments, checks permissions, reuses the services above and audits every call (`TOOL_INVOKED`, plus a `tool_invocations` row). `create_support_case` only proposes a case; the user creates it by confirming, which sends `POST /support-cases`. Answers report `tool_executions` and structured `records` next to `citations`. Details: `docs/phase-5/tool-integration.md`.

**Errors** use one format everywhere:
```json
{"error": {"code": "RESOURCE_NOT_FOUND", "message": "The requested item was not found.", "details": [], "request_id": "…"}}
```
Codes: `VALIDATION_ERROR` / `FIELD_NOT_ALLOWED` (422), `UNAUTHENTICATED` / `INVALID_CREDENTIALS` (401), `FORBIDDEN` (403), `RESOURCE_NOT_FOUND` (404), `METHOD_NOT_ALLOWED` (405), `RATE_LIMITED` (429), `INTERNAL_ERROR` (500), `SERVICE_UNAVAILABLE` (503, database unreachable). Error bodies never contain stack traces, SQL, connection details or submitted values. Every response carries `X-Request-ID`; send your own UUID in that header to correlate requests.

Quick try (PowerShell, server running):
```powershell
$pw = (Get-Content .env | Select-String '^SEED_USER_PASSWORD=').ToString().Split('=',2)[1]
$t = (Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/auth/login -ContentType application/json -Body (@{email='priya.member@example.test'; password=$pw} | ConvertTo-Json)).access_token
Invoke-RestMethod http://127.0.0.1:8000/api/v1/claims/SYN-CLM-2026-000101 -Headers @{Authorization="Bearer $t"}
```

## Synthetic demo data

`python -m scripts.seed_demo_data` inserts any missing records, matched by stable natural keys, in one transaction. It never updates or deletes existing rows, and it prints inserted/skipped counts. Data definitions live in `scripts/seed_data.py`.

| Entity | Records |
|---|---|
| Organizations | Maplestone Family Clinic (fictional) · IHSA Synthetic Support Center |
| Plans | `SYN-PLAN-GOLD-01`, `SYN-PLAN-BRONZE-01` (active), `SYN-PLAN-SILVER-25` (inactive, 2025) with 14 benefit entries |
| Members | `SYN-M-000001` (Gold), `SYN-M-000002` (Bronze), `SYN-M-000003` (Gold) |
| Claims | 10: `SYN-CLM-2026-000101…105` (member 1, one per status), `…000201–203` (member 2), `…000301–302` (member 3). `SYN-CLM-2026-999999` is deliberately absent |
| Accounts (`SEED_USER_PASSWORD`) | `priya.member@`, `lee.member@`, `robin.member@`, `jordan.provider@`, `casey.provider@`, `sam.agent@`, `taylor.agent@`, `alex.admin@` — all `…example.test` |

Claim statuses: `RECEIVED`, `UNDER_PROCESSING`, `PENDING_INFORMATION`, `PROCESSED_PAID`, `PROCESSED_DENIED`.

## AI / RAG (Phase 4)

- **Knowledge corpus:** `data/knowledge/` (14 synthetic documents plus `manifest.json`). Manage it as described in `docs/phase-4/knowledge-base-guide.md`, then run `python -m scripts.ingest_knowledge_base`.
- **Embeddings:** `BAAI/bge-small-en-v1.5`, run locally on CPU via fastembed. They are stored as `REAL[]` in PostgreSQL; pgvector isn't required (deviation D4-01).
- **Answers:**
  - `LLM_PROVIDER=extractive` (default): no LLM. Answers quote the retrieved source sentences, and every answer says so.
  - `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`: Claude writes the answers. **This path is unit-tested with a mocked client but has not been run live.**
- **Evaluation:** `python data/evaluation/build_eval_set.py`, then `python -m scripts.evaluate_rag`. This writes `data/evaluation/results/rag_eval_v1_<provider>.{md,json}`; see `docs/phase-4/rag-evaluation-report.md`.

## Migrations

```powershell
alembic upgrade head                                   # apply
alembic current                                        # show applied revision (0002)
alembic check                                          # fail if models and migrations drift
alembic revision --autogenerate -m "describe_change"   # new revision: always review the file
alembic downgrade -1                                   # dev/test databases only
```
Each phase adds its own tables in a new revision: `0001` is the Phase 2 foundation, and `0002` adds the knowledge base and conversations in Phase 4. Never run downgrades against a database you can't recreate.

## Tests

```powershell
.\scripts\local_postgres.ps1 start         # the PostgreSQL tests need TEST_DATABASE_URL reachable
python -m pytest                           # all tests
python -m pytest tests/unit                # no database needed
python -m pytest -m "not postgres"         # skip DB-backed tests explicitly
ruff check .
```

The suite rebuilds the `*_test` database from migrations and seeds it. It covers config validation, security helpers, the permission map, migrations (including a downgrade/upgrade round trip in a scratch database), constraints, seed repeatability, every endpoint's success, validation, authentication, authorization, outage and unexpected-error paths, and a route inventory that fails if any non-public route lacks authentication. If PostgreSQL is unreachable, the DB-backed tests are **skipped** (reported by pytest), not passed.

## Stopping local services

```powershell
# uvicorn: Ctrl+C
.\scripts\local_postgres.ps1 stop       # option A
docker compose down                     # option B (add -v to delete the volume)
```

## Common problems

| Symptom | Fix |
|---|---|
| `Invalid configuration: DATABASE_URL: Field required` | Create `.env` from `.env.example` or set the variable |
| `DATABASE_URL must use the 'postgresql+psycopg' driver` | Change the URL prefix from `postgresql://` to `postgresql+psycopg://` |
| `RuntimeError: Database is unavailable…` at startup | Start PostgreSQL (`local_postgres.ps1 start`) or set `DB_REQUIRED_AT_STARTUP=false` |
| `relation "users" does not exist` | Run `alembic upgrade head` |
| Seed prints `SEED_USER_PASSWORD is not set` | Add it to `.env` (≥ 12 characters) |
| Tests refuse to run: name must end in `_test` | Point `TEST_DATABASE_URL` at a dedicated test database |
| `local_postgres.ps1` can't find binaries | Set `IHSA_PG_BIN` to the folder containing `initdb.exe` |

## Known limitations (Phase 2)

- Login rate limiting is per email only. There's no per-IP limit yet (NFR-020 IP part → Phase 8).
- Tokens live in memory on the client. There's no refresh token (D-09).
- Support-agent claim access (`claims:read:case_linked`) always returns 404 until support cases exist (Phase 5/7).
- Separate least-privilege DB roles (SEC-17) aren't set up yet. Append-only audit is enforced by a database trigger instead.
- The Claude answer path has never been run against the live API. The extractive mode misses paraphrased questions and sometimes quotes related-but-not-answering sentences (see the evaluation report).
