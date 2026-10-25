# IHSA Frontend (Phase 3)

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
| Assistant (chat) | UI ready. Sends nothing until `POST /chat` exists (Phase 4) |
| Documents | File selection and client checks work. Upload is disabled until Phase 6 |
| PA readiness, support cases, case queue, admin dashboard | UI ready, showing an honest "not connected" state (Phases 5–7) |

## Troubleshooting
| Symptom | Fix |
|---|---|
| Blank page, console says `VITE_API_BASE_URL is not set` | Create `.env.local` from `.env.example` and restart `npm run dev` |
| "Service unreachable" badge, or "Can't reach the IHSA service" | Start the backend. Check the URL in `.env.local` |
| Requests blocked by CORS | Open `http://localhost:5173`, or add your origin to the backend's `CORS_ORIGINS` |
| Signed out after refreshing the page | Expected: the access token is held only in memory (decision D-09). Sign in again |
| "Too many requests" on sign-in | The backend locks an email for 15 minutes after 5 failed attempts |
| Port 5173 already in use | Stop the other process. The port is fixed to match the CORS setting |
