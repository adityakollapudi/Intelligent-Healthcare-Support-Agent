# 01 — Requirements Specification

**Project:** Intelligent Healthcare Support Agent (IHSA)
**Phase:** 1 — Requirements and System Design
**Status:** Baseline v1.0 (design artifact — nothing described here is implemented yet)
**Data policy:** Synthetic data and fictional documents only (see A-01).

> IHSA is an independent internship case-study prototype. It is **not** an Evernorth product, is not connected to any Evernorth system, and uses no Evernorth data, policies, or infrastructure.

---

## 1. Executive Summary

**Purpose.** IHSA is a web application that helps three kinds of users — healthcare insurance **members**, healthcare **provider administrative staff**, and internal **support staff** — get administrative healthcare information and complete a small set of supported workflows from one interface.

**Users.**
- *Members* ask about their plan benefits, check the status of their own (synthetic) claims, find out which documents a process needs, and open support cases.
- *Provider staff* look up fictional prior authorization (PA) documentation requirements, upload sample request documents, and receive a readiness checklist and draft summary for a human reviewer.
- *Support agents* work an assigned case queue; *administrators* assign cases, monitor aggregate metrics, and inspect audit events.

**Major capabilities.**
1. Conversational assistant with intent routing and conversation context.
2. Retrieval-Augmented Generation (RAG) over a fictional knowledge base, returning answers with verifiable citations.
3. Controlled, permission-checked lookups of synthetic claims, plan benefits, and documentation requirements.
4. Document upload, text extraction (with OCR fallback), and schema-based field extraction with field-level validation.
5. Deterministic, rule-based PA **readiness** checklists (never approvals).
6. Support case creation, human escalation, assignment, and status management.
7. Audit logging, an administrator dashboard, and knowledge-gap reporting.

**Technical approach.** React + TypeScript (Vite) frontend; Python FastAPI backend with Pydantic validation; PostgreSQL with the pgvector extension as the single datastore for structured records and vector search; a provider-agnostic LLM adapter; PyMuPDF and Tesseract for documents. All authorization, tool execution, and business rules run in the trusted backend, separate from the language model.

**How IHSA differs from a conventional chatbot.**

| Conventional chatbot | IHSA |
|---|---|
| Primarily answers questions from a script or from the model's general knowledge | Answers policy questions only from retrieved, permitted documents and shows the citations |
| Cannot see account-specific data, or exposes it without checks | Queries structured synthetic records through backend tools that check identity and ownership first |
| Cannot read documents | Extracts and validates fields from uploaded PDFs and images |
| Cannot do work | Prepares checklists, draft summaries, and support cases |
| Guesses when unsure | Returns an explicit insufficient-evidence response and offers human escalation |

**Intended value (to be evaluated, not claimed).** Less manual searching for administrative information, more complete PA documentation packages before human review, and more consistent, traceable support interactions. No time or cost savings are claimed; Phase 8 measures only prototype-level quality metrics on synthetic data.

**What IHSA is not.** It is an administrative-support prototype. It does not diagnose, recommend treatment, prescribe, adjudicate claims, or approve or deny prior authorizations.

---

## 2. Problem Statement

Members and provider administrative staff who need healthcare insurance information typically face:

1. **Fragmented documentation.** Benefit guides, FAQs, claim-processing instructions, and PA requirement documents are separate, long, and versioned. Finding the current, applicable passage is slow and error-prone.
2. **Opaque claim information.** Claim status codes ("pending information") are not self-explanatory, and the explanation lives in a different document from the status itself.
3. **Unclear documentation requirements.** Provider staff often discover missing items only after a request is returned, causing rework.
4. **Disconnected support processes.** Asking a question, checking a record, preparing a document, and contacting a human happen in different channels with no shared context.
5. **Limits of FAQ chatbots.** A scripted or ungrounded bot cannot retrieve account-specific data safely, read documents, perform workflows, or recognize when a human is required — and an ungrounded LLM may fabricate coverage rules.

**Proposed solution.** One authenticated interface where an assistant (a) answers policy questions from permitted documents with citations, (b) retrieves the caller's own structured records through permission-checked tools, (c) analyzes uploaded documents against explicit rule sets, and (d) creates and routes support cases to humans with the relevant context attached.

**Intended benefits vs. demonstrated outcomes.** The benefits above are hypotheses. The prototype will demonstrate functional correctness, retrieval quality, extraction accuracy, and access-control effectiveness on synthetic test data (doc 10). It will not demonstrate real-world operational or financial outcomes.

---

## 3. Project Goals

| Goal ID | Goal | Verification method | Related FRs |
|---|---|---|---|
| G-01 | Deliver a functioning conversational interface | E2E test: a user logs in, sends a message, receives a persisted response (AT-007) | FR-004, FR-005 |
| G-02 | Retrieve supported answers from the synthetic knowledge base | RAG evaluation set: answer correctness against an answer key (AT-015) | FR-008–FR-010 |
| G-03 | Display valid citations for document-grounded answers | Every citation resolves to a retrieved, permitted chunk (AT-015, AT-016) | FR-010, FR-011 |
| G-04 | Retrieve synthetic claims and plan benefits from structured data | Returned values equal database values (AT-019, AT-021) | FR-014, FR-015 |
| G-05 | Support document extraction and validation | Field-extraction accuracy on labeled synthetic documents (AT-031–AT-033) | FR-018–FR-021 |
| G-06 | Generate PA readiness checklists | Checklist items match expected outcomes for labeled document sets (AT-035–AT-037) | FR-022, FR-023 |
| G-07 | Create support cases and route unresolved requests | Case created, confirmed by ID, visible to authorized staff; failure is reported honestly (AT-041–AT-043) | FR-025, FR-026 |
| G-08 | Record important system activities | Audit events exist for every action in doc 09 §5 (AT-051) | FR-031 |
| G-09 | Display operational metrics | Dashboard values equal values computed directly from test records (AT-050) | FR-030, FR-033 |
| G-10 | Enforce backend authorization and basic privacy controls | All cross-user and cross-role negative tests pass (AT-004–AT-006, AT-026, AT-034, AT-038) | FR-001–FR-003 |

