# IHSA Frontend (Phases 3–7)

React + TypeScript + Vite user interface for the **Intelligent Healthcare Support Agent**, an internship prototype that uses **synthetic data only** and is not an Evernorth product. Architecture and decisions are in [`docs/phase-3/frontend-implementation.md`](../docs/phase-3/frontend-implementation.md).

## Prerequisites
- Node.js 20+ (developed with Node 24.13, npm 11.6)
- The IHSA backend running (see [`backend/README.md`](../backend/README.md)): PostgreSQL started, migrations applied, demo data seeded, `uvicorn app.main:app` on port 8000

## Setup and run
```powershell
cd frontend
npm ci                                  # exact versions from package-lock.json
Copy-Item .env.example .env.local       # bash: cp .env.example .env.local
npm run dev                             # http://localhost:5173
```
Open **http://localhost:5173** (not 127.0.0.1): the backend's default `CORS_ORIGINS` allows only `http://localhost:5173`. Sign in with a seeded demo account. The emails are listed in the backend README, and the password is `SEED_USER_PASSWORD` from `backend/.env`.

## Environment (`.env.local`; every `VITE_*` value is public, so never put secrets here)
| Variable | Default in example | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000/api/v1` | Backend API base. Required: the app throws a clear error at startup if it's missing |
| `VITE_API_TIMEOUT_MS` | `15000` | Client request timeout |

## Commands
| Command | What it does |
|---|---|
| `npm run dev` | Development server with hot reload |
| `npm run build` | Typecheck + production build to `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint (TypeScript, React hooks, jsx-a11y) |
| `npm test` | Vitest + Testing Library (jsdom). The network is stubbed per test, so no backend is needed |
| `npm run test:watch` | Tests in watch mode |

## What works today
| Area | Status |
|---|---|
| Sign in / sign out / session expiry | **Connected**: `POST /auth/login`, `GET /auth/me`, `POST /auth/logout` |
| Role-aware navigation | **Connected**: built from the `permissions` list returned by `/auth/me` |
| Service status indicator | **Connected**: `GET /health`, checked every 60 s |
| My claims (list, status filter, lookup) | **Connected**: `GET /claims`, `GET /claims/{claim_number}` |
| Plan benefits (own plan; staff search; category filter) | **Connected**: `GET /benefits/{plan_code}` |
| Assistant (chat) | **Connected** (Phase 4): `POST /chat`, `GET /chat/sessions`, `GET /chat/sessions/{id}`. Shows answers, evidence status, citations, "Recent conversations", and actions. Actions whose backend isn't built yet appear disabled |
| Documents | **Connected** (Phase 6): upload (multipart `POST /documents`), list, analyze, and poll for results; page-level reading status, an extracted-field table (value, check status, source page, OCR confidence) and warnings. Upload success is shown separately from analysis success |
| PA readiness | **Connected** (Phase 6, providers): choose a requirement set and analyzed documents, then view the backend checklist (four statuses, evidence, requirement source, reviewer summary) with a prominent "not an authorization decision" notice |
| Assistant tool results (Phase 5) | Claim, benefit and requirement records render as cards from the response `records`; each lookup shows a badge. A proposed support case opens a confirmation dialog and is created only on confirm (`POST /support-cases` with the server-issued `Idempotency-Key`); the case number appears only after the backend returns it |
| Support cases | **Connected** (Phase 5): list with status filter, case detail with history, and a "New case" form with review and confirmation |
| Case queue (agents) | **Connected** (Phase 7): unassigned queue and "assigned to me" with server-side filters and paging; a case panel with history, linked checklist and documents, and only the actions the backend allows (each confirmed, version-checked) |
| Admin dashboard | **Connected** (Phase 7): metrics from `GET /admin/metrics` for a UTC date range, knowledge gaps, a read-only audit log, and all cases with assign/cancel. Failed requests show errors, never zeros; missing data shows "—" |

## Troubleshooting
| Symptom | Fix |
|---|---|
| Blank page, console says `VITE_API_BASE_URL is not set` | Create `.env.local` from `.env.example` and restart `npm run dev` |
| "Service unreachable" badge, or "Can't reach the IHSA service" | Start the backend. Check the URL in `.env.local` |
| Requests blocked by CORS | Open `http://localhost:5173`, or add your origin to the backend's `CORS_ORIGINS` |
| Signed out after refreshing the page | Expected: the access token is held only in memory (decision D-09). Sign in again |
| "Too many requests" on sign-in | The backend locks an email for 15 minutes after 5 failed attempts |
| Port 5173 already in use | Stop the other process. The port is fixed to match the CORS setting |
