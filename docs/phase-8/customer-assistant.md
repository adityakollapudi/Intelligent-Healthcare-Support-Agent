# Customer-Friendly, Multilingual Assistant

How the existing IHSA assistant was extended to be the customer's first point of help, in English, Telugu and Hindi. No separate chatbot was built. Synthetic data only.

## 1. Existing architecture (before this work)

| Part | Where | Role |
|---|---|---|
| Chat service | `app/services/chat_service.py` | Sessions, saving messages, audit |
| Orchestrator | `app/rag/pipeline.py` | Route → tool or retrieval → generate → validate |
| Router | `app/rag/intent.py` | Deterministic intent rules, including refusals |
| Generators | `app/rag/generation.py` | Extractive (default, no LLM) or Claude (not run live) |
| Prompts | `app/rag/prompts.py` | System prompt and tool rules |
| Tools | `app/tools/` | Allowlist, schemas, permissions, audit |
| Chat UI | `frontend/src/pages/ChatPage.tsx`, `features/chat/chat-state.tsx` | Conversation screen and state |

The new layer runs **after** the pipeline. Routing, tools, permissions, citations and the false-claim guard are unchanged, and the RAG evaluation is unchanged (87.8%, 115/131).

## 2. How it works

| Need | Implementation |
|---|---|
| Plain language | `app/rag/friendly.py` turns each result into short sections: what it means, what to do next. Jargon is explained using a glossary. All values come from tools, the database or documents |
| Three languages | `app/rag/friendly_text.py` holds the wording in English, Telugu and Hindi |
| Language choice | `app/rag/language.py`: text in Telugu or Hindi script is answered in that language; Latin text follows the selector |
| Telugu/Hindi questions | Keyword matching maps them to questions the router already handles. Unrecognized questions get guided help, never a guess. Free text from these questions never reaches the pipeline |
| Translation | `POST /chat/messages/{id}/translate`, owner only. `app/services/translation.py` is the provider abstraction |
| Guided help | New `GUIDED` and `SIMPLIFY` routes offer simple choices, which send normal chat messages |
| Handoff | Case proposals now include the customer's recent questions. A case is still created only after confirmation, and the number shown is the backend's |

### What is and isn't translated

- **Fully in Telugu and Hindi:** welcome, quick actions, guided help, claim status explanations, benefit labels, requirement lists, readiness results, refusals and handoff messages.
- **Stays in English without a translator:** passages quoted from knowledge documents and uploads, claim notes, and benefit or file names. The answer says so.
- **Not understood:** romanized Telugu or Hindi (for example "naa claim status"), and detailed Telugu or Hindi questions beyond the keyword list. These get guided help.

### Translation provider

`TRANSLATION_PROVIDER=none` is the default. `anthropic` also needs `TRANSLATION_EXTERNAL_APPROVED=true` and a key, because answers can contain customer details. Claim numbers, dates, amounts, file names and citation markers are protected with placeholders, and the translation is rejected if any is lost. On any failure the customer keeps the English text and a note. **The live provider hasn't been run:** it's tested with fakes only.

The Telugu and Hindi wording was written for this prototype. **It has not been reviewed by a medical or insurance translator or by native-speaker reviewers.**

## 3. Updated system prompt

`PROMPT_VERSION` is now `rag-answer-v2`. Rule 8 changed:

> Write for an ordinary customer, like a helpful support person: everyday words and short sentences. If a technical term is needed, explain it straight away. Say what the information means for them and what they should do next. Keep it under about 150 words, and never lose accuracy to make something simpler. Don't promise a service is covered unless the evidence says so.

This only affects Claude mode, which hasn't been run live. In the default mode, answers quote documents, so a quoted passage can't be simplified; the glossary explains its terms instead.

## 4. Files

**New:** `backend/app/rag/language.py`, `friendly.py`, `friendly_text.py`; `backend/app/services/translation.py`; `backend/tests/api/test_customer_experience.py`; `frontend/src/features/chat/chat-i18n.ts`; this document.

**Changed:** `app/rag/intent.py`, `pipeline.py`, `prompts.py`; `app/services/chat_service.py`; `app/api/v1/routes/chat.py`; `app/schemas/chat.py`; `app/core/config.py`; `frontend/src/pages/ChatPage.tsx`, `features/chat/chat-state.tsx`, `services/index.ts`, `lib/validators.ts`, `types/api.ts`, `styles/app.css`; tests; `.env.example`; READMEs.

## 5. Test results (run 2026-11-01)

| Check | Result |
|---|---|
| Backend tests | 525 passed, 0 failed, 0 skipped; 95% coverage |
| Frontend tests | 114 passed, 0 failed |
| Lint, types, build | Clean |
| RAG evaluation | 87.8% (115/131), recall@5 100%, unchanged |
| pip-audit, secret scan | No findings |
| `npm audit --audit-level=high` | Passes. A moderate dev-only ESLint advisory remains; production dependencies have 0 |

| # | Scenario | Evidence | Result |
|---|---|---|---|
| 1–3 | Same question in English, Telugu, Hindi | Automated; live claims and benefits | Pass |
| 4 | Telugu selected, typed in English | Automated, live | Pass |
| 5 | Language changed mid-conversation | Automated | Pass |
| 6 | Complicated question | Automated, live | Pass: terms explained, or an honest "can't confirm" |
| 7 | Customer doesn't understand | Automated, live | Pass |
| 8 | Claim status | Automated, live | Pass |
| 9 | Uploaded document | Automated | Pass; quoted text stays in English |
| 10 | Missing authorization documents | Automated, live | Pass |
| 11 | No reliable answer | Automated, live | Pass |
| 12 | Human assistance | Automated | Pass; case needs confirmation |
| 13 | Translation unavailable | Automated with a failing fake | Pass; English kept, with a note |
| 14 | Another patient's information | Automated | Pass: 404, or not found |

Fixing issues found while testing: the false-claim warning was restored after the new claim layout hid it, the Authorization Process button no longer ends in "can't answer", and answers to coverage questions now state they don't confirm coverage.

Language quality and simplicity were checked by reading sample answers, not measured. No readability score or user testing was done.

## 6. Run it

No new setup is needed: start the database, API and frontend as in the deployment guide, then open http://localhost:5173 and sign in. Members land on the assistant.

Screenshots aren't included, because the browser pane was hidden during testing. The screens were checked by reading the live page.

## Everyday questions answered directly

Testing 41 customer questions found simple ones being sent to a person. These now answer directly:

- **Insurance words:** "What is a deductible?" uses the fixed glossary, with general meanings only. The new out-of-pocket entry's Telugu and Hindi wording needs human review.
- **Own account:** "What plan am I on?" and "What is my member ID?" come from the signed-in member's record.
- **Deductible and out-of-pocket maximum:** these come from the member's plan guide.
- **Primary care, specialist and emergency costs:** simple questions use the member's plan record. Searching documents had mixed in virtual visits and raised a false conflict.

The real virtual-care conflict is still reported. The RAG evaluation fell from 87.8% to 84.7% (111/131) because 4 items labelled for a document answer now use the plan record. All 4 contain the expected amount, and the evaluation set wasn't changed.