---

## 4. Scope

### 4.1 In scope for the first complete prototype (MVP)

- Four application roles: `MEMBER`, `PROVIDER`, `SUPPORT_AGENT`, `ADMIN` (doc 03).
- Local email/password authentication with hashed passwords (provisional, D-02).
- Chat interface with session history and intent routing.
- Synthetic organizations, members, plans, plan benefits, and claims.
- RAG over fictional administrative documents (benefit guides, FAQs, claim-process guides, PA requirement documents, support procedures).
- Source-grounded answers with validated citations and explicit insufficient-evidence and conflicting-evidence responses.
- Controlled tools: `get_claim_status`, `get_plan_benefits`, `get_required_documents`, `create_support_case`.
- Upload of PDF, PNG, and JPEG documents; text extraction; OCR fallback; schema-based field extraction; field validation.
- Rule-based PA readiness checklists using fictional requirement sets and a deterministic reviewer summary.
- Support case creation (with user confirmation), escalation, assignment, status transitions, and history.
- Audit logging and an administrator dashboard (metrics, audit events, knowledge gaps).
- Answer feedback (thumbs up/down).
- Testing, AI evaluation, security evaluation, Docker Compose packaging, and documentation.

### 4.2 Out of scope

- Autonomous diagnosis, triage, or treatment recommendations.
- Medication prescribing or dosing advice.
- Autonomous prior authorization approval, denial, or medical-necessity determination.
- Real claims adjudication, payment processing, or financial transactions.
- Access to real member records, real PHI, or real clinical documents.
- Production connections to Evernorth, any payer, clearinghouse, or EHR.
- Unapproved external healthcare integrations (e.g., real FHIR/X12 endpoints).
- Guaranteed legal, medical, coverage, or regulatory determinations.
- **Provider access to member-specific records** (claims, member documents). No approved provider–member relationship model exists; this is deferred (A-10, D-08).
- Complex multi-agent orchestration; runtime configuration UI; knowledge-document management UI (ingestion is an administrator CLI task in the MVP).
- Single sign-on with any company identity provider.

### 4.3 Future enhancements (not MVP acceptance criteria)

- Voice input and text-to-speech.
- Multilingual conversations.
- Opt-in proactive reminders for incomplete simulated workflows.
- Integration with approved healthcare data exchange standards (e.g., FHIR) in an approved environment.
- Carefully evaluated additional specialized agents.
- External identity provider (OIDC) and production-grade enterprise integration.
- Approved provider–member relationship model enabling provider claim lookups.
- Streaming chat responses; reranking model (only if evaluation shows benefit).

---

## 5. Stakeholders and User Personas

### 5.1 Stakeholders

| Stakeholder | Interest |
|---|---|
| Intern developer (project owner) | Builds and documents the prototype |
| Internship mentor / reviewers | Evaluate engineering quality and responsible-AI practice |
| Prototype end users (synthetic personas) | Members, provider staff, support agents, administrators |
| Future security/privacy/compliance reviewers | Would need to approve any real-data use (A-09) |

### 5.2 Personas

**P-01 — Healthcare Member (role `MEMBER`).** "Priya Synthetic", enrolled in fictional plan `SYN-PLAN-GOLD-01`. Needs plain-language benefit information, the status of her own claims and what that status means, which documents a process requires, and a simple way to reach a human. Cannot see any other member's data.

**P-02 — Provider Administrative Staff (role `PROVIDER`).** "Jordan Example", front-office coordinator at the fictional "Maplestone Family Clinic". Needs fictional PA requirement information, document analysis, a readiness checklist, a draft reviewer summary, and a way to submit the package for human review. **Does not** have access to member claims or member-uploaded documents in the MVP.

**P-03 — Support Agent (role `SUPPORT_AGENT`).** "Sam Reviewer", member of the fictional support organization. Works a queue: claims unassigned cases, reviews the case summary, linked evidence and documents, and moves cases through permitted status transitions. Sees only cases that are unassigned in the queue or assigned to them.

**P-04 — System Administrator (role `ADMIN`).** "Alex Operator". Assigns and reassigns cases, views aggregate metrics, inspects audit events and knowledge gaps, and runs ingestion and seeding tasks through deployment tooling.

### 5.3 Support agent vs. administrator

| Aspect | Support agent | Administrator |
|---|---|---|
| Primary job | Resolve individual cases | Operate and oversee the system |
| Case content | Full detail of cases assigned to them | Case metadata and summary only, for assignment and oversight |
| Case status | Changes status of own assigned cases | Assigns/reassigns; may close or cancel any case for administrative reasons |
| Claims | Only the claim linked to an assigned case | None (aggregate metrics only) |
| Audit logs | None (sees case history of own cases) | Read audit events (metadata only) |
| Configuration | None | Deployment configuration, ingestion, seeding (outside the web UI) |

Neither role grants unrestricted access to conversation transcripts or document contents.

---

## 6. User Stories

Priority uses MoSCoW: **Must**, **Should**, **Could**.

