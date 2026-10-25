# 03 — Roles and Permissions

The authorization model is defined **before** queries and routes. The backend is the only authority for access decisions.

---

## 1. Roles

| Role | Description |
|---|---|
| `MEMBER` | A synthetic plan member. Linked 1:1 to a `members` record (synthetic member number and plan). |
| `PROVIDER` | Administrative staff of a fictional provider practice. Linked to one `organizations` row of type `PROVIDER_PRACTICE`. |
| `SUPPORT_AGENT` | Staff of the fictional support center (`SUPPORT_CENTER` organization) who work support cases. |
| `ADMIN` | Operator of the prototype: assignment, metrics, audit, deployment-level configuration. |

These are **application roles inside a prototype**. They do not represent verified professional credentials, real employment, licensure, or real organizational membership. Each user has exactly one role (`users.role`). Role changes are made only by seed/administrative tooling, never through the public API.

---

## 2. Permission Catalogue

Permissions are fixed in code (a role → permission map). Every route and tool declares the permission(s) it requires.

| Permission | Meaning |
|---|---|
| `chat:use` | Send chat messages; read own sessions |
| `knowledge:read` | Retrieve knowledge chunks permitted for the role's audiences |
| `claims:read:own` | Read claims whose `member_id` is the caller's member record |
| `claims:read:case_linked` | Read the claim referenced by `related_claim_id` of a case assigned to the caller |
| `benefits:read:own` | Read benefits of the caller's own plan |
| `benefits:read:any` | Read benefits of any active synthetic plan (plan-level terms only) |
| `requirements:read` | Read active documentation requirement sets |
| `documents:upload` | Upload documents (owned by the caller) |
| `documents:read:own` | Read own uploaded documents, jobs and extracted fields |
| `documents:read:case_linked` | Read documents linked to a case assigned to the caller |
| `readiness:create` | Create readiness checklists from own documents |
| `readiness:read:own` | Read own checklists |
| `readiness:read:case_linked` | Read the checklist linked to a case assigned to the caller |
| `cases:create` | Create support cases |
| `cases:read:own` | Read cases the caller created |
| `cases:update:own` | Creator actions: cancel while `OPEN`, add note, reopen `RESOLVED` within 14 days |
| `cases:read:queue` | Read unassigned `OPEN` cases (summary-level) |
| `cases:read:assigned` | Read full detail of cases assigned to the caller |
| `cases:update:assigned` | Change status/notes of cases assigned to the caller |
| `cases:assign:self` | Self-assign an unassigned `OPEN` case; release own case |
| `cases:read:metadata_all` | Read metadata + summary of all cases (no linked content) |
| `cases:assign:any` | Assign/reassign/unassign any non-terminal case; close/cancel with reason |
| `metrics:read` | Read aggregate metrics |
| `knowledge_gaps:read` | Read knowledge-gap aggregates |
| `audit:read` | Read audit events (metadata only) |
| `feedback:create` | Rate own assistant messages |
| `config:manage` | Deployment-level configuration, ingestion and seeding via CLI (no web route in MVP) |

### 2.1 Role → permission map

| Permission | MEMBER | PROVIDER | SUPPORT_AGENT | ADMIN |
|---|:-:|:-:|:-:|:-:|
| `chat:use` | ✔ | ✔ | ✔ | ✔ |
| `knowledge:read` | ✔ | ✔ | ✔ | ✔ |
| `claims:read:own` | ✔ | — | — | — |
| `claims:read:case_linked` | — | — | ✔ | — |
| `benefits:read:own` | ✔ | — | — | — |
| `benefits:read:any` | — | ✔ | ✔ | ✔ |
| `requirements:read` | ✔ | ✔ | ✔ | ✔ |
| `documents:upload` | ✔ | ✔ | — | — |
| `documents:read:own` | ✔ | ✔ | — | — |
| `documents:read:case_linked` | — | — | ✔ | — |
| `readiness:create` | — | ✔ | — | — |
| `readiness:read:own` | — | ✔ | — | — |
| `readiness:read:case_linked` | — | — | ✔ | — |
| `cases:create` | ✔ | ✔ | — | — |
| `cases:read:own` | ✔ | ✔ | — | — |
| `cases:update:own` | ✔ | ✔ | — | — |
| `cases:read:queue` | — | — | ✔ | — |
| `cases:read:assigned` | — | — | ✔ | — |
| `cases:update:assigned` | — | — | ✔ | — |
| `cases:assign:self` | — | — | ✔ | — |
| `cases:read:metadata_all` | — | — | — | ✔ |
| `cases:assign:any` | — | — | — | ✔ |
| `metrics:read` | — | — | — | ✔ |
| `knowledge_gaps:read` | — | — | — | ✔ |
| `audit:read` | — | — | — | ✔ |
| `feedback:create` | ✔ | ✔ | ✔ | ✔ |
| `config:manage` | — | — | — | ✔ (CLI only) |

