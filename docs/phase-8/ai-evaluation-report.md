# Phase 8 — AI Evaluation Report

What was measured, how, and what remains unmeasured. **All AI results here are from the LLM-free configuration** (`LLM_PROVIDER=extractive`: local `bge-small` embeddings plus an extractive answerer that quotes retrieved sentences). No live LLM was evaluated, because there is no approved API key. Claude paths are covered by mocked or scripted-client tests only, and those tests check control flow, not answer quality.

## 1. RAG evaluation (`scripts/evaluate_rag.py`, run 2026-10-31, after adding the heart-surgery guide)

**Dataset:** `backend/data/evaluation/rag_eval_v1.jsonl`, 131 synthetic questions written for this project (builder `data/evaluation/build_eval_set.py`). Each item has:
- an expected behavior (ANSWER / INSUFFICIENT / CLARIFY / UNSUPPORTED / CONFLICT / TOOL / TOOL_NOT_FOUND / PROPOSE_CASE);
- expected source documents (by key);
- required facts (substrings a correct answer must contain);
- forbidden sources.

**Corpus:** 15 synthetic knowledge documents, including a superseded version and a deliberately conflicting pair.

| Category | Items | Behavior matched |
|---|---|---|
| strong evidence | 40 | 95.0% (38) |
| paraphrased wording | 20 | 55.0% (11) |
| multi-passage | 8 | 100% |
| partial / weak evidence | 8 | 50.0% (4) |
| no supporting source | 15 | 100% |
| incorrect assumption | 6 | 100% |
| ambiguous | 5 | 100% |
| conflicting sources | 4 | 75.0% (3) |
| outdated document | 4 | 100% |
| prompt injection | 6 | 100% |
| account-specific claim status (tool) | 6 | 100% |
| unavailable tool / out of scope | 5 | 100% |
| access boundary | 4 | 100% |
| **All** | **131** | **87.8% (115)** |

| Retrieval metric (81 answerable items with labeled sources) | Result |
|---|---|
| Recall@5 (an expected source is in the top 5) | 100% (81/81) |
| MRR@5 | 0.992 |
| Precision@5 (share of top-5 chunks from a labeled source) | 0.519 |
| Wrong-version retrieval → cited | 0 answers cited a superseded document |
| Unauthorized candidates | 0 items where another audience's or plan's document was even retrieved |

Precision@5 understates relevance: each question labels only its primary source, so passages from other relevant documents (for example a plan guide and a prior-authorization guide) count as non-matches. Similarity scores are not used as accuracy.

| Answer metric | Result |
|---|---|
| Required facts present (answered, answerable items) | 78.7% (59/75) |
| Answers containing all required facts | 76.1% (51/67) |
| Answers citing an expected source | 98.6% (70/71) |
| Answers citing a forbidden source | 0 |
| Invalid citations reaching the client | 0. Every marker is validated against the evidence supplied for that request (`test_chat::test_invalid_citations_are_removed_or_downgraded`) |

**Mismatches (16):**
- **Paraphrases (9):** most are informal wording whose best passage scores below the 0.70 relevance gate (for example "what's my out of pocket for going to the ER"). These return "insufficient evidence", a safe failure, not a wrong answer.
- **Partial-evidence items (4):** they were answered from partially relevant text instead of being declined.
- **Conflict item RAG-106 (1):** answered from one source without flagging the conflict.
- **Two strong-evidence items:** gated as insufficient.

All mismatches err toward under-answering, with one exception: the partial and conflict items answered when they should have declined or flagged. Those are the cases a live LLM should be evaluated on first.

**Unsupported-claim rate:** in extractive mode every sentence in an answer is a verbatim quote of a cited passage, so unsupported claims are 0 *by construction*. That does not measure a generative model. A human-reviewed sample is required once an LLM is enabled.

**Method limits:**
- Fact checks are substring matches.
- Correct citation *support* (the passage really backs the sentence) was checked by construction in extractive mode only.
- The dataset is self-authored and synthetic, so it isn't representative of real member language.

## 2. Tool-calling evaluation