| Story ID | Role | User story | Priority | Dependencies | Acceptance criteria | Planned phase |
|---|---|---|---|---|---|---|
| US-001 | Member | As a member, I want to ask questions in everyday language, so that I don't need to know where information is stored. | Must | FR-004, FR-005 | Message of 1–4,000 chars is accepted; a response is returned and both are persisted in my session (AT-007, AT-008). | 4 |
| US-002 | Member | As a member, I want answers that show their source documents, so that I can trust and verify them. | Must | FR-010, FR-011 | Grounded answers show ≥1 citation with title, version, effective date (if known) and passage excerpt; every citation resolves to a permitted chunk (AT-015, AT-016). | 4 |
| US-003 | Member | As a member, I want to be told clearly when the assistant cannot find an answer, so that I am not misled. | Must | FR-012, FR-026 | Out-of-knowledge-base questions return `evidence_status = INSUFFICIENT` with no factual policy claims, plus an escalation offer (AT-017, AT-043). | 4 |
| US-004 | Member | As a member, I want to check the status of my claim, so that I know where it stands. | Must | FR-014, FR-017 | Status, submission date and last-updated date equal database values (AT-019). | 5 |
| US-005 | Member | As a member, I want the meaning of my claim status explained, so that I know what to do next. | Should | FR-014, FR-010 | Explanation cites the claim-status guide; the status itself comes from the tool result (AT-019). | 5 |
| US-006 | Member | As a member, I want to see my plan's benefits, so that I understand what my plan describes. | Must | FR-015 | Benefits for my own plan are returned with their source document reference (AT-021). | 5 |
| US-007 | Member | As a member, I want to know which documents a process requires, so that I can prepare them. | Must | FR-016 | Requirements are returned from the configured requirement set with source references (AT-023). | 5 |
| US-008 | Member | As a member, I want to upload a supporting document, so that it can be checked and attached to a case. | Should | FR-018 | Valid PDF/PNG/JPEG ≤ configured size is accepted; invalid files are rejected with a clear message (AT-027–AT-029). | 6 |
| US-009 | Member | As a member, I want to create a support case, so that a person can help me. | Must | FR-025 | After confirmation, a case is created and its case number shown only if the backend confirms creation (AT-041, AT-042). | 5 |
| US-010 | Member | As a member, I want to see the status of my cases, so that I know if they're being handled. | Must | FR-027 | I see only my own cases with status and timestamps (AT-044). | 5 |
| US-011 | Provider | As provider staff, I want to ask what documentation a fictional procedure requires, so that I can prepare a complete request. | Must | FR-016, FR-010 | Answer lists configured requirements with citations to the requirement document (AT-023). | 5 |
| US-012 | Provider | As provider staff, I want to upload a sample authorization request, so that it can be analyzed. | Must | FR-018, FR-019 | File is validated, stored, and an analysis job reports its status (AT-027, AT-031). | 6 |
| US-013 | Provider | As provider staff, I want to review the extracted fields with warnings, so that I can correct problems. | Must | FR-020, FR-021 | Each field shows value, validation status and source page; absent fields are marked `ABSENT`, never filled in (AT-032, AT-033). | 6 |
| US-014 | Provider | As provider staff, I want to see apparently missing information, so that I can supply it before review. | Must | FR-022 | Missing requirements appear as `MISSING` items with the rule and source used (AT-036). | 6 |
| US-015 | Provider | As provider staff, I want a readiness checklist for my document set, so that I know its completeness. | Must | FR-022 | Every requirement in the set produces exactly one item with one of the four statuses (AT-035–AT-037). | 6 |
| US-016 | Provider | As provider staff, I want a draft summary for the reviewer, so that review is faster. | Should | FR-023 | Summary contains only checklist facts and the non-approval disclaimer (AT-039). | 6 |
| US-017 | Provider | As provider staff, I want to be told clearly that readiness is not approval, so that I don't misinform a patient. | Must | FR-024 | Asking "is it approved?" returns no approval status unless one exists in the synthetic data, and explains readiness limits (AT-040). | 6 |
| US-018 | Provider | As provider staff, I want to submit a checklist for human review, so that an authorized person can act on it. | Must | FR-025, FR-022 | A `PA_READINESS_REVIEW` case linked to the checklist is created; checklist `review_state` becomes `AWAITING_REVIEW` (AT-041). | 6 |
| US-019 | Provider | As provider staff, I want to track the cases I submitted, so that I can follow up. | Must | FR-027 | I see only cases I created (AT-044). | 5 |
| US-020 | Support agent | As a support agent, I want a queue of unassigned and my assigned cases, so that I can choose work. | Must | FR-027, FR-028 | Queue contains unassigned cases and cases assigned to me only (AT-045). | 7 |
| US-021 | Support agent | As a support agent, I want case details with the escalation reason and evidence, so that I can resolve it without re-asking. | Must | FR-027 | Assigned case detail shows summary, reason, linked citations, documents, checklist and claim (AT-045). | 7 |
| US-022 | Support agent | As a support agent, I want to update a case's status with a note, so that progress is recorded. | Must | FR-029 | Valid transitions succeed and are recorded in history; invalid ones return 409 (AT-047–AT-049). | 7 |
| US-023 | Admin | As an administrator, I want to assign cases to agents, so that work is distributed. | Must | FR-028 | Admin can assign/reassign; non-admins cannot assign to others (AT-046). | 7 |
| US-024 | Admin | As an administrator, I want aggregate metrics, so that I can monitor the prototype. | Must | FR-030 | Metrics equal values computed from records and are labeled as synthetic-environment data (AT-050). | 7 |
| US-025 | Admin | As an administrator, I want to view audit events, so that I can trace important actions. | Must | FR-032 | Filtered, paginated events contain metadata only; non-admins get 403 (AT-052). | 7 |
| US-026 | Admin | As an administrator, I want a list of frequently unanswered questions, so that I can improve documentation. | Should | FR-033 | Report groups insufficient-evidence questions by normalized topic with counts (AT-053). | 7 |
| US-027 | Any | As any user, I want my records protected from other users, so that my information stays private. | Must | FR-002, FR-003 | Every cross-user/cross-role negative test returns 403/404 and creates an `ACCESS_DENIED` audit event (AT-004–AT-006, AT-026, AT-034). | 2 |
| US-028 | Any | As any user, I want to log in and see only the screens for my role, so that the app is simple to use. | Must | FR-001 | Login works; navigation matches doc 08 matrix; backend still enforces access (AT-001–AT-003). | 2–3 |
| US-029 | Member/Provider | As a user, I want to rate an answer, so that the team can improve the assistant. | Should | FR-034 | Rating stored for my own message only (AT-054). | 7 |
| US-030 | Member/Provider | As a user, I want suggested next steps after an answer, so that I know what to do. | Should | FR-035 | Suggestions come only from the allowed-action list and respect my role (AT-059). | 7 |

