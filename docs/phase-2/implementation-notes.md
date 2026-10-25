# Phase 2 — Implementation Notes and Design Decisions

Records how Phase 2 implemented the Phase 1 design, and every place it deviated or filled a gap. Setup and usage instructions are in [`backend/README.md`](../../backend/README.md).

## 1. Inspection summary (start of Phase 2)

- The workspace contained only `docs/phase-1/` (12 files, all present). There was no code, no Git repository, no Docker, and no `psql` on PATH.
- Python 3.12.0, 3.11 and 3.14 were installed. **3.12** was used, matching Phase 1 doc 04.
- PostgreSQL 13 and 18 services were running on 5432/5433 with unknown credentials. They were **not touched**. Instead, `scripts/local_postgres.ps1` uses the PostgreSQL 18 binaries to run a private cluster on `127.0.0.1:55432` (trust auth, localhost only, synthetic data only).
- No Phase 1 inconsistencies blocked implementation. The gaps filled are listed in §3.

## 2. What was built

| Area | Implementation |
|---|---|
| App | `app/main.py` (`create_app` factory, lifespan DB check), `api/v1/router.py`, routes `health`, `auth`, `claims`, `benefits` |
| Config | `core/config.py` (pydantic-settings, validation, production guards, sanitized `ConfigurationError`) |
| Errors/logging | `core/exceptions.py` (standard error format), `core/middleware.py` (request ID, JSON request log, `Cache-Control: no-store`, last-resort 500), `core/logging.py` |
| Security | `core/security.py` (argon2id, HS256 JWT, email fingerprint), `authz/permissions.py` (full doc 03 catalogue: 27 permissions), `authz/dependencies.py` (`get_current_principal`, `require_any_permission`) |
| Data | Models for 8 tables, Alembic revision `0001`, `scripts/seed_demo_data.py` |
| Layers | routes → services (`auth`, `claim`, `benefit`, `health`, `audit`) → repositories (`user`, `claim`, `plan`) |
| Tests | 130 tests: unit, API and PostgreSQL integration |

## 3. Decisions and deviations from Phase 1

| # | Topic | Phase 1 said | Phase 2 did | Why |
|---|---|---|---|---|
| D2-01 | Scope of the initial migration | 26 tables in doc 05 | 8 tables now: `organizations`, `users`, `members`, `plans`, `plan_benefits`, `claims`, `audit_logs`, `revoked_tokens`. Each later phase adds its own tables in a new revision | Avoids dead schema and lets each phase review its own tables. The Phase 2 prompt also forbids implementing future-phase entities without need |
| D2-02 | `plans.source_document_id`, `plan_benefits.source_chunk_id` | FK columns to knowledge tables | Deferred to the Phase 4 revision. `benefits[].source` is returned as `null` | Their FK targets don't exist until Phase 4 |
| D2-03 | `users.email` type | `citext` | `varchar(254)` + `CHECK (email = lower(email))` + unique. The app lower-cases input | No extension dependency. Same case-insensitive uniqueness |
| D2-04 | `pgcrypto` | Listed for `gen_random_uuid()` | Not required | Built into PostgreSQL 13+ |
| D2-05 | Health/readiness | `GET /health` with `checks.api` / `checks.database` | Same single route. `checks.api` is liveness, `checks.database` is readiness. Returns 503 `degraded` when the DB is down. No version/service fields | The Phase 1 contract already defines readiness semantics and forbids exposing versions. A separate `/health/ready` would duplicate it |
| D2-06 | Error codes | Doc 06 §4 table | Added `SERVICE_UNAVAILABLE` (503, database unreachable) and `METHOD_NOT_ALLOWED` (405) | Needed for DB outages and wrong methods. Doc 06 is updated |
| D2-07 | Login lockout | 5 failures / 15 min / account (+ IP) | Counts `AUTH_LOGIN_FAILED` audit events per keyed email fingerprint within the window; this also covers unknown emails. `users.failed_login_count` is kept as an informational counter. The per-IP limit is deferred to Phase 8 | Reuses the audit trail, so no extra lockout columns are needed |
| D2-08 | Login failure reason codes | Not specified | `UNKNOWN_EMAIL`, `BAD_PASSWORD`, `DISABLED` (audit only; the client always sees `INVALID_CREDENTIALS`) | Supports investigation without leaking account existence. Doc 02 §3.9 is updated |
| D2-09 | Audit write semantics | "Append-only audit events" | (a) Each event is written in its own transaction, so denials persist even when the request fails. (b) **Fail closed**: if an event can't be stored, the request returns 500 and no data. (c) A DB trigger blocks UPDATE/DELETE on `audit_logs`; the retention purge must `SET LOCAL ihsa.allow_audit_purge = 'on'`. (d) Metadata keys are allowlisted in `audit_service.py` | Integrity regardless of code path. The prompt requires a documented failure behavior. SEC-17 DB roles are not set up yet |
| D2-10 | Agent claim access | Claims linked to an assigned case | Permission present, but always 404 (`NOT_ASSIGNED`) until `support_cases` exists (Phase 5/7) | Can't be implemented without case links. Fails closed |
| D2-11 | `GET /claims` page | Page of summaries | Adds top-level `data_environment` | Doc 06 convention for responses with record data |
| D2-12 | Seed data | Gold + Bronze plans | Adds inactive `SYN-PLAN-SILVER-25` | Tests the active-plan filter for staff |
| D2-13 | Orchestration of DB in tests | — | Tests use a dedicated `*_test` database rebuilt from migrations (never `create_all`). A scratch database tests downgrade/upgrade | Proves the migrations themselves, on PostgreSQL |
| D2-14 | Library versions | FastAPI/SQLAlchemy 2.x/Alembic | FastAPI 0.162, SQLAlchemy 2.1.6, Alembic 1.20.1, psycopg 3.3.6, pydantic 2.14, PyJWT 2.15, argon2-cffi 25.1 (pinned) | Current stable releases at implementation time |
| D2-15 | Dev identity adapter | — | **Not used.** Real local login (doc 03 §4.1) was implemented. Tests log in through the API with seeded accounts | Phase 1 placed `/auth/*` in Phase 2. No insecure bypass exists to disable in production |