---

## 3. Permission Matrix (resources and actions)

| Resource or action | Member | Provider | Support agent | Administrator |
|---|---|---|---|---|
| Ask general support questions | Allowed | Allowed | Allowed | Allowed |
| Read approved knowledge documents (via RAG citations) | Audience `MEMBER` only; plan-scoped docs only for own plan | Audiences `MEMBER`, `PROVIDER` | Audiences `MEMBER`, `PROVIDER`, `SUPPORT_INTERNAL` | Audiences `MEMBER`, `PROVIDER`, `SUPPORT_INTERNAL` |
| Retrieve own synthetic claim | Allowed (own member record only) | Not applicable (providers have no member record) | Not applicable | Not applicable |
| Retrieve another user's claim | **Denied** (returns 404) | **Denied** — out of scope pending an approved provider–member relationship model (D-08) | Only the claim linked to a case **assigned to them**; otherwise denied | **Denied** (aggregate metrics only) |
| Retrieve plan benefits | Own plan only | Any active synthetic plan | Any active synthetic plan | Any active synthetic plan |
| Retrieve documentation requirements | Allowed | Allowed | Allowed | Allowed |
| Upload own supported document | Allowed | Allowed | Denied | Denied |
| View an uploaded document and its extraction | Own only | Own only | Only documents linked to a case assigned to them | Denied (metadata counts only via metrics) |
| Prepare authorization (readiness) checklist | Denied | Allowed, using own analyzed documents only | Denied (may view checklist linked to an assigned case) | Denied |
| Create a support case | Allowed | Allowed | Denied (agents work cases, they don't file them in MVP) | Denied |
| View own created support cases | Allowed | Allowed | Not applicable | Not applicable |
| View unassigned case queue | Denied | Denied | Allowed (summary fields only) | Allowed via metadata list |
| View assigned support cases (full detail) | Denied | Denied | Allowed — cases assigned to them | Metadata + summary of all cases; no linked document fields, claim details or conversation excerpt |
| Assign a case | Denied | Denied | Self-assign unassigned `OPEN` cases; release own | Assign/reassign/unassign any non-terminal case |
| Update support case status | Creator transitions only (cancel `OPEN`, reopen `RESOLVED` ≤ 14 days, add note) | Same as member | Transitions in doc 02 §3.1 for cases assigned to them | Close/cancel any case with reason; reassignment |
| View aggregate dashboard metrics | Denied | Denied | Denied | Allowed |
| View knowledge-gap report | Denied | Denied | Denied | Allowed (no user identities) |
| View audit information | Denied | Denied | Denied (sees the event history of their assigned cases only) | Allowed — metadata only, no content |
| Rate an assistant answer | Own messages | Own messages | Own messages | Own messages |
| Change application configuration | Denied | Denied | Denied | Deployment configuration via environment/CLI only; no runtime config API in MVP |

---

## 4. Authorization Rules

### 4.1 Identity
- Established by `POST /api/v1/auth/login` (email + password, argon2id verification).
- Backend issues a signed JWT (HS256 with a secret from the environment; RS256 if an external IdP is adopted later) containing `sub` (user UUID), `role`, `jti`, `iat`, `exp` (30 min default).
- Every request resolves the token, then **reloads the user from the database** to confirm `account_status = ACTIVE` and the current role. Token claims are never trusted alone for resource scope.

### 4.2 Roles
- Read from `users.role` at request time. Role is not settable through any API.

### 4.3 Resource ownership and organizations
| Resource | Ownership / scope rule |
|---|---|
| `claims` | `claims.member_id = members.id WHERE members.user_id = current_user` |
| `plans`, `plan_benefits` | Member: `plans.id = members.plan_id` of current user. Others: `plans.is_active = true` |
| `uploaded_documents`, jobs, fields | `uploaded_documents.owner_user_id = current_user` |
| `authorization_checklists` | `created_by_user_id = current_user` (must be PROVIDER) |
| `support_cases` | Creator: `created_by_user_id = current_user`; Agent: `assigned_to_user_id = current_user`, or `status = OPEN AND assigned_to_user_id IS NULL` for queue view |
| `conversation_sessions` / messages | `conversation_sessions.user_id = current_user` |
| `user_feedback` | Message must belong to a session owned by current user |
| `audit_logs` | ADMIN only |

Organization membership (`users.organization_id`) is recorded for providers and agents. In the MVP it is used to (a) restrict assignees to active users in the `SUPPORT_CENTER` organization and (b) attribute provider-created cases to their practice in metrics. It does **not** grant access to other users' records.

### 4.4 Support-agent assignment checks
- Case detail, linked claim, linked documents and linked checklist are readable only while `support_cases.assigned_to_user_id = current_user`.
- Assignment changes are validated: assignee must have role `SUPPORT_AGENT`, `account_status = ACTIVE`, and belong to the `SUPPORT_CENTER` organization.
- Access ends immediately when the case is reassigned.

### 4.5 Administrative restrictions
- ADMIN cannot read claim details, uploaded document fields, conversation contents, or linked case content. ADMIN sees aggregates, case metadata/summary and audit metadata.
- ADMIN cannot create users or change roles through the API in the MVP (seed/CLI only).

### 4.6 Failed access attempts
- Role failures → 403 `FORBIDDEN`. Ownership/scope failures → 404 `RESOURCE_NOT_FOUND` (prevents ID enumeration).
- Both write an `ACCESS_DENIED` audit event with `outcome = DENIED`, `reason_code` (`ROLE_NOT_PERMITTED`, `NOT_OWNER`, `NOT_ASSIGNED`, `NOT_EXISTS`), resource type and the requested identifier (public reference only).
- More than 20 denials per user in 10 minutes is surfaced in metrics as `access_denied_spikes` (no automatic lockout in MVP).

### 4.7 RAG retrieval
- Audience filter in SQL: `knowledge_documents.audience && :allowed_audiences` where allowed audiences per role are listed in §3.
- Plan filter: `plan_id IS NULL OR plan_id = :caller_plan_id` for members.
- Lifecycle filter: `lifecycle_status = 'ACTIVE'`.
- Retrieval filtering limits what evidence the model sees; it is **not** a substitute for endpoint/tool authorization, and knowledge documents never contain member-specific data.

### 4.8 AI tool calls
- The LLM can only emit a structured *request* (tool name + arguments). The tool executor:
  1. Rejects tools not in the allowlist → `INVALID_ARGUMENTS`.
  2. Validates arguments against the Pydantic schema → `INVALID_ARGUMENTS`.
  3. Checks the tool's required permission for the caller's role → `PERMISSION_DENIED`.
  4. Executes using the **authenticated user context** injected by the backend — ownership predicates are added server-side; tool schemas have no `user_id`/`member_id` argument.
  5. Returns `NOT_FOUND` when no permitted record matches.
- `create_support_case` returns `CONFIRMATION_REQUIRED`; creation happens only through the user-confirmed API call.

### 4.9 Client-supplied identifiers
- Any ID in a path, query, body or tool argument is treated as a *lookup key*, never as proof of access. The ownership predicate is always combined with it in the same query.
- Server-controlled fields (owner, creator, assignee for non-admins, status timestamps, `case_number`, `version`) are ignored or rejected if supplied by clients (422 `FIELD_NOT_ALLOWED`).

### 4.10 Independence from model output
- No authorization decision reads LLM output. Model text cannot grant permissions, change roles, select another user's records, or mark a tool as confirmed.
- Retrieved documents and uploaded files are untrusted data; embedded instructions are ignored (doc 09 §4).

### 4.11 Frontend visibility
- The frontend hides navigation items not permitted for the role (doc 08 §2). This is a usability feature only; every route is enforced in the backend.

---

## 5. Explicitly Deferred

- **Provider access to member records** (claims, member documents, member-specific benefits): out of scope until an approved relationship model (e.g., attested treatment relationship, consent) exists — D-08.
- **Agent-created cases on behalf of users**, **admin user management**, and **audit access for agents**: not in MVP.