---

## 7. Functional Requirements

Format: each requirement lists **Actor / Preconditions / Trigger / Expected behavior / Success / Failure / Priority / Acceptance / Dependencies / Phase**.

### 7.1 Identity and access

**FR-001 — User authentication**
- *Description:* Users authenticate with email and password; the backend issues a signed, short-lived access token used for all non-public API calls.
- *Actor:* All roles. *Preconditions:* Active user account exists (seeded). *Trigger:* `POST /api/v1/auth/login`.
- *Expected behavior:* Verify password hash (argon2id); issue JWT (default lifetime 30 min, configurable) containing user ID and role; `GET /api/v1/auth/me` returns profile; `POST /api/v1/auth/logout` adds the token ID to a deny-list until expiry.
- *Success:* 200 with token and profile. *Failure:* Generic 401 `INVALID_CREDENTIALS` (no hint whether email exists); after 5 failures per account per 15 min, 429 `RATE_LIMITED`; audit `AUTH_LOGIN_FAILED`.
- *Priority:* Must. *Acceptance:* AT-001, AT-002, AT-003. *Dependencies:* `users`, NFR-004. *Phase:* 2 (API), 3 (UI).

**FR-002 — Role-based authorization**
- *Description:* Each endpoint and tool declares required permissions (doc 03); the backend denies by default.
- *Actor:* All. *Preconditions:* Authenticated. *Trigger:* Any protected request or tool call.
- *Expected behavior:* Role-permission check occurs in a backend dependency before any data access.
- *Success:* Permitted request proceeds. *Failure:* 403 `FORBIDDEN`; audit `ACCESS_DENIED` with resource type and reason code.
- *Priority:* Must. *Acceptance:* AT-004, AT-006, AT-038, AT-052. *Dependencies:* doc 03. *Phase:* 2.

**FR-003 — Resource ownership and scope enforcement**
- *Description:* Record access is filtered by the authenticated user's ownership, membership, or case assignment — never by a client-supplied user ID.
- *Actor:* All. *Preconditions:* Authenticated, role permitted. *Trigger:* Request referencing a claim, plan, document, checklist, case, session or message.
- *Expected behavior:* Queries include the ownership predicate (e.g., `claims.member_id = current_member_id`). Not-owned and nonexistent records are indistinguishable to the caller.
- *Success:* Owned record returned. *Failure:* 404 `RESOURCE_NOT_FOUND`; audit `ACCESS_DENIED` (internal reason `NOT_OWNER` vs `NOT_EXISTS` recorded only in the audit log).
- *Priority:* Must. *Acceptance:* AT-005, AT-012, AT-026, AT-034, AT-044. *Dependencies:* doc 03 §3, doc 05. *Phase:* 2.

### 7.2 Conversational assistant

**FR-004 — Chat message processing and sessions**
- *Description:* Accept a user message, create or continue a conversation session owned by the user, and return a structured assistant response.
- *Actor:* MEMBER, PROVIDER, SUPPORT_AGENT, ADMIN. *Preconditions:* Authenticated. *Trigger:* `POST /api/v1/chat`.
- *Expected behavior:* Validate message (1–4,000 chars after trimming); validate `session_id` ownership if supplied; persist user message; run orchestration; persist assistant message with intent, evidence status, citations, tool summaries and latency. Context = last 10 messages of the session (configurable).
- *Success:* 200 with `ChatResponse` (doc 06). *Failure:* 422 validation; 404 for a foreign session; 503 `AI_SERVICE_UNAVAILABLE` if the LLM fails — no partial or fabricated answer is stored as successful.
- *Priority:* Must. *Acceptance:* AT-007, AT-008. *Dependencies:* FR-005, `conversation_sessions`, `conversation_messages`. *Phase:* 4.

**FR-005 — Intent classification and routing**
- *Description:* Classify each message into one intent from the controlled taxonomy (doc 07 §1) and route it to RAG, a tool, document workflow, case workflow, or a refusal/clarification.
- *Actor:* System. *Preconditions:* FR-004. *Trigger:* Every user message.
- *Expected behavior:* Deterministic pre-rules (e.g., claim-number pattern `SYN-CLM-\d{4}-\d{6}`) plus LLM structured classification returning an intent enum. Classification is routing only, never authorization.
- *Success:* Intent stored on the message. *Failure:* Unknown/low-confidence → `UNSUPPORTED_OR_AMBIGUOUS` → clarification (FR-006).
- *Priority:* Must. *Acceptance:* AT-009, AT-011. *Dependencies:* doc 07. *Phase:* 4 (RAG intents), 5 (tool intents).

**FR-006 — Clarifying questions**
- *Description:* When required information is missing (e.g., no claim number, ambiguous procedure), ask one targeted question instead of guessing.
- *Actor:* System. *Trigger:* Ambiguous intent or missing required tool argument.
- *Expected behavior:* Response `answer_type = CLARIFICATION`, no tool executed, no factual claims.
- *Success:* User supplies the missing detail and the flow continues in the same session. *Failure:* After 2 consecutive clarifications on the same request, offer human escalation.
- *Priority:* Must. *Acceptance:* AT-010. *Dependencies:* FR-005. *Phase:* 4.

**FR-007 — Conversation history and retention**
- *Description:* Users can list and reopen their own sessions; messages older than the configured retention period are deleted by a scheduled cleanup.
- *Actor:* All roles (own sessions only). *Trigger:* `GET /api/v1/chat/sessions`, `GET /api/v1/chat/sessions/{session_id}`.
- *Expected behavior:* Return only sessions where `user_id = current_user`. Default retention 30 days (provisional, A-07).
- *Success:* Own history returned. *Failure:* 404 for foreign or expired sessions.
- *Priority:* Must. *Acceptance:* AT-012. *Dependencies:* NFR-021. *Phase:* 4.

