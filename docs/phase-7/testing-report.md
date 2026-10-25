# Phase 7 — Testing Report

Recorded on 2026-10-26 on Windows 11 with Python 3.12, PostgreSQL 18 (local cluster) and Node/Vitest. Only executed results are reported here.

## 1. Results

| Suite | Command | Result |
|---|---|---|
| Backend lint | `ruff check app tests scripts` | All checks passed |
| Backend tests | `python -m pytest` (from `backend/`) | **428 passed**, 0 failed, 0 skipped (64 new) |
| Migration | `alembic upgrade head`; dev `downgrade 0004` → `upgrade head`; `alembic check`; the suite rebuilds the test DB from migrations | Clean, no drift |
| Frontend | `npx tsc --noEmit` · `npm run lint` · `npx vitest run` | 0 errors · 0 problems · **93 passed** (9 new; 3 obsolete "not connected" tests replaced) |

## 2. New tests

**`tests/unit/test_case_workflow.py` (46):**
- every permitted transition in the doc 02 §3.1 table, with the resulting status, assignee and history event types;
- every rejected change: wrong role, not the assigned agent, invalid transition, missing `note`/`resolution_note`/`reason`, reopen window expired (15 days), terminal states, inactive or non-agent assignee, same assignee, no change;
- `allowed_actions` per role;
- the escalation policy (categories, confirmation always required, unknown conditions rejected, minimized readiness summary).

**`tests/api/test_case_review.py` (18):**
- **Full lifecycle:** member creates → agent sees it in the queue (summary view) → assign → start → request info → the member's note resumes it automatically → resolve → close. History rows are checked exactly; audit actions and metadata are checked; note text never appears in the audit log.
- **Invalid transitions:** 409 with details, a FAILURE audit row, no change in version or history.
- **Duplicates and stale versions:** a double click returns 409 `VERSION_CONFLICT` with only one ASSIGNED event, and another agent gets 404.
- **Required fields:** 422.
- **Role and field restrictions:** a member can't self-assign or assign; an agent can't assign others; server fields are rejected; other users get 404.
- **Admin assignment:** non-agent or unknown targets give 422; reassignment moves visibility between agents; the agent list is correct.
- **Member actions:** cancel; reopen refused after 14 days.
- **Scopes:** enforced (6 forbidden combinations); no cross-user listing.
- **Pagination:** a cursor walk returns every case exactly once; a bad cursor gives 422; the case-number filter works.
- **Summary view:** hides the claim, linked content and notes; the admin view is audited.
- **Phase 6 integration:**
  - the checklist's `escalation_offer` creates a linked case, and `review_state` moves to AWAITING_REVIEW and then UNDER_REVIEW;
  - the assigned agent can then open the checklist and the document's fields (`DOCUMENT_VIEWED` audited);
  - another agent gets 404, and before linking even the assigned agent gets 404.
- **Linking refusals:** someone else's checklist or document gives 404.
- **Audit API:** admin-only (3 roles get 403); filters; fixed field set; the summary text is absent; cursor paging; POST/PUT/PATCH/DELETE return 405; bad filters give 422; viewing is itself audited.
- **Metrics:** hand-computed values in an isolated March-2020 period (see dashboard-metrics.md §4); an empty period gives zeros and nulls; invalid ranges give 422; non-admins get 403.
- **Knowledge gaps:** aggregation, suppression (1-user topic hidden), by-intent counts, requirement misses, tool failures, no message text, empty period.
- **Atomicity:** a forced audit-insert failure rolls back the case change (status, version and history unchanged), and the error response contains no SQL.

**`frontend/src/pages/phase7.test.tsx` (9):**
- **Agent queue:** loads from the server; nothing is sent before confirming; after "Assign to me" the next action appears.
- **Resolve:** blocked until a resolution is entered; a 409 conflict shows "This case changed" and no "Saved".
- **Empty queue and filters:** an honest empty state; filters are sent as query parameters.
- **Member note:** sends exactly `{version, note}`.
- **Admin metrics:** rendered from the API; null shown as "—"; `unavailable` named; `"<3"` suppression shown.
- **Failures and validation:** a failed metrics call shows an alert, not numbers; an invalid date range blocks the request.
- **Audit paging and access:** "Load older" sends the cursor, with no edit or delete controls; non-admins aren't offered the dashboard.

## 3. Live end-to-end check (browser, API on port 8000, dev database)

1. **Member** (Priya) asked "Does my plan cover acupuncture?". The assistant had insufficient evidence and offered **Ask a support agent**. After confirming, the UI showed "Support case CASE-2026-000003 created", the number returned by the API.
2. **Agent** (Sam):
   - The case appeared in the unassigned queue, and opening it showed the summary view with only "Assign to me".
   - Assign → confirm → "Start work" appeared → start → **Resolve** with a resolution note.
   - The panel showed "Resolved". The history read Created (Priya) → Assigned → Status changed (In progress) → Status changed (Resolved, with the note), all by Sam Reviewer. Category Knowledge gap and reason No adequate answer came from the central escalation policy.
3. **Admin** (Alex): the dashboard (2026-09-26 to 2026-10-25 UTC) showed 3 cases created (3 from the assistant), current Open 2 / Resolved 1, 14 questions, 3 access-denied events, and latency p50 274 ms / p95 1820 ms over 14 answers.
4. **Cross-check by direct SQL** on the same database: cases by status `OPEN 2, RESOLVED 1`; created in the period 3; from chat 3; user messages 14; `ACCESS_DENIED` 3. The audit rows for CASE-2026-000003, in order, were CREATED, VIEWED, ASSIGNED (OPEN→ASSIGNED), VIEWED, STATUS_CHANGED (ASSIGNED→IN_PROGRESS), VIEWED, STATUS_CHANGED (IN_PROGRESS→RESOLVED), VIEWED. **All match the dashboard.**

## 4. Not verified / limitations

- **Untested combinations:** concurrent PATCHes from two processes were tested via the version check (sequential stale request), not a true parallel race. The `SELECT … FOR UPDATE` row lock is in place but not load-tested.
- **Untested UI paths:** the admin assign/cancel flows in the UI are covered by the shared panel's tests and the API tests, not by a separate browser run. Responsive layout was not checked on real devices.
- **Live integrations:** OCR and LLM remain unverified (Phases 4–6).
- **Not implemented:** feedback metrics (no feedback feature), and the retention or cleanup jobs for cases, documents and audit data (Phase 8).