## 4. Acceptance tests from Phase 1 covered in Phase 2

| AT | Status | Test(s) |
|---|---|---|
| AT-001 | Pass | `tests/api/test_auth.py::test_login_and_me` |
| AT-002 | Pass (per-email; per-IP part deferred) | `test_wrong_password_and_unknown_email_look_identical`, `test_repeated_failures_are_rate_limited` |
| AT-003 | Pass | `test_protected_routes_reject_missing_or_invalid_tokens` (20 cases), `test_logout_revokes_the_token`, `tests/unit/test_security.py` |
| AT-004 | Partly: admin routes arrive in Phase 7. Role-denial mechanism verified on claims | `test_roles_without_claim_permission_are_forbidden` |
| AT-005 | Pass | `test_other_members_claim_is_indistinguishable_from_missing` |
| AT-006 | Pass | `test_roles_without_claim_permission_are_forbidden` |
| AT-019 / AT-020 | Pass (API part; tool part is Phase 5) | `test_own_claim_matches_database_exactly`, `test_other_members_claim_is_indistinguishable_from_missing` |
| AT-021 / AT-022 | Pass | `tests/api/test_benefits.py` |
| AT-057 | Pass | `test_unexpected_error_returns_safe_500`, `test_database_outage_returns_503_without_details`, validation tests |
| AT-058 | Pass | `tests/api/test_health.py` |
| AT-061 | Partly: lightweight secret check only; gitleaks is not installed | `test_env_files_are_git_ignored_and_example_has_no_secret`, `test_local_secrets_do_not_appear_in_source_files` |

## 5. Verification log

| Check | Command | Result |
|---|---|---|
| Fresh migration (dev DB) | `alembic upgrade head`, `alembic current` | `0001 (head)` |
| Model/migration drift | `alembic check` | "No new upgrade operations detected." |
| Seed idempotency | `python -m scripts.seed_demo_data` ×2 | 1st run: 40 inserted. 2nd run: 0 inserted, 40 skipped |
| Test suite | `python -m pytest` | **130 passed, 0 failed, 0 skipped** (1 third-party deprecation warning) |
| Clean-environment install | New venv + `pip install -r requirements-dev.txt` + `pytest` + `pip check` | 130 passed. No broken requirements |
| Lint | `ruff check .` | All checks passed |
| Live server | `uvicorn app.main:app` + HTTP calls to health, login, own/other claim, benefits, `/docs` | 200 / 200 / 200 / 404 / 200 / 200 |
| Docker Compose | — | **Not verified** (Docker not installed) |