### 7.3 Knowledge base and RAG

**FR-008 — Knowledge document ingestion**
- *Description:* An administrator-run CLI ingests fictional documents (PDF, Markdown, TXT) with a metadata manifest, extracts text, chunks, embeds, and stores chunks with metadata.
- *Actor:* ADMIN (via deployment tooling). *Preconditions:* Manifest lists title, document_type, version, effective_date (or null), audience, plan scope. *Trigger:* `ingest` command (Phase 4).
- *Expected behavior:* Compute SHA-256 of source; skip unchanged documents (idempotent); new version of same `document_key` marks prior version `SUPERSEDED`. Missing effective dates remain null — never invented.
- *Success:* `ingestion_status = INGESTED`, chunks stored. *Failure:* `INGESTION_FAILED` with error code; no partial chunks remain (transactional).
- *Priority:* Must. *Acceptance:* AT-013. *Dependencies:* `knowledge_documents`, `document_chunks`. *Phase:* 4.

**FR-009 — Permission-aware retrieval**
- *Description:* Retrieval returns only chunks from `ACTIVE` documents whose audience permits the caller's role and whose plan scope is null or matches the caller's plan.
- *Actor:* System. *Trigger:* RAG-routed intents.
- *Expected behavior:* Filters are applied inside the SQL query, not after generation. Hybrid ranking (vector + keyword) with a relevance threshold.
- *Success:* Up to `top_k` (default 6) permitted chunks. *Failure:* No chunk above threshold → FR-012.
- *Priority:* Must. *Acceptance:* AT-014. *Dependencies:* doc 03 §6. *Phase:* 4.

**FR-010 — Grounded answer generation with citations**
- *Description:* The LLM receives only the user question, minimal context, and retrieved chunks (as delimited untrusted data) and must answer using citation markers referencing the supplied chunks.
- *Actor:* System. *Trigger:* Retrieval returned sufficient evidence.
- *Expected behavior:* Response `answer_type = DOCUMENT_GROUNDED`, `evidence_status = SUPPORTED`, citations with document title, version, effective date, section, page, and an excerpt taken from the stored chunk text (not model output).
- *Success:* Answer + ≥1 valid citation. *Failure:* LLM error → 503; no valid citations → FR-011 downgrade.
- *Priority:* Must. *Acceptance:* AT-015. *Dependencies:* FR-009, FR-011. *Phase:* 4.

**FR-011 — Citation validation**
- *Description:* Backend verifies every citation marker maps to a chunk retrieved for this request; invalid markers are removed.
- *Expected behavior:* If zero valid citations remain for a grounded answer, the response is replaced with the insufficient-evidence response. Validation outcome stored per message.
- *Priority:* Must. *Acceptance:* AT-016. *Dependencies:* FR-010, `message_citations`. *Phase:* 4.

**FR-012 — Insufficient-evidence response**
- *Description:* When evidence is missing or below threshold, respond with a standard message stating the information could not be verified, without policy facts, and offer escalation.
- *Expected behavior:* `answer_type = INSUFFICIENT_EVIDENCE`, `evidence_status = INSUFFICIENT`, `escalation.offered = true` with reason `NO_ADEQUATE_ANSWER`; event recorded for gap analysis.
- *Priority:* Must. *Acceptance:* AT-017. *Dependencies:* FR-026, FR-033. *Phase:* 4.

**FR-013 — Superseded and conflicting sources**
- *Description:* Superseded documents are excluded from retrieval by default; when retrieved active chunks disagree on the same topic, the answer presents both with citations and flags the conflict.
- *Expected behavior:* `evidence_status = CONFLICTING`; escalation offered with reason `CONFLICTING_INFORMATION`.
- *Priority:* Must. *Acceptance:* AT-018. *Dependencies:* FR-008. *Phase:* 4.

### 7.4 Structured data and tools

**FR-014 — Claim status lookup**
- *Description:* Members retrieve their own synthetic claims (list and detail) via API and via the `get_claim_status` tool.
- *Actor:* MEMBER (own); SUPPORT_AGENT (claim linked to a case assigned to them). *Trigger:* `GET /api/v1/claims`, `GET /api/v1/claims/{claim_number}`, or tool call.
- *Expected behavior:* Return claim_number, service_date, submission_date, status, status_reason_code, status_description, last_updated_at, provider display name. The assistant explains the status using the claim-status guide (RAG) but takes the status only from the tool result.
- *Success:* Values equal DB values. *Failure:* 404 for nonexistent or not-owned; tool result `NOT_FOUND`; assistant states the claim could not be found and never invents a status.
- *Priority:* Must. *Acceptance:* AT-005, AT-019, AT-020. *Dependencies:* FR-003, FR-017. *Phase:* 2 (API), 5 (tool).

**FR-015 — Plan benefits lookup**
- *Description:* Retrieve plan-level benefit entries with their source document reference.
- *Actor:* MEMBER (own plan only); PROVIDER, SUPPORT_AGENT, ADMIN (any active synthetic plan — plan terms are not member-specific). *Trigger:* `GET /api/v1/benefits/{plan_code}` or `get_plan_benefits`.
- *Success:* Plan with benefits list. *Failure:* 404 for unknown plan or (for members) a plan other than their own.
- *Priority:* Must. *Acceptance:* AT-021, AT-022. *Phase:* 2 (API), 5 (tool).

**FR-016 — Required documents lookup**
- *Description:* Return the configured documentation requirement set for a fictional procedure or workflow code, each requirement linked to its source knowledge chunk.
- *Actor:* All roles. *Trigger:* `GET /api/v1/authorization/requirements/{procedure_code}` or `get_required_documents`.
- *Success:* Active requirement set with requirements and sources. *Failure:* 404 `REQUIREMENT_SET_NOT_FOUND`; assistant says no configured requirements exist and offers escalation.
- *Priority:* Must. *Acceptance:* AT-023. *Dependencies:* `pa_requirement_sets`, `pa_requirements`. *Phase:* 5.

