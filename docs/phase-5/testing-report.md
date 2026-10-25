# Phase 5 — Testing Report

Run on 2026-10-25 on Windows 11, Python 3 venv, PostgreSQL 18 (local dev cluster on 127.0.0.1:55432). Only results actually observed are reported here.

## 1. Summary

| Suite | Command | Result |
|---|---|---|
| Backend lint | `ruff check app tests scripts` | All checks passed |
| Backend tests | `python -m pytest` (from `backend/`) | **270 passed**, 0 failed, 0 skipped |
| Migration drift | `alembic check` | No new upgrade operations detected |
| Frontend typecheck | `npx tsc --noEmit` | 0 errors |
| Frontend lint | `npm run lint` | 0 problems |
| Frontend tests | `npx vitest run` | **81 passed** (5 files) |
| Evaluation | `python -m scripts.evaluate_rag` (real `bge-small` embeddings, extractive generator) | 87.8% behavior (115/131); see §4 |
| Browser end to end | live backend + Vite dev server | passed; see §5 |

## 2. New backend tests (61)

| File | Tests | Covers |
|---|---|---|
| `tests/unit/test_tools_unit.py` | 10 | Allowlist is exactly 4 tools, with only `create_support_case` writing and requiring confirmation. Model schemas forbid extra properties and expose no identity fields. Malformed or SQL-like claim numbers are rejected. Exactly one procedure identifier is allowed. Server-controlled case fields (`status`, `created_by_user_id`) and invalid enums are rejected |
| `tests/integration/test_tools.py` | 16 | Unknown or injected tool names are rejected and logged. Non-object and extra-field arguments never reach the service. A member reads their own claim (`tool_invocations` row and `TOOL_INVOKED` audit checked). Another member's claim returns NOT_FOUND with a `NOT_OWNER` audit row. Listing returns own claims only. Admin and provider get PERMISSION_DENIED. Members can't read another plan's benefits. Providers must name a plan. Requirements carry verified source chunks plus the disclaimer. Unknown procedures return NOT_FOUND. The case tool writes nothing. Agents and admins can't propose cases. The call budget returns CALL_LIMIT_REACHED. A DB outage returns EXECUTION_ERROR with no data and no internals |
| `tests/api/test_support_cases.py` | 21 | 201 with OPEN status, atomic audit row, and no summary text in the audit. Same-key replay returns 200 with the same case and only 1 row. Same key with a different body returns 409. The same key from another user creates a separate case. Missing, empty or non-UUID keys return 400. Server-controlled fields return 422. Agent and admin get 403. A foreign session or claim link returns 404. A failed audit insert leaves **no phantom case**. Cases are visible only to their creator (404 plus audit for others). Status filter. 401 unauthenticated. Requirements endpoint returns sources, 404 and 422. Every `SUPPORT_CASE_CREATED` audit row refers to a case that exists |
| `tests/api/test_chat_tools.py` | 14 | Router: claim record answer; other member's claim not revealed; admin denied; benefits default to own plan; requirements cite source documents; case request is only a proposal, then confirmed with the prefilled key (201, linked session); records persist in history; an injected document can't trigger tools. **Claude with a scripted SDK client:** tool calls run through the executor (`requested_by=llm`); a cross-member claim is NOT_FOUND and no data leaks into the model context; unknown tool and malformed args return `is_error` results; the loop is bounded (5 rounds, then 503) with CALL_LIMIT_REACHED audited; a model claiming "I have created case CASE-2026-424242" is overridden; a model claiming an approval is overridden |

Updated existing tests:
- route contract: 12 authenticated routes and the new schemas;
- migrations: 5 new tables, revision `0003`;
- routing parametrization: new routes, plus three regression cases found by the evaluation;
- chat: escalation is now available to members, and the claim case moved to the tool tests.

## 3. New frontend tests (11, `src/pages/cases.test.tsx`)

- Claim and requirement record cards render from `records`. A requirement with no verified source is flagged.
- Malformed records (wrong shape, unknown `kind`) make the response invalid, so it is not shown.
- Case confirmation:
  - nothing is sent before confirming, and cancelling sends nothing;
  - the POST carries the server-issued `Idempotency-Key` and exactly the prefilled body;
  - after a 500, no case number is shown and the retry reuses the **same** key;
  - unavailable actions stay disabled.
- Cases screen:
  - list and detail with history;
  - status filter sent as a query parameter;
  - the create form validates the minimum length, confirms, then shows the backend's case number;
  - the screen isn't offered to support agents.

## 4. Evaluation (`rag_eval_v1`, 131 items)

| Metric | Phase 4 final | Phase 5 |
|---|---|---|
| Expected behavior matched | 87.8% | **87.8% (115/131)** |
| Retrieval recall@5 | 100% | 100% (81/81) |
| MRR@5 | 0.992 | 0.992 |
| Required facts present | 77.3% | 78.7% (59/75) |
| Forbidden or superseded citations | 0 / 0 | 0 / 0 |
| Unauthorized candidates | 0 | 0 |
| claim-status category | 100% (expected UNSUPPORTED) | 100% (expected TOOL / TOOL_NOT_FOUND) |
| unavailable-tool category | 100% | 100% |

Dataset changes (`data/evaluation/build_eval_set.py`), all intended Phase 5 behavior:
- RAG-117, 118, 119 and 121 now expect `TOOL` (the claim answers come from the record).
- RAG-120 (another member's claim) now expects `TOOL_NOT_FOUND`.
- RAG-125 ("talk to a human") now expects `PROPOSE_CASE`.
- RAG-055 ("back MRI preauth checklist") accepts `ANSWER` or `TOOL`.

The runner labels tool turns from the executor status, not the answer text. It runs as a seeded user per role with audit and tool-invocation writes disabled and rolls back each item, so the run is read-only.

The first Phase 5 run scored 81.7% and exposed two routing regressions, both fixed and covered by unit tests:
- "the form" was routed to requirements before the too-short check;
- "what happens after I open a ticket" was routed to case creation.

The remaining mismatches are the same retrieval and extractive-answer limits documented in Phase 4.

## 5. Browser end-to-end check (member account, live API)

1. "What is the status of my claim SYN-CLM-2026-000101?"
   - Result: record card (Pending information), "Claim lookup" badge, and the explanation cited from the Claims Status Guide.
   - This showed that an unrelated status sentence with leftover markdown was included. Fixed: only sentences about that status are kept, and only their sources are cited. Re-checked in the browser.
2. "Please open a support case: my claim … needs review"
   - Result: "prepared… not created yet" and a **Create support case** button. Nothing was written.
3. Confirm dialog → Create case
   - Result: "Support case CASE-2026-000001 created".
   - The Support cases page showed the case OPEN, with category, summary and the history line "Created (Open) by Priya Synthetic".

## 6. Not tested / limits

- Claude (`LLM_PROVIDER=anthropic`) was **never called live**. Only scripted-client tests exist.
- No load, concurrency or penetration testing. The idempotency race is covered by the unique-constraint path in code, not by a concurrent test.
- The browser check covered the member role only. Other roles are covered by API and Vitest tests.
