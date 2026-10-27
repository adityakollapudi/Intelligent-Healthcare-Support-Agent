# Phase 8 — Deployment Guide

Two supported paths:
- **(A) Native local development** on Windows. This is the path verified end to end in this project.
- **(B) Docker Compose.** The files are provided, but they were **not executed here, because Docker isn't installed**. Treat the first run as a verification step.

Synthetic data only. No external or company deployment was performed.

## 1. Prerequisites

| Path | Needs |
|---|---|
| A | Python 3.12, Node.js 20+ (verified on 24.13), a PostgreSQL 18 installation (binaries; `scripts/local_postgres.ps1` creates a private cluster), and optionally Tesseract OCR 5 with English data |
| B | Docker Engine 24+ with Compose v2 |

## 2. Environment settings

| Area | Variables (see `backend/.env.example`, root `.env.example` for Compose) |
|---|---|
| Application | `APP_ENV` (development / test / production), `API_V1_PREFIX`, `LOG_LEVEL` |
| Database | `DATABASE_URL` (postgresql+psycopg), `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_SIDE_POOL_SIZE`, `DB_SIDE_MAX_OVERFLOW` (audit/tool-log pool, D8-07), `DB_CONNECT_TIMEOUT_SECONDS`, `DB_REQUIRED_AT_STARTUP`, `TEST_DATABASE_URL` (name must end in `_test`) |
| Authentication | `JWT_SECRET` (≥ 32 random characters in production), `JWT_ACCESS_TOKEN_MINUTES`, `LOGIN_MAX_FAILURES`, `LOGIN_FAILURE_WINDOW_MINUTES` |
| CORS | `CORS_ORIGINS` (comma-separated; `*` refused in production) |
| LLM | `LLM_PROVIDER` (`extractive` default / `anthropic`), `LLM_MODEL`, `LLM_EFFORT`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `ANTHROPIC_API_KEY` (secret; only with approval) |
| Embeddings | `EMBEDDING_PROVIDER` (`fastembed`), `EMBEDDING_MODEL`, `EMBEDDING_CACHE_DIR` |
| Retrieval | `RAG_*`, `CHAT_*`, `TOOL_MAX_CALLS_PER_MESSAGE` |
| Vector store | None separate: embeddings live in PostgreSQL (`document_chunks`, deviation D4-01) |
| Documents and OCR | `DOCUMENT_STORAGE_DIR` (private), `MAX_UPLOAD_BYTES`, `MAX_PDF_PAGES`, `MAX_IMAGE_MEGAPIXELS`, `JOB_TIMEOUT_SECONDS`, `MAX_CONCURRENT_DOCUMENT_JOBS`, `DOCUMENT_UPLOADS_PER_HOUR` (20), `DOCUMENT_ANALYSES_PER_HOUR`, `OCR_ENGINE`, `OCR_TESSERACT_PATH`, `OCR_LANGUAGES`, `OCR_*` |
| Retention | `CHAT_SESSION_RETENTION_DAYS`, `DOCUMENT_RETENTION_DAYS` (provisional 30) |
| Demo seed | `SEED_USER_PASSWORD` (read only by the seed script) |
| Frontend | `VITE_API_BASE_URL`, `VITE_API_TIMEOUT_MS` (public build-time values; **never secrets**) |

Secrets belong only in `.env` files, which are git-ignored. `.env.example` files hold placeholders.

## 3. Path A — native local setup (verified)

The first two blocks start the backend and the frontend; each needs its own terminal.

```powershell
# backend (PowerShell)
cd backend
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env          # set JWT_SECRET and SEED_USER_PASSWORD
.\scripts\local_postgres.ps1 init    # first time: private cluster on 127.0.0.1:55432 + ihsa_dev + ihsa_test
.\scripts\local_postgres.ps1 start   # later runs
.\.venv\Scripts\alembic upgrade head # migrations 0001 → 0006
.\.venv\Scripts\python -m scripts.seed_demo_data          # synthetic demo data (idempotent)
.\.venv\Scripts\python -m scripts.ingest_knowledge_base   # embeds the knowledge corpus (~130 MB model on first run)
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# frontend (second terminal)
cd frontend
npm ci; Copy-Item .env.example .env.local
npm run dev                          # http://localhost:5173
```

```powershell
# health and smoke checks (from backend/)
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health      # {"status":"ok",...}
.\.venv\Scripts\python -m pytest -ra                        # 453 tests
.\.venv\Scripts\python -m scripts.perf_smoke               # bounded local load test
```

**Shutdown:** stop uvicorn and Vite with Ctrl+C, then `.\scripts\local_postgres.ps1 stop`.

**OCR (optional):** install Tesseract, for example `winget install UB-Mannheim.TesseractOCR`. Set `OCR_TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe` and restart the API. Then check with `python -m scripts.evaluate_documents`: its header should show `available: True`.