**FR-017 — Controlled tool execution**
- *Description:* The LLM may only *propose* tool calls from an allowlist; the backend validates the tool name, argument schema, caller permission and resource scope, then executes and records the result.
- *Expected behavior:* Lifecycle in doc 07 §4. Maximum 3 tool calls per user message. `create_support_case` is never auto-executed; it returns `CONFIRMATION_REQUIRED` and a proposed action.
- *Failure:* `INVALID_ARGUMENTS`, `PERMISSION_DENIED`, `NOT_FOUND`, `EXECUTION_ERROR` — each produces a truthful user message.
- *Priority:* Must. *Acceptance:* AT-024, AT-025, AT-026. *Dependencies:* doc 06 §5, `tool_invocations`. *Phase:* 5.

### 7.5 Document processing

**FR-018 — Document upload and validation**
- *Description:* Users upload PDF, PNG or JPEG files up to a configurable limit (default 10 MB, 20 pages).
- *Actor:* MEMBER, PROVIDER. *Trigger:* `POST /api/v1/documents` (multipart).
- *Expected behavior:* Validate extension, declared MIME type, and magic bytes; reject encrypted PDFs; compute SHA-256; store under a server-generated UUID name outside any web root; create `uploaded_documents` row owned by the user.
- *Success:* 201 with `document_id`. *Failure:* 415 `UNSUPPORTED_FILE_TYPE`, 413 `FILE_TOO_LARGE`, 422 `MALFORMED_FILE`; audit `DOCUMENT_UPLOAD_REJECTED`.
- *Priority:* Must. *Acceptance:* AT-027, AT-028, AT-029. *Phase:* 6.

**FR-019 — Text extraction with OCR fallback**
- *Description:* Extract the text layer with PyMuPDF; run OCR only on pages with insufficient text (< 50 characters, configurable) and on images.
- *Trigger:* `POST /api/v1/documents/{document_id}/analyze` creates a processing job.
- *Expected behavior:* Record extraction method per page (`TEXT_LAYER` or `OCR`) and OCR mean confidence.
- *Success:* Job proceeds to field extraction. *Failure:* Job `FAILED` with safe error code (`PDF_PARSE_ERROR`, `OCR_FAILED`, `PAGE_LIMIT_EXCEEDED`, `TIMEOUT`).
- *Priority:* Must. *Acceptance:* AT-030, AT-031. *Phase:* 6.

**FR-020 — Structured field extraction and validation**
- *Description:* Extract fields defined by the schema for the detected document type (doc 07 §5) and validate each with deterministic rules.
- *Expected behavior:* Each field records raw value, normalized value, `validation_status` (`VALID`, `ABSENT`, `ILLEGIBLE`, `INVALID_FORMAT`, `INCONSISTENT`, `LOW_CONFIDENCE`), source page, and extraction method. A raw value must appear in the document text (substring/normalized check); otherwise it is discarded and the field is `ABSENT`.
- *Success:* Job `COMPLETED` or `COMPLETED_WITH_WARNINGS`. *Priority:* Must. *Acceptance:* AT-032, AT-033, AT-055. *Phase:* 6.

**FR-021 — Document result review**
- *Description:* The owner views document metadata, job status, extracted fields and warnings.
- *Actor:* Owner; SUPPORT_AGENT for documents linked to an assigned case. *Trigger:* `GET /api/v1/documents/{document_id}`.
- *Failure:* 404 for others. *Priority:* Must. *Acceptance:* AT-034. *Phase:* 6.

### 7.6 Prior authorization readiness

**FR-022 — Readiness checklist generation**
- *Description:* For a procedure code and a set of the provider's analyzed documents, evaluate every requirement in the active requirement set using deterministic rules and produce one checklist item per requirement.
- *Actor:* PROVIDER. *Preconditions:* Documents owned by the caller with a `COMPLETED`/`COMPLETED_WITH_WARNINGS` job. *Trigger:* `POST /api/v1/authorization/readiness`.
- *Expected behavior:* Item status ∈ `SATISFIED`, `MISSING`, `UNREADABLE`, `NEEDS_MANUAL_REVIEW`; each item stores rule ID, evidence field IDs and requirement source chunk. Overall `readiness_status` ∈ `DOCUMENTATION_APPEARS_COMPLETE`, `DOCUMENTATION_INCOMPLETE`, `MANUAL_REVIEW_REQUIRED`. The LLM is not used to decide item status.
- *Success:* 201 with checklist. *Failure:* 404 unknown procedure/requirement set; 409 `DOCUMENT_NOT_ANALYZED`; 403 for non-providers.
- *Priority:* Must. *Acceptance:* AT-035, AT-036, AT-037, AT-038. *Phase:* 6.

**FR-023 — Reviewer summary**
- *Description:* Produce a draft summary from a deterministic template populated only with checklist data, plus the mandatory disclaimer.
- *Expected behavior:* Stored in `authorization_checklists.reviewer_summary`. No new facts may be added. *Priority:* Should. *Acceptance:* AT-039. *Phase:* 6.

**FR-024 — Non-approval disclosure**
- *Description:* Every readiness result and summary includes: "This checklist reviews documentation completeness only. It is not an authorization approval, denial, medical-necessity determination, or guarantee of coverage." Questions about approval status receive this explanation; no approval status exists in the MVP data model.
- *Priority:* Must. *Acceptance:* AT-040. *Phase:* 6.

### 7.7 Support cases and escalation

**FR-025 — Support case creation**
- *Description:* Members and providers create cases directly or by confirming a proposed action from chat.
- *Trigger:* `POST /api/v1/support-cases` with `Idempotency-Key` header.
- *Expected behavior:* Validate category, summary (10–2,000 chars), linked resources (must be owned by the caller); create case `OPEN` and an initial `support_case_events` row in one transaction; generate `case_number` (`CASE-YYYY-NNNNNN`). Linking a checklist sets its `review_state = AWAITING_REVIEW`.
- *Success:* 201 with case. Replay with same key returns the original case (200). *Failure:* Any error → no case number shown; message "Your support case could not be created. Please try again." Audit `SUPPORT_CASE_CREATE_FAILED`.
- *Priority:* Must. *Acceptance:* AT-041, AT-042. *Phase:* 5.

