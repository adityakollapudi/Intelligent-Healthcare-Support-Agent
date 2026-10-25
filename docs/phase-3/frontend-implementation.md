# Phase 3 — Frontend Implementation

## 1. Starting point
- No frontend existed. The backend (Phase 2) exposes `GET /health`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `GET /claims`, `GET /claims/{claim_number}` and `GET /benefits/{plan_code}`. Types were written from `backend/app/schemas/*`.
- Every other Phase 1 endpoint (chat, documents, readiness, cases, admin) is **not implemented**, so the frontend never calls it.

## 2. Stack and dependencies
React 18.3, TypeScript 5.7 (strict, `noUncheckedIndexedAccess`), Vite 6.4.5, and React Router 7.18.4, upgraded from 6.x to clear two router advisories. `npm audit --omit=dev` reports **0 vulnerabilities** in runtime dependencies. Styling is plain CSS with design tokens. Tests use Vitest 3.2.7, Testing Library and jsdom; lint uses ESLint 9.39 with typescript-eslint, react-hooks and jsx-a11y. All versions are pinned exactly.

**Remaining dev-only advisories:** vitest ≤ 4.1 and its `tinypool` dependency (one moderate, two critical). Fixing them requires Vitest 5, a breaking upgrade that probably also needs Vite 7. They affect only the local test runner, which executes the project's own test files; nothing ships to the browser. This is tracked for Phase 8.

These were deliberately left out: a component library, a server-state library (TanStack Query), Redux, and a charting library. The current data needs are a few request/response screens, which a small `useRequest` hook covers. Revisit for Phase 7's dashboard if needed.

## 3. Structure
```
frontend/src/
  app/          App.tsx (providers + routes), navigation.ts (role-aware nav), guards.tsx
  components/   ui.tsx (Button, TextField, Alert, Loading/Empty/ErrorState, FeatureUnavailable, PageHeader, StatusBadge)
                status.tsx (claim/checklist/field/evidence status → badge), ConfirmDialog, SourceCitation,
                FileDropzone (+ checkFile), Checklist (ChecklistView, ChecklistLegend), layout/ (AppLayout, HealthIndicator)
  features/     auth/session.tsx (SessionProvider), chat/chat-state.tsx (ChatProvider)
  hooks/        useRequest.ts (abort-on-rerun, stale-result protection)
  lib/          config.ts, api-client.ts, errors.ts, validators.ts, features.ts, format.ts
  services/     index.ts (health, auth, claims, benefits, chat boundary)
  pages/        Login, Chat, Claims, Benefits, Documents, PreparedPages (readiness, cases, agent, admin, provider workspace), StatusPages
  styles/       tokens.css, app.css
  test/         fetch-mock.ts, render.tsx, setup.ts
```

## 4. Design system
CSS custom properties in `tokens.css` define the palette (navy `#0b2340` navigation, teal `#0b6e6e` primary actions, near-white surfaces, red/amber/green status colors), a type scale, a 4–32 px spacing scale and one radius. Status is always icon + text (`StatusBadge`), never color alone. Focus is a 3 px visible outline, and motion respects `prefers-reduced-motion`.

## 5. Routes and role-aware navigation
| Route | Shown when the user holds | Status |
|---|---|---|
| `/login` | — | Connected |
| `/provider` | `readiness:create` | Links to tasks |
| `/chat` | `chat:use` | UI ready (Phase 4) |
| `/claims` | `claims:read:own` | Connected |
| `/benefits` | `benefits:read:own` or `benefits:read:any` | Connected |
| `/documents` | `documents:upload` | Client checks only (Phase 6) |
| `/readiness` | `readiness:create` | UI ready (Phase 6) |
| `/cases` | `cases:read:own` | UI ready (Phase 5/7) |
| `/agent` | `cases:read:queue` | UI ready (Phase 7) |
| `/admin` | `metrics:read` | UI ready (Phase 7) |
| any other path | — | Not-found page. A known route the role can't use shows the access-denied page |

