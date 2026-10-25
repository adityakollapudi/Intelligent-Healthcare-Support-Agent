# Phase 7 — Audit Architecture

The audit trail is the existing `audit_logs` table (Phase 2) written through `AuditService`. Phase 7 adds case-workflow events and a read-only query API. Case history (`support_case_events`) is a separate, user-facing record of the case. The audit log is the accountability record. Neither is a metrics store.

## 1. Event schema (`audit_logs`, doc 05 §2.24)

`id` (bigint identity, ordered), `occurred_at` (DB `now()`, UTC), `request_id` (matches `X-Request-ID` and error responses), `actor_user_id`, `actor_role` (role at the time), `action`, `resource_type`, `resource_ref` (a public reference or UUID, never content), `outcome` (`SUCCESS`/`DENIED`/`FAILURE`), `reason_code`, `metadata` (jsonb).

- **Append-only at the database level:** a trigger installed by migration 0001 rejects UPDATE/DELETE.
- **No modifying API:** there is no route that edits or deletes audit rows. `POST/PUT/PATCH/DELETE /admin/audit-events` return 405 (tested).

## 2. Events (Phase 7 additions in bold)

| Action | Outcome | Written |
|---|---|---|
| `SUPPORT_CASE_CREATED` | SUCCESS | Same transaction as the case and its CREATED event |
| `SUPPORT_CASE_CREATE_FAILED` | FAILURE | After the rollback |
| **`SUPPORT_CASE_ASSIGNED` / `SUPPORT_CASE_UNASSIGNED`** | SUCCESS | Same transaction as the change (metadata `from_status`, `to_status`) |
| **`SUPPORT_CASE_STATUS_CHANGED`** | SUCCESS | Same transaction (metadata `from_status`, `to_status`) |
| **`SUPPORT_CASE_NOTE_ADDED`** | SUCCESS | Same transaction; **the note text is never audited** |
| **`SUPPORT_CASE_UPDATE_REJECTED`** | FAILURE | Rejected change (reason: `VERSION_CONFLICT`, `INVALID_STATUS_TRANSITION`, `FORBIDDEN`, `MISSING_FIELD`, `INVALID_ASSIGNEE`, `DATABASE_ERROR`…) after a rollback, so no success row exists |
| **`SUPPORT_CASE_VIEWED`** | SUCCESS | An agent or admin opened a case |
| **`DOCUMENT_VIEWED`**, **`READINESS_CHECKLIST_VIEWED`** | SUCCESS | Case-linked access by the assigned agent |
| **`ADMIN_METRICS_VIEWED`**, **`KNOWLEDGE_GAPS_VIEWED`**, **`AUDIT_EVENTS_VIEWED`** | SUCCESS | After the query succeeded |
| `ACCESS_DENIED` | DENIED | Every refused read or write (reason `ROLE_NOT_PERMITTED`, `NOT_OWNER`, `NOT_EXISTS`, `NOT_ASSIGNED`) |
| Phases 2–6 events | — | Logins, lookups, tools, documents, readiness (unchanged) |

## 3. Transaction behavior

- **Mandatory write events** (case created or changed) use `add_to_transaction`. The audit row commits **with** the business change or not at all. If the audit insert fails, the case change rolls back as well, and the client gets a generic 500 (tested: status and version unchanged, no history row).
- **Rejections and denials** are recorded with `record()` in their own transaction after the business transaction is rolled back. A rejected transition can never appear as a success.
- **If `record()` fails:** it raises `AuditWriteError` (fail-closed), so the request fails rather than silently losing a required event.

## 4. Access (`GET /api/v1/admin/audit-events`)

- **Permission:** `audit:read` (ADMIN only). Any other role gets 403 plus `ACCESS_DENIED`.
- **Filters** (validated): `from`, `to` (timestamps), `action` (`^[A-Z_]{3,60}$`), `outcome` (enum), `actor_user_id`, `resource_type` (`^[a-z_]{2,40}$`), `resource_ref` (≤80), `limit` 1–100, and `cursor` (the last seen `id`, keyset, newest first).
- **Response fields:** `id`, `occurred_at`, `request_id`, `actor {id, display_name, role}`, `action`, `resource_type`, `resource_ref`, `outcome`, `reason_code`, `metadata`.

## 5. Data minimization

- **Allowlisted metadata:** keys are allowlisted in `AuditService.ALLOWED_METADATA_KEYS`, and an unknown key raises at the call site (tested since Phase 2). Phase 7 added `from_status`/`to_status` only.
- **Never recorded:** case summaries, notes, resolution text, message content, document values, filenames of other users, tokens or prompts. A test asserts that a case summary doesn't appear in the audit API output.

## 6. Limitations (stated plainly)

- **Not tamper-proof:** the table is append-only for the application (trigger plus no API). A database superuser can still alter it. There is no hash chain or external write-once store.
- **Retention isn't enforced:** NFR-021's 365-day purge job isn't implemented (Phase 8).
- **No export:** there is no audit export or alerting.
- **Not every read is audited:** reads by a record's own creator (for example a member viewing their own case) aren't audited, per doc 06.