**FR-026 — Escalation detection**
- *Description:* Offer escalation when any trigger occurs: `NO_ADEQUATE_ANSWER`, `CONFLICTING_INFORMATION`, `USER_REQUESTED_HUMAN`, `DOCUMENT_REQUIRES_REVIEW`, `TOOL_FAILURE`, `APPROVAL_REQUIRED`, `OUT_OF_SCOPE`.
- *Expected behavior:* Response includes a `CREATE_SUPPORT_CASE` proposed action with a prefilled draft; creation happens only after user confirmation (FR-025).
- *Priority:* Must. *Acceptance:* AT-043. *Phase:* 4 (offer), 7 (full rules).

**FR-027 — Case listing and detail**
- *Description:* Creators see their cases; support agents see unassigned cases (queue) and cases assigned to them; admins see metadata and summaries of all cases.
- *Trigger:* `GET /api/v1/support-cases`, `GET /api/v1/support-cases/{case_id}`.
- *Priority:* Must. *Acceptance:* AT-044, AT-045. *Phase:* 5 (creator), 7 (agent/admin).

**FR-028 — Case assignment**
- *Description:* Support agents may self-assign an unassigned `OPEN` case; admins may assign or reassign any non-closed case to an active support agent.
- *Trigger:* `PATCH /api/v1/support-cases/{case_id}` with `assigned_to_user_id` (admin) or `assign_to_me: true` (agent).
- *Failure:* 403 for others; 422 if the assignee is not an active `SUPPORT_AGENT`. *Priority:* Must. *Acceptance:* AT-046. *Phase:* 7.

**FR-029 — Case status update**
- *Description:* Status changes follow the transition table in doc 02 §3.1, require the current `version` (optimistic locking), and append a history event.
- *Failure:* 409 `INVALID_STATUS_TRANSITION`, 409 `VERSION_CONFLICT`, 403 for unauthorized actors. *Priority:* Must. *Acceptance:* AT-047, AT-048, AT-049. *Phase:* 7.

### 7.8 Administration, audit and feedback

**FR-030 — Aggregate metrics**
- *Description:* Admin dashboard returns counts and distributions computed from stored records for a date range: messages, intents, evidence statuses, tool outcomes, cases by status, document job outcomes, latency p50/p95, feedback ratings. Response is labeled `data_environment: "SYNTHETIC_PROTOTYPE"`.
- *Priority:* Must. *Acceptance:* AT-050. *Phase:* 7.

**FR-031 — Audit event recording**
- *Description:* The backend writes an append-only audit event for each action listed in doc 09 §5 with actor, action, resource type/ID, outcome, reason code, request ID and timestamp — never message text, document text, passwords, or tokens.
- *Priority:* Must. *Acceptance:* AT-051. *Phase:* 2 (infrastructure), extended in each phase.

**FR-032 — Audit event viewing**
- *Description:* Admins query audit events with filters (date range, action, outcome, actor, resource type) and pagination.
- *Priority:* Must. *Acceptance:* AT-052. *Phase:* 7.

**FR-033 — Knowledge gap analysis**
- *Description:* Aggregate insufficient-evidence and conflicting-evidence messages, requirement-set misses, and tool failures by normalized topic for admins, without showing user identities.
- *Priority:* Should. *Acceptance:* AT-053. *Phase:* 7.

**FR-034 — Answer feedback**
- *Description:* Users rate their own assistant messages (`HELPFUL` / `NOT_HELPFUL`) with an optional comment ≤ 500 chars; one rating per message per user (updatable).
- *Priority:* Should. *Acceptance:* AT-054. *Phase:* 7.

**FR-035 — Next-best-action suggestions**
- *Description:* Responses may include proposed actions from a fixed list (`CREATE_SUPPORT_CASE`, `UPLOAD_DOCUMENT`, `START_READINESS_CHECK`, `VIEW_CLAIM`, `VIEW_CASE`) selected by deterministic rules from the intent, evidence status and tool results, filtered by role.
- *Priority:* Should. *Acceptance:* AT-059. *Phase:* 7 (basic offers exist from Phase 4/5).

**FR-036 — Health check**
- *Description:* Public `GET /api/v1/health` reports `ok`/`degraded` for the API and database connectivity only, without versions, hostnames or configuration.
- *Priority:* Must. *Acceptance:* AT-058. *Phase:* 2.

---

## 8. Non-Functional Requirements

Thresholds marked **(provisional)** are initial targets for the local Docker environment with seed-scale data; they must be validated in Phase 8 and are not production commitments.

