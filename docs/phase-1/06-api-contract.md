# 06 — API Contract

Interface contracts only; routes are implemented from Phase 2 onward. FastAPI will publish an OpenAPI document that must match this contract.

---

## 1. Conventions

| Topic | Convention |
|---|---|
| Base path | `/api/v1` |
| Format | JSON (`application/json; charset=utf-8`) except file upload (`multipart/form-data`) |
| Authentication | `Authorization: Bearer <access_token>` on all routes except `GET /health` and `POST /auth/login`. Missing/invalid/expired/revoked token → 401 `UNAUTHENTICATED` |
| Authorization | Each route lists a required permission (doc 03). Role failure → 403 `FORBIDDEN`; scope/ownership failure → 404 `RESOURCE_NOT_FOUND` |
| Validation | Pydantic models with `extra="forbid"`: unknown fields → 422 `VALIDATION_ERROR`; server-controlled fields → 422 `FIELD_NOT_ALLOWED` |
| Request ID | Client may send `X-Request-ID` (UUID); otherwise server generates. Always echoed in response header and error body |
| Timestamps | ISO 8601 UTC with `Z`, e.g. `2026-10-25T14:03:11Z`. Dates as `YYYY-MM-DD`. Client renders in the user's local timezone |
| Pagination | Cursor-based: `?limit=` (1–100, default 20) and `?cursor=`; response `{ "items": [...], "next_cursor": "…" \| null }` |
| Sorting | Fixed per endpoint (documented) to avoid arbitrary-column sorting |
| Idempotency | `POST /support-cases` requires `Idempotency-Key: <uuid>`. `POST /chat` accepts `client_message_id` for dedup. `POST /documents/{id}/analyze` returns the existing active job if one is `QUEUED`/`RUNNING` |
| Concurrency | `PATCH /support-cases/{case_id}` requires body `version`; mismatch → 409 `VERSION_CONFLICT` |
| Status codes | 200 OK, 201 Created, 202 Accepted, 204 No Content, 400 bad request shape, 401, 403, 404, 409, 413, 415, 422, 429 (with `Retry-After`), 500, 503 |
| Versioning | Breaking changes only in a new prefix (`/api/v2`). Additive fields are non-breaking; clients must ignore unknown response fields |
| CORS | Only the configured frontend origin |
| Synthetic marker | Responses with record data include `"data_environment": "SYNTHETIC_PROTOTYPE"` at the top level |

---

## 2. Shared Schemas

```jsonc
// Citation
{
  "marker": "C1",
  "chunk_id": "8b6f0c0e-2c4b-4b7a-9c55-0d7d1e7d0a11",
  "document_id": "5d0c…",
  "document_title": "Synthetic Imaging Prior Authorization Guide",
  "document_type": "PA_REQUIREMENTS",
  "document_version": "2.0",
  "effective_date": "2026-01-01",          // null → UI shows "Effective date not stated"
  "section_heading": "Lumbar MRI > Required documentation",
  "page_start": 3, "page_end": 3,
  "excerpt": "Requests must include documentation of at least six weeks of conservative therapy…" // from stored chunk, ≤ 400 chars
}

// ToolExecutionSummary
{ "tool_name": "get_claim_status", "result_status": "SUCCEEDED", "summary": "Claim record retrieved" }

// ProposedAction
{
  "action_type": "CREATE_SUPPORT_CASE",   // CREATE_SUPPORT_CASE | UPLOAD_DOCUMENT | START_READINESS_CHECK | VIEW_CLAIM | VIEW_CASE
  "label": "Ask a support agent",
  "requires_confirmation": true,
  "prefill": { "category": "BENEFITS_QUESTION", "escalation_reason": "NO_ADEQUATE_ANSWER",
               "summary": "Member asked about acupuncture coverage; no matching document found.",
               "related_session_id": "…" }
}

// Escalation
{ "offered": true, "reason": "NO_ADEQUATE_ANSWER" }

// Page<T>
{ "items": [ /* T */ ], "next_cursor": null }
```

---

## 3. Endpoints

### 3.1 System

#### `GET /api/v1/health`
| Item | Detail |
|---|---|
| Purpose | Liveness + DB connectivity |
| Auth | None (public) |
| Response 200 | `{ "status": "ok", "checks": { "api": "ok", "database": "ok" }, "time": "2026-10-25T14:03:11Z" }` |
| Response 503 | `{ "status": "degraded", "checks": { "api": "ok", "database": "unavailable" }, "time": "…" }` |
| Must not expose | Versions, hostnames, connection strings, model names, configuration, counts |
| Side effects / audit | None |
| FRs / tests | FR-036 / AT-058 |

### 3.2 Authentication (added: required by FR-001)

