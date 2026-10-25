# Phase 5 — API and Workflow Contracts

Base path `/api/v1`. Every endpoint requires a bearer token, and errors use the standard `{"error": {code, message, details, request_id}}` envelope. All data is synthetic (`data_environment: "SYNTHETIC_PROTOTYPE"`).

## 1. `POST /support-cases`

Permission `cases:create` (MEMBER, PROVIDER).

Headers: `Idempotency-Key: <UUID>` (**required**).

```json
{
  "category": "CLAIM_INQUIRY",
  "summary": "Member needs help with claim SYN-CLM-2026-000101.",
  "escalation_reason": "USER_REQUESTED_HUMAN",
  "related_session_id": "8f…",
  "related_claim_number": "SYN-CLM-2026-000101"
}
```

| Field | Rule |
|---|---|
| `category` | `BENEFITS_QUESTION`, `CLAIM_INQUIRY`, `DOCUMENT_ISSUE`, `PA_READINESS_REVIEW`, `KNOWLEDGE_GAP`, `TECHNICAL_ISSUE`, `OTHER` |
| `summary` | 10–2000 characters |
| `escalation_reason` | `NO_ADEQUATE_ANSWER`, `CONFLICTING_INFORMATION`, `USER_REQUESTED_HUMAN`, `DOCUMENT_REQUIRES_REVIEW`, `TOOL_FAILURE`, `APPROVAL_REQUIRED`, `OUT_OF_SCOPE`, `USER_INITIATED` (default) |
| `related_session_id`, `related_claim_number` | optional; must belong to the caller |
| any other field (`status`, `case_number`, `created_by_user_id`, …) | 422 |

| Response | Meaning |
|---|---|
| 201 `CaseDetail` | created, status `OPEN` |
| 200 `CaseDetail` | replay: same key and same body, same case, nothing new |
| 400 `IDEMPOTENCY_KEY_REQUIRED` | header missing or not a UUID |
| 403 `FORBIDDEN` | role lacks `cases:create` |
| 404 `RESOURCE_NOT_FOUND` | related session or claim not owned (audited `ACCESS_DENIED`) |
| 409 `IDEMPOTENCY_KEY_REUSED` | same key, different body |
| 500 `CASE_CREATION_FAILED` | write failed; nothing persisted |

`CaseDetail`: `case_id`, `case_number` (`CASE-YYYY-NNNNNN`), `category`, `status`, `escalation_reason`, `summary`, `related_session_id`, `related_claim_number`, `resolution_note`, `version`, `events[]` (`event_type`, `from_status`, `to_status`, `note`, `actor_display_name`, `created_at`), `created_at`, `updated_at`.

## 2. `GET /support-cases` and `GET /support-cases/{case_id}`

Permission `cases:read:own`. Only cases the caller created are listed. `?status=OPEN&status=RESOLVED` filters by status, and `limit` accepts 1–100 (default 20). Another user's case returns 404 and writes an `ACCESS_DENIED` audit row.

## 3. `GET /authorization/requirements/{procedure_code}`

Permission `requirements:read`. Path pattern `^SYN-PROC-[A-Z0-9-]{2,30}$` (otherwise 422). Returns the active requirement set with each requirement's verified source passage (`source: null` when the passage can't be found in the active document; `evidence_status` is then `PARTIALLY_SUPPORTED`) and the disclaimer "Documentation requirements only… not an authorization approval…". Unknown code, or a source document that isn't ACTIVE, ingested and visible to the caller's audience: 404. Audited as `REQUIREMENTS_LOOKUP`.

## 4. `POST /chat` additions

`ChatResponse` (and each assistant message in `GET /chat/sessions/{id}`) gains:

```json
"tool_executions": [{"tool_name": "get_claim_status", "result_status": "SUCCEEDED", "summary": "1 claim record(s) retrieved"}],
"records": [{"kind": "claims", "data": {"claims": [ … ]}}]
```

- `result_status`: `SUCCEEDED`, `CONFIRMATION_REQUIRED`, `INVALID_ARGUMENTS`, `PERMISSION_DENIED`, `NOT_FOUND`, `EXECUTION_ERROR`, `CALL_LIMIT_REACHED`.
- `records[].kind`: `claims`, `plan_benefits`, `requirements`, `support_case_proposal`.
- `answer_type` is `TOOL_RESULT` when a tool supplied the answer; `evidence_status` is `VERIFIED_RECORD` when only records (no citations) back it.
- A `CREATE_SUPPORT_CASE` proposed action carries `prefill`: `category`, `summary`, `escalation_reason`, `related_session_id`, `idempotency_key` (server-issued). The client sends these to `POST /support-cases` only after the user confirms.

## 5. Tool contract (model-facing)

`anthropic_tool_definitions()` produces `{name, description, input_schema}` from the Pydantic input models with `additionalProperties: false`. The tool result sent back to the model is `{"status": …, "result": <validated output or {status, error}>}`, with `is_error` set for any non-success result. The loop allows at most `TOOL_MAX_CALLS_PER_MESSAGE` (3) executions and `max_calls + 2` model rounds. After that the request fails with 503 `AI_SERVICE_UNAVAILABLE`; no partial answer is invented.

## 6. Data model (migration `0003`)

| Table | Key constraints |
|---|---|
| `support_cases` | `case_number` unique, matching `CASE-\d{4}-\d{6}`; CHECKs on status/category/escalation_reason; summary 10–2000; unique `(created_by_user_id, idempotency_key)`; FKs to user, session, claim |
| `support_case_events` | FK case; `event_type`, `from_status`, `to_status`, actor |
| `pa_requirement_sets` | partial unique index: one active set per `procedure_code`; `aliases text[]`; `source_document_key` |
| `pa_requirements` | FK set; `requirement_code`, `description`, `is_mandatory`, `rule_type`, `rule_params`, `source_phrase`, `display_order` |
| `tool_invocations` | `message_id`, `user_id`, `tool_name`, `requested_by` (`router`/`llm`), `arguments_redacted` jsonb, `result_status`, `latency_ms` |
| `conversation_messages` | new jsonb columns `tool_executions`, `records` |
| sequence | `support_case_number_seq` |

`alembic check` reports no drift. The test suite runs a downgrade/upgrade round trip.

## 7. Audit events added

`TOOL_INVOKED` (SUCCESS/DENIED/FAILURE), `SUPPORT_CASE_CREATED` (same transaction as the case), `SUPPORT_CASE_CREATE_FAILED`, `REQUIREMENTS_LOOKUP`, plus `ACCESS_DENIED` with `resource_type` `tool`, `support_case`, `conversation_session` or `claim`. Metadata keys are allowlisted; summaries, questions and argument values other than codes are never audited.