| ID | Category | Requirement | Measure / threshold | Verification |
|---|---|---|---|---|
| NFR-001 | Security | All endpoints except `/health` and `/auth/login` require a valid token; default-deny authorization. | 100% of protected routes return 401 without a token | Automated route-inventory test (AT-003) |
| NFR-002 | Access control | Authorization decisions are made in backend service code, never by the frontend or LLM. | Every resource endpoint and tool has ≥1 negative authorization test | Test inventory review, AT-004–AT-006, AT-026 |
| NFR-003 | Privacy | Data minimization: logs and audit events contain no message text, document text, passwords, tokens or full extracted values. | 0 occurrences in log-scan test | AT-051, AT-057 |
| NFR-004 | Security | Passwords hashed with argon2id (fallback bcrypt cost ≥ 12); never logged or returned. | Hash format check | Unit test |
| NFR-005 | Performance | Structured lookups (`/claims`, `/benefits`, `/support-cases`) respond quickly. | p95 ≤ 500 ms at 10 concurrent users (provisional) | Phase 8 load test |
| NFR-006 | Performance | Chat responses requiring RAG + LLM. | p95 ≤ 10 s, p50 ≤ 5 s (provisional; depends on D-01) | Latency recorded per message; Phase 8 |
| NFR-007 | Performance | Document processing. | Text PDF ≤ 10 pages in ≤ 30 s; OCR ≤ 15 s/page (provisional) | Phase 6/8 benchmark |
| NFR-008 | Reliability | External AI calls use timeouts (LLM 30 s, embeddings 10 s) and at most 1 retry; failures surface as errors, never as fabricated answers. | Fault-injection test passes | AT-042-style failure tests |
| NFR-009 | Error handling | All errors use the standard error format (doc 06 §4) with a request ID; no stack traces or internal details. | 100% of error responses conform | AT-057 |
| NFR-010 | Observability | Structured JSON logs with `request_id`, route, status, latency; metrics derivable from DB. | Every request log line has `request_id` | Log inspection test |
| NFR-011 | Maintainability | Layered code (routers → services → repositories); linting and typing pass (ruff, mypy, eslint, tsc). | CI lint/type jobs green | Phase 2+ CI |
| NFR-012 | Testability | LLM, embeddings and OCR behind interfaces with deterministic test doubles; backend service/authorization coverage target ≥ 80%. | Coverage report | Phase 8 |
| NFR-013 | Reproducibility | Clean install with Docker Compose and documented commands; dependencies pinned; seed script deterministic. | Fresh-machine install succeeds following README | AT-063 |
| NFR-014 | Usability | Every async action shows loading, success and error text; primary tasks reachable within 3 clicks of the role's home screen. | UX checklist review | Phase 3/8 |
| NFR-015 | Accessibility | Target WCAG 2.1 AA for primary screens; statuses never conveyed by color alone. | 0 serious/critical axe violations | AT-062 |
| NFR-016 | Scalability | Stateless API processes; MVP sized for ≤ 50 concurrent users, ≤ 200 knowledge documents, ≤ 20,000 chunks (provisional). | Design review; load test | Phase 8 |
| NFR-017 | Data integrity | FKs, NOT NULL, CHECK constraints on enums, unique keys; multi-row writes (case + event, checklist + items) are transactional. | Constraint tests | Phase 2 tests |
| NFR-018 | Explainability | Grounded answers display source title, version, effective date (or "not stated"), passage excerpt and evidence status. | UI and API contract tests | AT-015 |
| NFR-019 | Secret management | Secrets only via environment variables; `.env` git-ignored; `.env.example` has no real values. | Secret scan finds 0 secrets | AT-061 |
| NFR-020 | Resource limits | Rate limits: login 5 failures/15 min/account; chat 20 messages/min/user; uploads 20/hour/user; request body ≤ 11 MB. | 429 returned when exceeded | AT-060 |
| NFR-021 | Retention | Configurable retention: conversations 30 days, uploaded files 30 days, audit events 365 days (provisional defaults); cleanup job deletes expired data. | Cleanup test with time travel | Phase 7/8 |
| NFR-022 | Compatibility | Latest stable Chrome, Edge, Firefox; layouts usable from 360 px width. | Manual + E2E viewport tests | Phase 3/8 |

---

## 9. Assumptions and Dependencies

| ID | Assumption / dependency | Reason needed | Effect on design | Validation | Responsible |
|---|---|---|---|---|---|
| A-01 | All data and documents are synthetic or fictional and marked `is_synthetic = true`. | No approved real data exists. | Simplifies privacy posture; IDs prefixed `SYN-`. | Seed review; data-scan test | Project owner, Phase 2 |
| A-02 | An LLM with structured output / tool-calling support will be available via an approved provider; the exact provider is unknown. | Generation, classification, extraction. | Provider-agnostic `LLMAdapter`; deterministic stub for tests. | D-01 decision before Phase 4 | Project owner + mentor |
| A-03 | A CPU-capable local embedding model is acceptable (provisional `BAAI/bge-small-en-v1.5`, 384 dims). | Embeddings without sending documents externally. | `vector(384)` column; dimension configurable via migration. | Phase 4 retrieval evaluation | Phase 4 |
| A-04 | Local email/password auth is acceptable for the prototype. | No approved identity provider. | `users.password_hash`; JWT access tokens. Auth isolated to swap for OIDC later. | D-02 | Phase 2 |
| A-05 | PostgreSQL 16 with pgvector runs locally via Docker. | Single datastore. | One DB for structured and vector data. | Phase 2 setup | Phase 2 |
| A-06 | Uploaded files are stored on a local filesystem volume. | No approved object storage. | `FileStorage` interface; `storage_key` column. | D-04 | Phase 6 |
| A-07 | Retention periods are provisional defaults (30/30/365 days). | No organizational policy provided. | Configurable settings, cleanup job. | D-06 | Phase 7 |
| A-08 | No company-specific requirements, workflows or PA rules are available. | Avoid inventing facts. | Fictional requirement sets and documents only. | Mentor confirmation | Project owner |
| A-09 | Use of real healthcare data requires prior security, privacy, legal and compliance approval by the responsible organization. | Regulatory and ethical obligations. | Out of scope; synthetic-only guardrails. | N/A for MVP | Responsible organization |
| A-10 | No approved provider–member relationship model exists. | Providers must not see arbitrary members' data. | Providers have no member-record access in MVP. | D-08 | Future |
| A-11 | Tesseract OCR 5.x can be installed in the backend container. | Scanned documents. | OCR adapter; English language pack. | Phase 6 spike | Phase 6 |
| A-12 | Deployment target for the prototype is local Docker Compose; any hosted deployment needs approval. | Unknown environment. | Compose-first; no cloud-specific services. | D-05 | Phase 8 |
| A-13 | Single support organization handles all cases in the MVP. | Simplify assignment. | Agents belong to the single `SUPPORT_CENTER` organization. | Design review | Phase 7 |