Home page by role: Member → `/chat`, Provider → `/provider`, Support agent → `/agent`, Admin → `/admin`. The navigation reads the `permissions` array from `GET /auth/me`, the same catalogue as `backend/app/authz/permissions.py`. **These checks are UX only**; the backend authorizes every request.

## 6. Authentication and session
- Login calls `POST /auth/login`, keeps the access token **in memory only** (a React ref, never `localStorage`), then loads identity and role from `GET /auth/me`.
- A page reload therefore signs the user out. That's the accepted trade-off in decision D-09; the alternative is an HttpOnly refresh cookie added on the backend.
- Any 401 on a request that carried a token ends the session. The app then redirects to `/login?expired=1` with a notice, and after re-login it returns to the same page. Only same-app paths (`/…`, not `//…`) are accepted as return targets.
- An explicit sign-out calls `POST /auth/logout` (revoking the token server-side) and does **not** carry the previous user's page to the next user. The chat state is cleared whenever the user changes.
- No development bypass or client-chosen role exists. Credentials come only from the backend seed.

## 7. API layer and errors
- `lib/api-client.ts` is the only `fetch` caller. It builds URLs from `VITE_API_BASE_URL`, attaches the bearer token, applies a timeout (`VITE_API_TIMEOUT_MS`), supports caller `AbortSignal`s, sets `credentials: "omit"`, parses JSON safely (empty and non-JSON bodies included), and runs an optional runtime shape check (`lib/validators.ts`). It never logs tokens or bodies.
- All failures become an `ApiError` with `kind` (`http`, `network`, `timeout`, `aborted`, `invalid_response`), `status`, `code`, `requestId`, `details` and `retryAfterSeconds`. `describeError()` maps each to a user message and says whether a retry makes sense (401, 403, 404, 422, 429, 500, 503 are handled distinctly). State-changing requests are never retried automatically.
- `lib/features.ts` records which backend capabilities exist. Screens for missing services render `FeatureUnavailable`, which names the endpoint and phase. Flip a flag only when the endpoint really exists.

## 8. State management
- Server data uses local component state plus `useRequest`: a new request aborts the previous one, and stale or unmounted results are ignored.
- Session and chat are React contexts, kept in memory only.
- Nothing about claims, benefits, documents or messages is written to browser storage.

## 9. Screens
| Screen | Behavior |
|---|---|
| Login | Labeled fields, client validation, show/hide password, busy state, generic failure message, rate-limit message with wait time, session-expiry notice |
| Assistant | Message list (text-only rendering), composer (Enter sends, Shift+Enter adds a line, 4,000-char limit), suggestions per role, confirmation before clearing. The draft survives navigation. **While `features.chat` is off, Send shows "Not sent" and keeps the text.** With the flag on (tested), it calls `POST /chat` and renders answers, evidence status and backend citations; on failure it restores the question and offers retry |
| My claims | List from `GET /claims` with status filter and "Load more" (cursor). Lookup validates `SYN-CLM-YYYY-NNNNNN`, then calls `GET /claims/{n}`. 404 → "No claim found on your account" (doesn't reveal other members' claims). The card shows the status meaning plus dates |
| Plan benefits | Members: their own plan from `/auth/me` loads automatically (no search box). Staff: plan-code search. Category filter re-queries with `?benefit_category=`. Missing values show "Not listed" (not a coverage decision). Source shows "Not linked yet" until Phase 4 |
| Documents | Drag-and-drop or picker. Client checks extension, browser MIME/extension match, empty file and 10 MB limit (labeled as usability only). Upload is disabled with a stated reason, and the file stays on the device |
| PA readiness | Non-approval disclaimer, legend for `SATISFIED` / `MISSING` / `UNREADABLE` / `NEEDS_MANUAL_REVIEW`, empty checklist state. `ChecklistView` is ready for real results |
| Support cases / Case queue / Admin | Availability notice and empty states. **No sample cases or metrics are shown** |
| Access denied / Not found | Clear messages with a link home |