| Check | Evidence | Result |
|---|---|---|
| Correct tool choice (router) | Eval "claim-status" 6/6 (TOOL, TOOL_NOT_FOUND for another member's claim); `test_chat_tools` router tests | Pass |
| Unknown or invalid tool request; malformed and extra arguments | `int/test_tools`, `test_chat_tools::test_unknown_tool_and_malformed_arguments…` (scripted Claude) | Rejected, returned as errors to the model |
| Permission denial | Admin/provider claim lookup → PERMISSION_DENIED + audit | Pass |
| Call budget / bounded loop | 3 calls per message; scripted model looping forever → 503 after 5 rounds | Pass |
| Confirmation for writes; duplicate writes | `create_support_case` only proposes; the case is created by a confirmed POST with an Idempotency-Key (replay 200, different body 409) | Pass |
| False claims of success | Scripted model claiming "created case CASE-2026-424242" or an approval → overridden | Pass |
| Prompt injection to create or claim a case | `test_phase8::test_prompt_injection_cannot_create_or_claim_a_case` | No case created, no fake number |

The Claude tool loop was exercised only with a **scripted** SDK client. Tool-choice quality of a real model is unmeasured.

## 3. Document AI and readiness (`scripts/evaluate_documents.py`, run 2026-10-27)

**Corpus:** 13 synthetic documents with manually defined ground truth (`backend/data/samples/documents/expected.json`):
- 10 text-layer PDFs: PA request forms (complete, incomplete, conflicting, prompt-injection), a PT form, 3 referral letters, 1 clinical note, and 1 unrecognized letter;
- 3 that need OCR: a PNG scan, an image-only PDF, and a mixed PDF.

Extraction is deterministic (labeled lines plus patterns). The optional LLM extraction was not used. **OCR engine: Tesseract configured but not installed.**

| Metric (10 scored documents, 65 fields) | Result |
|---|---|
| Document-type accuracy | 100% (10/10) |
| Field validation-status accuracy | 100% (65/65) |
| Exact match (status + normalized value) | 100% (65/65) |
| VALID-field precision / recall | 100% (53/53) / 100% (53/53) |
| Missing-field (ABSENT) detection precision / recall | 100% (10/10) / 100% (10/10) |
| Date and identifier validation | Covered by unit tests (impossible dates → INVALID_FORMAT, unknown procedure codes, conflicting member numbers → INCONSISTENT) |

| Readiness (9 scored scenarios, 48 items) | Result |
|---|---|
| Item status accuracy | 100% (48/48) |
| Overall readiness status accuracy | 100% (9/9) |
| SATISFIED / MISSING / UNREADABLE / NEEDS_MANUAL_REVIEW | 25/25 · 9/9 · 1/1 · 13/13 |
| OCR failure not treated as absence | The mixed PDF's NPI on its unread page 2 → `ILLEGIBLE` → item `UNREADABLE` (not MISSING); also the API test `test_missing_and_unreadable_are_distinguished` |
| Contradictions → manual review | Conflicting form → REQ-MRI-01/04 NEEDS_MANUAL_REVIEW |
| Summary counts = persisted checklist | `test_counts_and_summary_match_persisted_items` |
| No approval wording | Disclaimer present; tests assert there's no approval claim |

**Not scored:** the 3 OCR documents. Without OCR, the PNG and image-only PDF are `UNRECOGNIZED` with no fields, and the job fails honestly with `OCR_FAILED`. Processing time for text PDFs was 8–62 ms; image PDFs took about 0.7–0.85 s, rendering included.

**Limits:**
- The extractor and the corpus were written by the same project in the same label format. The 100% figures show that the rules work as specified; they don't show accuracy on real documents.
- No handwriting, tables or noisy scans were tested.
- The confidence thresholds are uncalibrated.

## 4. What must happen before trusting AI quality

1. Run `evaluate_rag` with an approved model (`LLM_PROVIDER=anthropic`), and human-review a sample for unsupported claims and citation support.
2. Install Tesseract and score the OCR documents. Add real-layout synthetic scans.
3. Extend the question set with real (de-identified, approved) phrasing, and re-tune `RAG_MIN_RELEVANCE` on it.