#### `POST /api/v1/auth/login`
| Item | Detail |
|---|---|
| Auth | None. Rate limited (NFR-020) |
| Request | `{ "email": "priya.member@example.test", "password": "••••••••" }` (email ≤ 254, password 8–128) |
| Response 200 | `{ "access_token": "eyJ…", "token_type": "bearer", "expires_in": 1800, "user": { "id": "…", "display_name": "Priya Synthetic", "role": "MEMBER" } }` |
| Errors | 401 `INVALID_CREDENTIALS` (same for unknown email, wrong password, disabled account); 429 `RATE_LIMITED`; 422 |
| Audit | `AUTH_LOGIN_SUCCEEDED` / `AUTH_LOGIN_FAILED` (no password, email hashed in metadata) |
| FRs / tests | FR-001 / AT-001, AT-002 |

#### `POST /api/v1/auth/logout`
Auth: any. Revokes token `jti`. 204. Audit `AUTH_LOGOUT`. FR-001 / AT-003.

#### `GET /api/v1/auth/me`
Auth: any. 200 `{ "id", "display_name", "email", "role", "organization": { "id", "name" } | null, "member": { "member_number", "plan_code" } | null, "permissions": ["chat:use", …] }`. `permissions` is for UI rendering only. FR-001, FR-002 / AT-001.

### 3.3 Chat

#### `POST /api/v1/chat`
| Item | Detail |
|---|---|
| Purpose | Process one user message |
| Auth / permission | `chat:use`; `session_id` must be owned by caller |
| Request | `{ "session_id": "uuid \| null", "client_message_id": "uuid", "message": "string 1–4000", "context": { "document_ids": ["uuid"], "checklist_id": "uuid \| null" } }` — `context` optional; referenced items must be owned by caller |
| Response 200 | See example |
| Errors | 422 `VALIDATION_ERROR`; 404 `RESOURCE_NOT_FOUND` (session/context item); 429 `RATE_LIMITED`; 503 `AI_SERVICE_UNAVAILABLE` (user message stored, no assistant answer) |
| Side effects | Creates session (if null), user + assistant messages, citations, tool invocations; may create gap records via `gap_topic` |
| Audit | `CHAT_MESSAGE_PROCESSED` (intent, answer_type, evidence_status — no content); `KNOWLEDGE_RETRIEVAL` (document IDs, count); tool events per §5 |
| Dedup | Same `client_message_id` in the same session returns the stored response |
| FRs / tests | FR-004–FR-013, FR-017, FR-026, FR-035 / AT-007–AT-018, AT-024–AT-026, AT-043, AT-059 |

Example — grounded answer:
```json
{
  "session_id": "1f3c8d1e-7b51-4a34-8a50-3c1f0b0a9d21",
  "message_id": "a3c4…",
  "intent": "REQUIRED_DOCUMENTS",
  "answer_type": "DOCUMENT_GROUNDED",
  "evidence_status": "SUPPORTED",
  "answer_text": "For a lumbar MRI request under the synthetic imaging guide, the request should include the ordering provider's details, the requested service date, and documentation of at least six weeks of conservative therapy [C1]. A referral letter is also listed as required [C2].",
  "citations": [ { "marker": "C1", "document_title": "Synthetic Imaging Prior Authorization Guide", "document_version": "2.0", "effective_date": "2026-01-01", "page_start": 3, "page_end": 3, "section_heading": "Lumbar MRI > Required documentation", "excerpt": "…", "chunk_id": "…", "document_id": "…", "document_type": "PA_REQUIREMENTS" } ],
  "tool_executions": [ { "tool_name": "get_required_documents", "result_status": "SUCCEEDED", "summary": "6 requirements found for SYN-PROC-MRI-LUMBAR" } ],
  "proposed_actions": [ { "action_type": "START_READINESS_CHECK", "label": "Check my documents against these requirements", "requires_confirmation": false, "prefill": { "procedure_code": "SYN-PROC-MRI-LUMBAR" } } ],
  "escalation": { "offered": false, "reason": null },
  "disclaimers": ["Information is from synthetic prototype documents and is not a coverage determination."],
  "latency_ms": 4210,
  "created_at": "2026-10-25T14:03:15Z",
  "data_environment": "SYNTHETIC_PROTOTYPE"
}
```

Example — insufficient evidence:
```json
{
  "session_id": "…", "message_id": "…",
  "intent": "BENEFITS_INFO",
  "answer_type": "INSUFFICIENT_EVIDENCE",
  "evidence_status": "INSUFFICIENT",
  "answer_text": "I couldn't find information about acupuncture coverage in the documents available to me, so I can't give a verified answer. A support agent can look into this for you.",
  "citations": [], "tool_executions": [],
  "proposed_actions": [ { "action_type": "CREATE_SUPPORT_CASE", "label": "Ask a support agent", "requires_confirmation": true, "prefill": { "category": "BENEFITS_QUESTION", "escalation_reason": "NO_ADEQUATE_ANSWER", "summary": "Question about acupuncture coverage could not be answered from available documents.", "related_session_id": "…" } } ],
  "escalation": { "offered": true, "reason": "NO_ADEQUATE_ANSWER" },
  "disclaimers": [], "latency_ms": 1830, "created_at": "…", "data_environment": "SYNTHETIC_PROTOTYPE"
}
```

