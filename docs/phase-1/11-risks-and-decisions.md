# 11 — Technical Risks and Decision Register

Likelihood and impact: High / Medium / Low. Priority = combined judgement (P1 highest).

## 1. Risk Register

| ID | Risk | Likelihood | Impact | Priority | Mitigation | Verification | Owner / workstream |
|---|---|---|---|---|---|---|---|
| R-01 | Approved LLM service unavailable, delayed or unaffordable | M | H | P1 | `LLMAdapter` with `StubLLM` for development/tests; local-model fallback (e.g., via Ollama) evaluated in Phase 4; no feature depends on one provider's proprietary API | Adapter contract tests run against stub and at least one real provider | AI (Phase 4) |
| R-02 | Hallucinated answers | M | H | P1 | Grounding-only prompts, sufficiency gate, citation validation, insufficient-evidence downgrade, tool values rendered from records | AT-015–AT-017; citation-support sampling | AI (Phase 4/8) |
| R-03 | Poor retrieval quality | M | H | P1 | Hybrid search, heading-aware chunking, chunk-size experiments, eval set with gold chunks; reranker only if justified | recall@6, MRR (doc 07 §2.10) | AI (Phase 4) |
| R-04 | Conflicting or outdated documents | M | M | P2 | Versioning, single active version per key, superseded exclusion, conflict flagging | AT-013, AT-018 | AI (Phase 4) |
| R-05 | OCR / extraction errors | H | M | P1 | Text layer first; OCR confidence thresholds; grounding check; field validation; user review of all fields; manual-review statuses | AT-031–AT-033; field accuracy on labeled set | Documents (Phase 6) |
| R-06 | Unauthorized data retrieval | M | H | P1 | Scoped repositories, identical 404s, permission inventory test, no user IDs in tool args | AT-004–AT-006, AT-026, AT-034, AT-044, AT-045 | Backend (Phase 2/5) |
| R-07 | Prompt injection | H | M | P1 | Channel separation, no tools in extraction, deterministic decisions, injection regression tests | AT-055, AT-056 | AI + Security (Phase 4/6/8) |
| R-08 | Invalid workflow execution (duplicate/phantom cases, bad transitions) | M | M | P2 | Confirmation, idempotency keys, transactions, transition table, optimistic locking, honest failure messages | AT-041–AT-043, AT-047–AT-049 | Backend (Phase 5/7) |
| R-09 | LLM cost and latency | M | M | P2 | Small context windows, top_k = 6, deterministic pre-routing, provisional latency targets, latency logging | NFR-006 measurement | AI (Phase 4/8) |
| R-10 | Oversized or malicious uploads | M | H | P1 | Size/page/pixel limits, magic-byte checks, timeouts, non-root container, dependency audits | AT-027–AT-030 | Documents + Security (Phase 6) |
| R-11 | Incomplete audit trail | M | M | P2 | Central audit service; catalogue (doc 09 §5); coverage test over demo scenario | AT-051 | Backend (Phase 2–7) |
| R-12 | Excessive project scope | H | H | P1 | MoSCoW priorities; one complete path first (demo scenario); future features excluded from MVP acceptance | Phase gate reviews against doc 10 | Project owner |
| R-13 | Insufficient testing data | M | M | P2 | Author synthetic documents and labeled sets alongside features; grow eval set to 100–200 items | Eval set size and coverage report | QA (Phase 4–8) |
| R-14 | Deployment environment limitations (no Docker, no Tesseract, low RAM for embeddings) | M | M | P2 | Docker Compose; CPU-sized embedding model; documented native fallback setup | AT-063 on a second machine | DevOps (Phase 2/8) |
| R-15 | Windows development environment differences (paths, Tesseract/libmagic install) | M | L | P3 | Run backend inside Docker; avoid OS-specific paths | Phase 2 setup on the developer machine | DevOps (Phase 2) |
| R-16 | Misinterpretation of readiness as approval by users | M | H | P1 | Disclaimers on every surface; no approval data model; FR-024 handling | AT-035, AT-039, AT-040 | Product (Phase 6) |

## 2. Decision Register

Unresolved external decisions do not block Phase 1; each has a provisional choice that lets Phase 2 begin.

| ID | Question | Provisional choice | Consequence of choice | Validation required before implementation | Needed by |
|---|---|---|---|---|---|
| D-01 | Which LLM provider/model is approved? | Provider-agnostic adapter; development with `StubLLM`; first real integration with whichever hosted model the mentor approves (one with tool-calling and JSON output), local-model fallback | Phase 2–3 unaffected; Phase 4 needs a decision | Mentor/organization approval of provider, data-handling terms, budget | Start of Phase 4 |
| D-02 | Which authentication approach? | Local email/password + argon2id + JWT (ADR-11) | Must implement rate limiting and revocation ourselves | Confirm no IdP is expected for the case study | Start of Phase 2 |
| D-03 | Which vector store? | pgvector in PostgreSQL (ADR-03) — **decided for MVP** | One datastore; HNSW tuning | Phase 4 latency/recall check at seed scale | Phase 4 (confirmation) |
| D-04 | Which file-storage mechanism? | Private local Docker volume behind `FileStorage` interface (ADR-09) | Single-node only | Confirm acceptable for demo/deployment target | Phase 6 |
| D-05 | Which deployment environment? | Local Docker Compose; any hosted deployment only after approval | No public URL by default | Mentor confirmation of demo format | Phase 8 |
| D-06 | Which retention requirements apply? | Configurable defaults: conversations 30 d, uploads 30 d, audit 365 d | Cleanup job required | Organizational policy, if any is provided | Phase 7 |
| D-07 | Which embedding model? | `BAAI/bge-small-en-v1.5` (384-d, local CPU) | `vector(384)` column; re-embed if changed | Phase 4 retrieval experiment vs. one alternative | Phase 4 |
| D-08 | Is a provider–member relationship model approved? | No — provider access to member records is out of scope | Providers cannot look up claims | Only revisited with an approved relationship/consent design | Future |
| D-09 | Is the JWT kept only in memory (re-login on reload) acceptable UX for the demo? | Yes for MVP | Page reload logs the user out | Revisit in Phase 3; alternative is an HttpOnly refresh cookie with CSRF protection | Phase 3 |