## 10. Accessibility and responsive behavior
- Accessibility:
  - semantic landmarks and a skip link
  - one `h1` per page
  - labels plus `aria-describedby` hints and errors
  - `aria-invalid`, and `aria-live` on results and status
  - a dialog focus trap with Escape to close and focus restored afterwards
  - visually hidden context on "View" buttons
  - table captions
- Breakpoints:
  - ≤ 1100 px: two-column pages stack.
  - ≤ 860 px: the sidebar becomes an off-canvas drawer (toggle with `aria-expanded`, Escape and the backdrop close it).
  - ≤ 640 px: tables become labeled stacked cards.
  - ≤ 520 px: the top bar compacts.
- Long IDs wrap (`overflow-wrap:anywhere`), dialogs fit the viewport, and touch targets are ≥ 40 px.

## 11. Testing (`npm test`)
64 tests in 4 files, all passing:
- `lib/api-client.test.ts`: URL building, token handling, error normalization, Retry-After, 401 session expiry, network/non-JSON/invalid/204, cancellation, timeout, and no secrets in console output.
- `app/App.test.tsx`:
  - login validation, wrong credentials, rate limiting, password toggle
  - session expiry and return to the same page; sign-out with no carry-over to the next user
  - navigation per role (all 4 roles); every visible link renders a screen
  - access denied, not found, back/forward, mobile drawer, live health status
- `pages/pages.test.tsx`:
  - claims: list, lookup, validation, 404, 503 retry, status filter via the API
  - benefits: own plan, category query, staff not-found
  - chat: unavailable path, validation, draft persistence, confirm dialog, an enabled-service test (citations, HTML shown as text), failure recovery
  - prepared screens: no API calls and no numbers
- `components/components.test.tsx`: file checks, dropzone, badges, citations, dialog focus trap.

Manual verification in a browser against the **real backend** (Chromium, 1024×768 and 375×812):
- member login (wrong, then correct password)
- chat "Not sent" behavior
- claims list, own lookup, another member's claim → 404, malformed number
- own-plan benefits; provider navigation, inactive-plan 404, Bronze lookup
- the readiness page
- the mobile drawer, with no horizontal overflow at 375 px
- backend stopped → "Can't reach the IHSA service" with Try again

Two defects found this way were fixed:
- a stale lookup result stayed visible next to a validation error
- the previous user's page carried over after sign-out

## 12. Known limitations
- Token in memory: a reload signs out (D-09).
- No automated end-to-end suite against the real backend yet (Playwright is planned for Phase 8). Real-backend checks so far were manual.
- No automated contrast/axe audit yet (Phase 8, AT-062). Contrast was chosen against WCAG AA values but not tool-measured.
- Benefit sources and the chat, documents, readiness, cases and admin features await their backend phases.
- The health indicator polls every 60 s, so an outage may take up to a minute to show (individual requests report failures immediately).

## 13. Integration points for later phases
| Phase | Ready now | To do when the backend lands |
|---|---|---|
| 4 (RAG chat) | `ChatResponse`/`Citation` types, `chatService.send`, `ChatProvider` (session ID, client message ID, retry), `SourceCitationList`, evidence badges | Set `features.chat.available = true`. Add session history (`GET /chat/sessions`), feedback buttons and proposed-action buttons |
| 5 (tools, cases) | `ProposedAction` type, `ConfirmDialog`, cases page shell | Case services + create flow with `Idempotency-Key`; show a case number only from a 201/200 response |
| 6 (documents, readiness) | `FileDropzone`/`checkFile`, `FIELD_STATUS_META`, `ChecklistView`, `READINESS_DISCLAIMER` | Upload (multipart), job polling, extracted-field table, readiness request and reviewer summary |
| 7 (agent, admin) | Route guards, page shells, table styles | Queue/detail with `allowed_transitions` and `version` conflicts; metrics and audit tables with an equivalent data table for any chart |
| 8 | Test helpers (`mockApi`, `renderSignedIn`) | Playwright E2E against the real stack, axe checks, CI |
