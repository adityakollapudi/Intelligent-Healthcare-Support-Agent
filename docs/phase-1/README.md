# IHSA — Phase 1 Design Package

**Intelligent Healthcare Support Agent (IHSA)** — independent Evernorth internship case study. Synthetic data only; not an Evernorth product.

## Purpose of Phase 1

Phase 1 defines what IHSA must do and how it is structured, so Phases 2–8 can be implemented without redesigning foundations. It contains **design artifacts only** — no application code, migrations, AI pipelines or deployments exist yet. When Phase 1 began, the workspace (`D:\EverNorth_CaseStudy`) was empty, so no existing code constrained the design.

## Documents and reading order

| # | File | Purpose |
|---|---|---|
| 1 | [01-requirements-specification.md](01-requirements-specification.md) | Summary, problem, goals, scope, personas, user stories (US-001–030), functional (FR-001–036) and non-functional (NFR-001–022) requirements, assumptions (A-01–13) |
| 2 | [03-roles-and-permissions.md](03-roles-and-permissions.md) | Roles, permission catalogue, matrix, authorization rules — read before any API or query work |
| 3 | [02-use-cases-and-workflows.md](02-use-cases-and-workflows.md) | Use cases UC-01–14, workflow diagrams A–F, **authoritative status enumerations** (§3) |
| 4 | [04-system-architecture.md](04-system-architecture.md) | Stack, component responsibilities, component and trust-boundary diagrams, ADR-01–12 |
| 5 | [05-database-design.md](05-database-design.md) | 26 tables, constraints, indexes, ERD, seed plan |
| 6 | [06-api-contract.md](06-api-contract.md) | REST conventions, endpoints, error format, internal tool contracts |
| 7 | [07-ai-and-document-design.md](07-ai-and-document-design.md) | Intent taxonomy, RAG, answer rules, tool lifecycle, document extraction, readiness rules, knowledge gaps |
| 8 | [08-ui-wireframes.md](08-ui-wireframes.md) | Screens 1–8, navigation matrix, error-state behavior, accessibility |
| 9 | [09-security-and-privacy.md](09-security-and-privacy.md) | Threat model TH-01–16, security requirements, privacy, AI controls, audit catalogue, responsible AI |
| 10 | [10-traceability-and-acceptance.md](10-traceability-and-acceptance.md) | Traceability matrix, acceptance tests AT-001–063, phase dependencies |
| 11 | [11-risks-and-decisions.md](11-risks-and-decisions.md) | Risk register R-01–16, decision register D-01–09 |

## Main architecture decisions

1. React + TypeScript (Vite) frontend; FastAPI + Pydantic + SQLAlchemy/Alembic backend (ADR-01).
2. PostgreSQL 16 with **pgvector** as the single datastore for structured data and vectors; hybrid vector + full-text retrieval (ADR-02, ADR-03).
3. Backend-only tool execution with an allowlist, schema validation, permission checks and server-injected user context; the LLM proposes, the backend decides (ADR-05).
4. Deterministic readiness rules with four item statuses (`SATISFIED`, `MISSING`, `UNREADABLE`, `NEEDS_MANUAL_REVIEW`) — never approval/denial (ADR-06).
5. User-confirmed, idempotent support-case creation; assignment-scoped human review (ADR-07).
6. Provider-agnostic LLM adapter with a deterministic stub; local CPU embeddings (ADR-12, A-03).
7. Local email/password auth with argon2id + JWT, isolated for later IdP replacement (ADR-11).
8. Plain Python orchestration, single assistant, no multi-agent framework in MVP (ADR-10).
9. Providers have **no** access to member records until an approved relationship model exists (D-08).

## External decisions still to confirm

| ID | Decision | Needed by |
|---|---|---|
| D-01 | Approved LLM provider/model and data-handling terms | Start of Phase 4 |
| D-02 | Confirm local auth is acceptable (no IdP expected) | Start of Phase 2 |
| D-04 / D-05 | File storage and deployment target (provisional: local Docker volume / Docker Compose) | Phase 6 / 8 |
| D-06 | Retention policy (provisional defaults 30/30/365 days) | Phase 7 |
| D-07 | Embedding model confirmation via experiment | Phase 4 |
| D-09 | In-memory token UX acceptable for demo | Phase 3 |

None of these blocks Phase 2.

## Quality-control review (performed for Phase 1)

| Check | Result |
|---|---|
| A — Requirements | 36 FRs each with priority, phase and ≥1 acceptance test; MoSCoW priorities; future enhancements separated from MVP |
| B — Permissions | 27 permissions mapped to 4 roles; every owned entity has an access rule (doc 10 §1.3); frontend hiding documented as non-security; tools take no user identifiers |
| C — Architecture | 13 components with responsibilities and "must not control" constraints; external LLM boundary and controls identified; rules separated from AI |
| D — Database | 26 tables with keys, constraints and indexes; ERD cardinalities match nullable FKs; status values defined once (doc 02 §3); API fields map to columns |
| E — API | All endpoints list permissions, errors, side effects, audit and FR/AT links; server-controlled fields rejected; public routes vs internal tools separated |
| F — AI & workflows | Insufficient-evidence and conflict paths; citations built from DB; tool lifecycle with validation; extraction grounding; readiness disclaimers; escalation triggers |
| G — UI | Screens for every workflow (doc 10 §1.4); navigation matrix per role; loading/empty/error/denied/timeout states; actions map to routes |
| H — Traceability | Scripted cross-check: all 36 FRs in the RTM; all 63 referenced AT IDs defined; all 30 user stories traced; no undefined FR/US references; permissions used = catalogue; audit actions used = catalogue |

Fixes applied during the review: added `GET /authorization/checklists` (provider workspace needed it), made `pa_requirement_sets.source_document_id` nullable until Phase 4 ingestion, corrected ERD optionality for nullable FKs, aligned the MRI conservative-therapy requirement to a presence check (no clinical threshold), added proposed-action / job error / reason-code enumerations to doc 02 §3.9, normalized organization naming to `SUPPORT_CENTER`, and removed statement separators from Mermaid sequence messages.

Not yet verified: Mermaid diagrams have not been rendered with a Mermaid tool in this phase; syntax was reviewed manually.

## Conditions to start Phase 2

1. This package is reviewed and accepted (or change requests are applied across all affected documents).
2. D-02 confirmed (or provisional choice accepted).
3. Developer machine has Git, Docker Desktop, Python 3.12 and Node 20 LTS (or the backend runs fully in Docker).

**Phase 2 entry point:** create the repository skeleton (`backend/`, `frontend/`, `docs/`), Docker Compose with PostgreSQL 16 + pgvector, then implement — in this order — doc 05 tables via Alembic, the seed plan (doc 05 §8), `core/` (config, errors, request ID), `authz/` (permission map, scoped repositories), `GET /health`, `/auth/*`, `GET /claims`, `GET /claims/{claim_number}`, `GET /benefits/{plan_code}` and the audit service, verified by AT-001–AT-006, AT-019–AT-022, AT-057, AT-058 and AT-061.