**Model:** the default `LLM_PROVIDER=extractive` needs no key. For Claude, set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`, but only with an approved key and data-handling terms (decision D-01). This mode is unverified live.

## 4. Path B — Docker Compose (files provided, not executed here)

Files: `compose.yaml`, `backend/Dockerfile` (python:3.12-slim, Tesseract eng, non-root uid 10001, health check), `frontend/Dockerfile` (node:24 build → nginx-unprivileged on port 8080), `frontend/nginx.conf` (SPA fallback, security headers), and `.dockerignore` files.

```bash
cp .env.example .env
docker compose build
docker compose up -d db
docker compose run --rm migrate
docker compose --profile demo run --rm seed
docker compose up -d api frontend
docker compose ps
curl http://localhost:8000/api/v1/health
docker compose down
```

1. In `.env`, set `POSTGRES_PASSWORD`, `JWT_SECRET` and `SEED_USER_PASSWORD`. Compose refuses to start without them.
2. `docker compose run --rm migrate` is a **controlled migration step**. Migrations never run automatically at API start.
3. The `seed` step loads demo data and the knowledge base, **only when explicitly requested** (it is under the `demo` profile).
4. `docker compose up -d api frontend` starts the API on http://localhost:8000 and the UI on http://localhost:8080.
5. `docker compose down` stops everything. Data persists in the named volumes `pgdata`, `uploads` and `models`.

Startup order: db (healthy) → migrate → (optional seed) → api → frontend.

- **Ports:** the database isn't published, and the API and UI are published on 127.0.0.1 only.
- **Production mode:** the API runs with `APP_ENV=production`, so docs are off and strict configuration guards apply.
- **Limits:** memory and CPU limits are set per service.
- **Before relying on this path:** build the images, run the steps above, run `pytest` against the container database if needed, and scan the images (for example with Trivy).

## 5. Production-like configuration check (verified natively)

On 2026-10-27 the API was started with `APP_ENV=production` against the local cluster through a DML-only role. The role was created with `python -m scripts.create_app_role --role ihsa_app --database ihsa_dev`.

- **Refused at startup:** the example JWT secret, `CORS_ORIGINS=*`, and the dev `postgres@localhost` superuser connection.
- **With a valid configuration:**
  - health is `ok`;
  - `/docs` and `/api/v1/openapi.json` return 404;
  - unauthenticated `/claims` returns 401;
  - CORS is granted only to the configured origin;
  - an unknown route returns 404 with no traceback.
- **The `ihsa_app` role:** can read and write rows, but can't create or drop tables or update or delete audit rows.

For a real deployment, run migrations with an owner/migrator role and the API with the DML-only role (SEC-17).

## 6. Scheduled jobs

| Job | Command | Suggested schedule |
|---|---|---|
| Retention cleanup (sessions, expired documents and fields, revoked tokens) | `python -m scripts.cleanup_expired` (`--dry-run` to preview) | Daily |

## 7. Backup and recovery (local prototype)

- **Database:** `pg_dump -h 127.0.0.1 -p 55432 -U postgres -Fc ihsa_dev > ihsa_dev.dump` and `pg_restore` to recover. With Compose, back up the `pgdata` volume, or run `pg_dump` inside the `db` container.
- **Uploads:** back up `DOCUMENT_STORAGE_DIR` (Compose: the `uploads` volume) **together with** the database, because rows reference storage keys.
- **Rebuildable:** the knowledge base can be rebuilt from `data/knowledge` with `ingest_knowledge_base`. Demo data can be re-seeded with `seed_demo_data`, which is idempotent and never deletes.

## 8. CI

`.github/workflows/ci.yml` runs on push and pull requests:
- **backend job:** ruff and the full pytest suite against a PostgreSQL 18 service container, pip-audit, and the secret scan;
- **frontend job:** lint, tsc, vitest, build, and `npm audit --audit-level=high`.

No external AI services are called. The workflow was written and YAML-validated but **hasn't run on GitHub yet**: it runs on the first push.

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| API refuses to start: "Invalid configuration: …" | Read the named setting; production refuses example or weak secrets, `*` CORS, DEBUG and the dev superuser |
| `connection timeout expired` / DB 503 | PostgreSQL isn't running: `.\scripts\local_postgres.ps1 start` |
| 503 "The service is busy" under load | Pool exhausted. Raise `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` or reduce concurrency |
| Scanned documents fail with `OCR_FAILED` | Install Tesseract (§3) |
| 404 `REQUIREMENTS_SOURCE_UNAVAILABLE` | Run `scripts.ingest_knowledge_base` |
| Frontend calls fail with CORS errors | Open http://localhost:5173 (not 127.0.0.1) or add the origin to `CORS_ORIGINS` |
| Tests are skipped | The PostgreSQL test database is unreachable; skipped tests are listed by `pytest -ra` |