#### `GET /api/v1/chat/sessions` (added: FR-007)
Permission `chat:use`. Own sessions, sorted `last_message_at DESC`. Page of `{ "session_id", "title", "last_message_at", "created_at" }`. AT-012.

#### `GET /api/v1/chat/sessions/{session_id}` (added: FR-007)
Own session only (else 404). `{ "session_id", "title", "messages": [ { "message_id", "sender", "content", "intent", "answer_type", "evidence_status", "citations": [], "proposed_actions": [], "created_at" } ] }`. AT-012.

#### `POST /api/v1/chat/messages/{message_id}/feedback` (added: FR-034)
Permission `feedback:create`; message must be an ASSISTANT message in caller's session (else 404). Request `{ "rating": "HELPFUL" | "NOT_HELPFUL", "comment": "≤500 chars | null" }`. 200 upsert → `{ "message_id", "rating", "updated_at" }`. Audit `FEEDBACK_SUBMITTED`. AT-054.

### 3.4 Benefits

#### `GET /api/v1/benefits/{plan_code}`
| Item | Detail |
|---|---|
| Permission | `benefits:read:own` (MEMBER, must equal own plan) or `benefits:read:any` |
| Path | `plan_code` pattern `SYN-PLAN-[A-Z0-9-]{2,20}` (the master list's `{plan_id}` is the public plan code) |
| Query | `benefit_category` (optional) |
| Response 200 | `{ "plan_code": "SYN-PLAN-GOLD-01", "plan_name": "Synthetic Gold Plan", "plan_year": 2026, "effective_start": "2026-01-01", "effective_end": "2026-12-31", "benefits": [ { "benefit_category": "IMAGING", "service_name": "MRI (outpatient)", "in_network_cost_share": "20% coinsurance", "out_of_network_cost_share": "40% coinsurance", "prior_auth_required": true, "visit_limit": null, "limitations": "Prior authorization listed in synthetic guide.", "source": { "document_title": "Synthetic Gold Plan Benefit Guide", "document_version": "1.0", "effective_date": "2026-01-01", "page_start": 7, "chunk_id": "…" } } ], "data_environment": "SYNTHETIC_PROTOTYPE" }` |
| Errors | 404 `RESOURCE_NOT_FOUND` (unknown or, for members, not own plan); 422 bad pattern |
| Audit | `BENEFITS_LOOKUP` (plan_code, outcome) |
| FRs / tests | FR-015 / AT-021, AT-022 |

### 3.5 Claims

#### `GET /api/v1/claims` (added: needed for "list my claims" and claim-number clarification)
Permission `claims:read:own`. Own claims, sorted `submission_date DESC`. Query `status` (optional). Page of claim summaries (same fields as below minus `status_description`). AT-019, AT-044-style scope test.

#### `GET /api/v1/claims/{claim_number}`
| Item | Detail |
|---|---|
| Permission | `claims:read:own`, or `claims:read:case_linked` (SUPPORT_AGENT, claim referenced by a case assigned to caller) |
| Path | `claim_number` pattern `SYN-CLM-\d{4}-\d{6}` (the master list's `{claim_id}`) |
| Response 200 | `{ "claim_number": "SYN-CLM-2026-000101", "member_number": "SYN-M-000001", "plan_code": "SYN-PLAN-GOLD-01", "provider_name": "Maplestone Family Clinic (fictional)", "service_date": "2026-08-14", "submission_date": "2026-08-20", "status": "PENDING_INFORMATION", "status_reason_code": "PI-01", "status_description": "Additional itemized bill requested (synthetic).", "last_status_change_at": "2026-09-02T10:15:00Z", "data_environment": "SYNTHETIC_PROTOTYPE" }` |
| Not returned | Billed amount (not needed for status), internal IDs, any clinical data |
| Errors | 404 for nonexistent or not permitted (identical body); 403 for roles without either permission (PROVIDER, ADMIN); 422 bad pattern |
| Audit | `CLAIM_LOOKUP` SUCCESS / `ACCESS_DENIED` (reason `NOT_OWNER`/`NOT_EXISTS`/`ROLE_NOT_PERMITTED`) |
| FRs / tests | FR-014, FR-003 / AT-005, AT-006, AT-019, AT-020 |

### 3.6 Documents

#### `POST /api/v1/documents`
| Item | Detail |
|---|---|
| Permission | `documents:upload` |
| Request | multipart: `file` (required), `declared_purpose` (`PA_REQUEST`\|`SUPPORTING_DOCUMENT`\|`OTHER`, optional) |
| Validation | Size ≤ `MAX_UPLOAD_BYTES` (default 10 MB) → else 413; extension ∈ {.pdf,.png,.jpg,.jpeg} AND declared MIME AND magic bytes agree → else 415; PDF parses, not encrypted, ≤ 20 pages; image ≤ 25 megapixels → else 422 `MALFORMED_FILE` |
| Response 201 | `{ "document_id": "…", "original_filename": "pa_request_sample.pdf", "mime_type": "application/pdf", "size_bytes": 182311, "page_count": 2, "created_at": "…", "expires_at": "…", "latest_job": null }` |
| Server-controlled | owner, storage key, hash, expiry |
| Audit | `DOCUMENT_UPLOADED` / `DOCUMENT_UPLOAD_REJECTED` (reason code, mime, size) |
| FRs / tests | FR-018 / AT-027, AT-028, AT-029 |

#### `GET /api/v1/documents` (added: needed to select documents for readiness)
Permission `documents:read:own`. Own, non-deleted documents, newest first; each with `latest_job` status. AT-034.

#### `GET /api/v1/documents/{document_id}`
| Item | Detail |
|---|---|
| Permission | `documents:read:own` (owner) or `documents:read:case_linked` |
| Response 200 | `{ "document_id", "original_filename", "mime_type", "page_count", "created_at", "latest_job": { "job_id", "status": "COMPLETED_WITH_WARNINGS", "detected_document_type": "PA_REQUEST_FORM", "pages_text_layer": 1, "pages_ocr": 1, "ocr_mean_confidence": 81.5, "warning_count": 2, "error_code": null, "completed_at": "…", "fields": [ { "field_id", "field_name": "requested_service_date", "raw_value": "11/04/2026", "normalized_value": "2026-11-04", "validation_status": "VALID", "validation_message": null, "source_page": 1, "extraction_method": "TEXT_LAYER" }, { "field_id", "field_name": "ordering_provider_npi", "raw_value": null, "normalized_value": null, "validation_status": "ABSENT", "validation_message": "Not found in document", "source_page": null, "extraction_method": null } ] } }` |
| Errors | 404 not owned/not found |
| Audit | `DOCUMENT_VIEWED` (only for case-linked access by agents) |
| FRs / tests | FR-021 / AT-034 |

#### `POST /api/v1/documents/{document_id}/analyze`
| Item | Detail |
|---|---|
| Permission | `documents:upload` + owner |
| Request | `{}` (no client parameters in MVP) |
| Response 202 | `{ "job_id": "…", "status": "QUEUED", "created_at": "…" }` — poll `GET /documents/{id}` every 2 s (UI), up to the job timeout (120 s default) |
| Errors | 404; 409 `JOB_ALREADY_RUNNING` returns existing job ID in `details` |
| Side effects | Background extraction pipeline |
| Audit | `DOCUMENT_ANALYSIS_REQUESTED`, `DOCUMENT_ANALYSIS_COMPLETED`/`DOCUMENT_ANALYSIS_FAILED` |
| FRs / tests | FR-019, FR-020 / AT-030–AT-033, AT-055 |

### 3.7 Documentation requirements and readiness

#### `GET /api/v1/authorization/requirements/{procedure_code}` (document-requirements contract)
| Item | Detail |
|---|---|
| Permission | `requirements:read` |
| Response 200 | `{ "procedure_code": "SYN-PROC-MRI-LUMBAR", "display_name": "Lumbar spine MRI (fictional requirement set)", "version": "2.0", "requirements": [ { "requirement_code": "REQ-MRI-03", "description": "Conservative therapy duration is documented", "is_mandatory": true, "rule_type": "FIELD_PRESENT", "source": { "document_title": "Synthetic Imaging Prior Authorization Guide", "document_version": "2.0", "effective_date": "2026-01-01", "page_start": 3, "chunk_id": "…" } } ], "data_environment": "SYNTHETIC_PROTOTYPE" }` |
| Errors | 404 `REQUIREMENT_SET_NOT_FOUND` |
| Audit | `REQUIREMENTS_LOOKUP` |
| FRs / tests | FR-016 / AT-023 |
| Note | Same service as the `get_required_documents` tool (§5.3) |

#### `POST /api/v1/authorization/readiness`
| Item | Detail |
|---|---|
| Purpose | Create a documentation-readiness checklist. **Not** an approval/denial endpoint |
| Permission | `readiness:create` (PROVIDER) |
| Request | `{ "procedure_code": "SYN-PROC-MRI-LUMBAR", "document_ids": ["uuid", "uuid"], "provider_note": "optional ≤2000" }` — 1–10 documents, all owned by caller with latest job `COMPLETED`/`COMPLETED_WITH_WARNINGS` |
| Response 201 | See example |
| Errors | 403 non-provider; 404 unknown procedure/document; 409 `DOCUMENT_NOT_ANALYZED`; 422 |
| Side effects | Creates checklist, items, `checklist_documents` |
| Audit | `READINESS_CHECKLIST_CREATED` (procedure_code, readiness_status, counts) |
| FRs / tests | FR-022, FR-023, FR-024 / AT-035–AT-040 |

```json
{
  "checklist_id": "c0a1…",
  "procedure_code": "SYN-PROC-MRI-LUMBAR",
  "requirement_set_version": "2.0",
  "readiness_status": "DOCUMENTATION_INCOMPLETE",
  "review_state": "NOT_SUBMITTED",
  "counts": { "SATISFIED": 3, "MISSING": 1, "UNREADABLE": 1, "NEEDS_MANUAL_REVIEW": 1 },
  "items": [
    { "requirement_code": "REQ-MRI-01", "description": "Requested service date present", "item_status": "SATISFIED",
      "explanation": "requested_service_date = 2026-11-04 (VALID) in pa_request_sample.pdf p.1",
      "evidence": [ { "document_id": "…", "field_name": "requested_service_date", "validation_status": "VALID", "source_page": 1 } ],
      "requirement_source": { "document_title": "Synthetic Imaging Prior Authorization Guide", "document_version": "2.0", "page_start": 3, "chunk_id": "…" } },
    { "requirement_code": "REQ-MRI-02", "description": "Ordering provider identifier present", "item_status": "MISSING",
      "explanation": "Field ordering_provider_npi ABSENT in all submitted documents", "evidence": [], "requirement_source": { "…": "…" } },
    { "requirement_code": "REQ-MRI-06", "description": "Clinical rationale reviewed by staff", "item_status": "NEEDS_MANUAL_REVIEW",
      "explanation": "Rule type MANUAL_ONLY: requires human verification", "evidence": [], "requirement_source": { "…": "…" } }
  ],
  "reviewer_summary": "DRAFT — Documentation readiness summary for SYN-PROC-MRI-LUMBAR (requirement set v2.0)… ",
  "disclaimer": "This checklist reviews documentation completeness only. It is not an authorization approval, denial, medical-necessity determination, or guarantee of coverage.",
  "created_at": "…",
  "data_environment": "SYNTHETIC_PROTOTYPE"
}
```

#### `GET /api/v1/authorization/checklists` (added: provider workspace "recent checklists")
Permission `readiness:read:own`. Own checklists, `created_at DESC`. Page of `{ "checklist_id", "procedure_code", "readiness_status", "review_state", "counts", "created_at" }`. AT-038.

#### `GET /api/v1/authorization/checklists/{checklist_id}` (added: reopen checklist; reviewer access)
Permission `readiness:read:own` (creator) or `readiness:read:case_linked` (assigned agent). Same body as above. 404 otherwise. AT-038, AT-045.

### 3.8 Support cases

#### `POST /api/v1/support-cases`
| Item | Detail |
|---|---|
| Permission | `cases:create` |
| Headers | `Idempotency-Key: <uuid>` (required → else 400 `IDEMPOTENCY_KEY_REQUIRED`) |
| Request | `{ "category": "PA_READINESS_REVIEW", "summary": "10–2000 chars", "escalation_reason": "USER_INITIATED", "related_session_id": "uuid\|null", "related_claim_number": "SYN-CLM-…\|null", "related_checklist_id": "uuid\|null", "document_ids": ["uuid"], "evidence_references": [ { "chunk_id": "uuid" } ] }` |
| Client must NOT send | `created_by_user_id`, `assigned_to_user_id`, `status`, `case_number`, `version` → 422 `FIELD_NOT_ALLOWED` |
| Validation | All related items owned by caller (else 404); `evidence_references` chunks must have been cited in the caller's `related_session_id` (else dropped with warning) |
| Response 201 | `{ "case_id": "…", "case_number": "CASE-2026-000042", "status": "OPEN", "category": "PA_READINESS_REVIEW", "escalation_reason": "USER_INITIATED", "summary": "…", "assigned_to": null, "version": 1, "created_at": "…", "updated_at": "…" }` |
| Replay | Same key + same caller → 200 with original case; same key with different body → 409 `IDEMPOTENCY_KEY_REUSED` |
| Errors | 422; 404; 500 `CASE_CREATION_FAILED` (transaction rolled back — **no case exists**) |
| Side effects | Case + `CREATED` event; links; checklist `review_state → AWAITING_REVIEW` |
| Audit | `SUPPORT_CASE_CREATED` / `SUPPORT_CASE_CREATE_FAILED` |
| FRs / tests | FR-025 / AT-041, AT-042 |

#### `GET /api/v1/support-cases`
| Item | Detail |
|---|---|
| Permission / scope | `scope=mine` (default for MEMBER/PROVIDER; `cases:read:own`), `scope=queue` (unassigned OPEN; `cases:read:queue`), `scope=assigned` (`cases:read:assigned`), `scope=all` (ADMIN; `cases:read:metadata_all`). A scope not permitted for the role → 403 |
| Query | `status` (multi), `category`, `case_number`, `created_from`, `created_to`, `limit`, `cursor` |
| Sort | `updated_at DESC` |
| Response 200 | Page of `{ "case_id", "case_number", "category", "status", "escalation_reason", "summary_preview" (≤140 chars), "assigned_to": { "id", "display_name" } \| null, "created_at", "updated_at" }` |
| FRs / tests | FR-027 / AT-044, AT-045 |

#### `GET /api/v1/support-cases/{case_id}`
| Item | Detail |
|---|---|
| Access | Creator (`cases:read:own`); assigned agent (`cases:read:assigned`); agent for unassigned OPEN case (summary view, no linked content); ADMIN (metadata + summary) |
| Response 200 (creator / assigned agent) | `{ "case_id", "case_number", "category", "status", "escalation_reason", "summary", "resolution_note", "version", "created_by": { "display_name", "role" }, "assigned_to": {…}\|null, "related_claim_number", "related_checklist_id", "documents": [ { "document_id", "original_filename" } ], "evidence_references": [Citation], "conversation_excerpt": [ { "sender", "content", "created_at" } ], "events": [ { "event_type", "from_status", "to_status", "note", "actor_display_name", "created_at" } ], "allowed_transitions": ["IN_PROGRESS","OPEN"], "created_at", "updated_at" }` — `conversation_excerpt` = last 6 messages of `related_session_id`, assigned agent only |
| ADMIN / queue view | Same minus `documents`, `evidence_references`, `conversation_excerpt`, `related_claim_number` |
| Errors | 404 when none of the above apply |
| Audit | `SUPPORT_CASE_VIEWED` for agent/admin views |
| FRs / tests | FR-027 / AT-044, AT-045 |

#### `PATCH /api/v1/support-cases/{case_id}`
| Item | Detail |
|---|---|
| Request | `{ "version": 3, "status": "IN_PROGRESS" (optional), "note": "≤2000" (optional), "resolution_note": "required when status=RESOLVED", "assign_to_me": true (agent, optional), "release": true (assigned agent, optional), "assigned_to_user_id": "uuid" (ADMIN only, optional; null = unassign), "reason": "required for ADMIN cancel/close" }` — at least one change field |
| Rules | Transition table doc 02 §3.1; actor rules doc 03 §3; creator note while `AWAITING_USER` auto-transitions to `IN_PROGRESS` |
| Response 200 | Updated case detail with new `version` |
| Errors | 403 `FORBIDDEN` (field not permitted for role, e.g. member sets `assigned_to_user_id`); 404; 409 `INVALID_STATUS_TRANSITION` (details: from, to, allowed); 409 `VERSION_CONFLICT`; 422 `INVALID_ASSIGNEE`, missing `resolution_note`/`reason` |
| Side effects | `support_case_events` rows; checklist `review_state` sync (doc 02 §3.6) |
| Audit | `SUPPORT_CASE_STATUS_CHANGED`, `SUPPORT_CASE_ASSIGNED`, `SUPPORT_CASE_NOTE_ADDED` |
| FRs / tests | FR-028, FR-029 / AT-046–AT-049 |

### 3.9 Administration

#### `GET /api/v1/admin/metrics`
| Item | Detail |
|---|---|
| Permission | `metrics:read` (ADMIN) |
| Query | `from`, `to` (dates, range ≤ 366 days, default last 30 days) |
| Response 200 | `{ "data_environment": "SYNTHETIC_PROTOTYPE", "period": { "from": "2026-09-25", "to": "2026-10-25" }, "chat": { "user_messages": 412, "by_intent": { "GENERAL_FAQ": 120, "CLAIM_STATUS": 88, "…": 0 }, "by_evidence_status": { "SUPPORTED": 210, "INSUFFICIENT": 41, "CONFLICTING": 6, "VERIFIED_RECORD": 95, "NOT_APPLICABLE": 60 }, "latency_ms": { "p50": 3900, "p95": 8700, "sample_size": 412 } }, "tools": { "get_claim_status": { "SUCCEEDED": 80, "NOT_FOUND": 6, "INVALID_ARGUMENTS": 2, "PERMISSION_DENIED": 0, "EXECUTION_ERROR": 0, "CONFIRMATION_REQUIRED": 0 } }, "cases": { "created": 37, "by_status": { "OPEN": 4, "…": 0 }, "escalated_from_chat": 22, "median_hours_to_resolution": 5.2 }, "documents": { "jobs_by_status": { "COMPLETED": 30, "COMPLETED_WITH_WARNINGS": 12, "FAILED": 3 }, "top_field_issues": [ { "field_name": "ordering_provider_npi", "status": "ABSENT", "count": 9 } ] }, "readiness": { "by_status": { "DOCUMENTATION_INCOMPLETE": 10, "…": 0 } }, "feedback": { "HELPFUL": 90, "NOT_HELPFUL": 14 }, "security": { "access_denied_events": 17 } }` (numbers illustrative only) |
| Boundaries | Counts only; no user identities, message text, or document content; groups with < 3 items shown as `"<3"` in `top_field_issues` |
| Errors | 403; 422 bad range |
| Audit | `ADMIN_METRICS_VIEWED` |
| FRs / tests | FR-030 / AT-050 |

#### `GET /api/v1/admin/audit-events`
| Item | Detail |
|---|---|
| Permission | `audit:read` (ADMIN) |
| Query | `from`, `to`, `action`, `outcome`, `actor_user_id`, `resource_type`, `resource_ref`, `limit`, `cursor` |
| Sort | `occurred_at DESC` |
| Response 200 | Page of `{ "id", "occurred_at", "request_id", "actor": { "id", "display_name", "role" } \| null, "action", "resource_type", "resource_ref", "outcome", "reason_code", "metadata": {…allowlisted} }` |
| Restrictions | Read-only; no content fields exist to expose |
| Errors | 403 (also audited as `ACCESS_DENIED`); 422 |
| Audit | `AUDIT_EVENTS_VIEWED` |
| FRs / tests | FR-032 / AT-052 |

#### `GET /api/v1/admin/knowledge-gaps` (added: FR-033)
Permission `knowledge_gaps:read`. Query `from`, `to`. Response `{ "data_environment": "SYNTHETIC_PROTOTYPE", "items": [ { "gap_topic": "acupuncture coverage", "evidence_status": "INSUFFICIENT", "occurrences": 7, "distinct_users": 5, "last_seen_at": "…", "example_intents": ["BENEFITS_INFO"] } ], "requirement_set_misses": [ { "requested_procedure_text": "knee arthroscopy", "occurrences": 3 } ], "tool_failures": [ { "tool_name": "get_plan_benefits", "result_status": "EXECUTION_ERROR", "occurrences": 2 } ] }`. Topics with `distinct_users < 2` are suppressed. AT-053.

#### `GET /api/v1/admin/support-agents` (added: assignment UI needs assignee list)
Permission `cases:assign:any`. `{ "items": [ { "id", "display_name", "open_assigned_count" } ] }` — active SUPPORT_AGENT users only. AT-046.

---

## 4. Standard Error Format

```json
{
  "error": {
    "code": "INVALID_STATUS_TRANSITION",
    "message": "This case can't move from CLOSED to IN_PROGRESS.",
    "details": [ { "field": "status", "issue": "not_allowed", "allowed": [] } ],
    "request_id": "6f1d2b8c-0f7e-4f0a-9a3e-2b1c8d7e6a55"
  }
}
```

| Code | HTTP | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Schema/field validation failed (`details` lists fields) |
| `FIELD_NOT_ALLOWED` | 422 | Client sent a server-controlled field |
| `IDEMPOTENCY_KEY_REQUIRED` | 400 | Missing `Idempotency-Key` |
| `IDEMPOTENCY_KEY_REUSED` | 409 | Key reused with a different body |
| `UNAUTHENTICATED` | 401 | Missing/invalid/expired/revoked token |
| `INVALID_CREDENTIALS` | 401 | Login failed |
| `FORBIDDEN` | 403 | Role lacks permission |
| `RESOURCE_NOT_FOUND` | 404 | Not found **or** not permitted (indistinguishable) |
| `REQUIREMENT_SET_NOT_FOUND` | 404 | No active requirement set |
| `DOCUMENT_NOT_ANALYZED` | 409 | Document lacks a completed job |
| `JOB_ALREADY_RUNNING` | 409 | Analysis already queued/running |
| `INVALID_STATUS_TRANSITION` | 409 | Transition not allowed |
| `VERSION_CONFLICT` | 409 | Stale `version` |
| `INVALID_ASSIGNEE` | 422 | Assignee not an active support agent |
| `FILE_TOO_LARGE` | 413 | Upload too large |
| `UNSUPPORTED_FILE_TYPE` | 415 | Type not allowed or mismatched |
| `MALFORMED_FILE` | 422 | Corrupt, encrypted, or over page/pixel limits |
| `RATE_LIMITED` | 429 | Too many requests (`Retry-After` header) |
| `CASE_CREATION_FAILED` | 500 | Case not created |
| `INTERNAL_ERROR` | 500 | Unexpected error |
| `AI_SERVICE_UNAVAILABLE` | 503 | LLM/embedding service failed or timed out |
| `SERVICE_UNAVAILABLE` | 503 | Database unreachable (added in Phase 2, D2-06) |
| `METHOD_NOT_ALLOWED` | 405 | HTTP method not supported by the route (added in Phase 2, D2-06) |

Messages are safe, generic and user-readable. Never included: stack traces, SQL, file paths, prompts, model names, tokens, secrets, or other users' data.

---

## 5. Tool Contracts (internal, not public routes)

Tools are invoked only by the orchestrator through the tool executor. Each tool receives a backend-injected `UserContext { user_id, role, member_id?, plan_id?, organization_id? }` that the model never sees or supplies. Common rules: argument schemas use `extra="forbid"`; max 3 tool calls per user message; every invocation writes `tool_invocations` + an audit event.

### 5.1 `get_claim_status`
| Item | Detail |
|---|---|
| Purpose | Retrieve one of the caller's claims, or list recent claims |
| Input | `{ "claim_number": "SYN-CLM-2026-000101" \| null }` (null → up to 5 most recent own claims) |
| Output | `{ "result_status": "SUCCEEDED", "claims": [ { "claim_number", "status", "status_reason_code", "status_description", "service_date", "submission_date", "last_status_change_at", "provider_name" } ] }` |
| Allowed when | Intent `CLAIM_STATUS`; role MEMBER |
| Permission check | `claims:read:own`; query scoped `member_id = ctx.member_id` |
| Data | Read `claims` |
| Failures | `INVALID_ARGUMENTS` (pattern), `PERMISSION_DENIED` (non-member), `NOT_FOUND`, `EXECUTION_ERROR` |
| Idempotency | Read-only |
| Audit | `TOOL_INVOKED` + `CLAIM_LOOKUP` / `ACCESS_DENIED` |
| Confirmation / human approval | No / No |

### 5.2 `get_plan_benefits`
| Item | Detail |
|---|---|
| Input | `{ "plan_code": "SYN-PLAN-GOLD-01" \| null, "benefit_category": "IMAGING" \| null }` (MEMBER: null → own plan; a different code → `NOT_FOUND`) |
| Output | `{ "result_status", "plan": { "plan_code", "plan_name", "plan_year" }, "benefits": [ { …as API…, "source_chunk_id" } ] }` |
| Allowed when | Intent `BENEFITS_INFO` |
| Permission | `benefits:read:own` or `benefits:read:any` |
| Failures | `INVALID_ARGUMENTS` (provider with null plan_code → clarification), `NOT_FOUND`, `EXECUTION_ERROR` |
| Audit | `TOOL_INVOKED` + `BENEFITS_LOOKUP` |
| Confirmation / approval | No / No |

### 5.3 `get_required_documents`
| Item | Detail |
|---|---|
| Input | `{ "procedure_code": "SYN-PROC-MRI-LUMBAR" \| null, "procedure_text": "lumbar MRI" \| null }` — exactly one required; text matched against `aliases` deterministically (case-insensitive exact/contains); ambiguous → `INVALID_ARGUMENTS` with candidate codes |
| Output | `{ "result_status", "procedure_code", "version", "requirements": [ { "requirement_code", "description", "is_mandatory", "source_chunk_id" } ] }` |
| Allowed when | Intent `REQUIRED_DOCUMENTS` or `PA_READINESS` |
| Permission | `requirements:read` |
| Failures | `INVALID_ARGUMENTS`, `NOT_FOUND` (recorded for gap analysis), `EXECUTION_ERROR` |
| Audit | `TOOL_INVOKED` + `REQUIREMENTS_LOOKUP` |
| Confirmation / approval | No / No |

### 5.4 `create_support_case`
| Item | Detail |
|---|---|
| Purpose | Propose a support case; **never creates one directly** |
| Input | `{ "category": "…", "escalation_reason": "…", "summary": "10–2000 chars" }` |
| Output | `{ "result_status": "CONFIRMATION_REQUIRED", "proposed_action": ProposedAction }` — backend fills `related_session_id` and validated citations |
| Allowed when | Intents `SUPPORT_CASE_CREATE`, `HUMAN_ASSISTANCE`, or any escalation trigger |
| Permission | `cases:create` (else `PERMISSION_DENIED`) |
| Data | None modified by the tool. Creation happens via `POST /support-cases` after user confirmation, with its own validation and idempotency |
| Audit | `TOOL_INVOKED` (result `CONFIRMATION_REQUIRED`) |
| Confirmation / approval | **Yes — explicit user confirmation** / Human review happens after creation by a support agent |

The language model may request any of these tools, but it never authorizes or executes them. The backend validates the tool name, arguments, the authenticated user and resource permissions before execution, and builds the user-facing result only from the verified output.
