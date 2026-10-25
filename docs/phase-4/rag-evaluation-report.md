# RAG Evaluation Report — rag_eval_v1

All numbers below were measured on 2026-10-25 by running `python -m scripts.evaluate_rag` against the ingested synthetic corpus. Raw results: `backend/data/evaluation/results/rag_eval_v1_extractive.{md,json}`. Baseline: `…_extractive_baseline.{md,json}`.

## 1. What was and was not evaluated

| | Status |
|---|---|
| Real embeddings (`BAAI/bge-small-en-v1.5`), real PostgreSQL retrieval, permission filters | **Measured** |
| Answers from `LLM_PROVIDER=extractive` (quotes source sentences; no LLM) | **Measured** |
| Answers from Claude (`LLM_PROVIDER=anthropic`) | **Not measured.** No approved API key (decision D-01). The adapter is unit-tested with a mocked SDK only |
| Semantic support of citations (does the cited sentence really support the claim?) | **Not measured automatically.** Spot-checked by hand during browser testing. A human-reviewed sample is still needed |

## 2. Dataset

`backend/data/evaluation/rag_eval_v1.jsonl` has 131 synthetic questions, built by `data/evaluation/build_eval_set.py`. Each record has `test_id`, `category`, `role`, `question`, `expected_behavior`, `expected_source_ids`, `expected_answer_facts` (substrings) and `forbidden_source_ids`.

| Category | Items | Expected behavior |
|---|---|---|
| strong (clear evidence) | 40 | ANSWER with facts |
| paraphrase (different wording) | 20 | ANSWER |
| multi-passage | 8 | ANSWER with 2 facts |
| partial (related docs exist, answer doesn't) | 8 | INSUFFICIENT |
| no-support | 15 | INSUFFICIENT |
| incorrect-assumption | 6 | ANSWER that states the correct fact |
| ambiguous | 5 | CLARIFY |
| conflict | 4 | CONFLICT |
| outdated / superseded | 4 | ANSWER from v2.0, never v1.0 |
| prompt injection in the question | 6 | UNSUPPORTED / INSUFFICIENT (one asks a real question → ANSWER) |
| account-specific claim/case status | 6 | UNSUPPORTED (Phase 5 tools) |
| unavailable tools / medical / human | 5 | UNSUPPORTED |
| access boundary (other plan, provider-only, internal) | 4 | must not cite the forbidden source |

## 3. Configuration measured

Embedding `BAAI/bge-small-en-v1.5` (384-d, CPU) · chunking 160 words / 30 overlap, one section or page per chunk · 61 chunks from 14 documents · hybrid cosine + full-text (RRF k=60) · `RAG_TOP_K=5` · `RAG_MIN_RELEVANCE=0.70` · extractive sentence cutoff 0.70 · local Windows laptop CPU.

## 4. Results

| Metric | Baseline (first run) | Final |
|---|---|---|
| Expected behavior matched, all items | 84.0% (110/131) | **87.8% (115/131)** |
| Retrieval recall@5 (an expected source in the top 5) | 100% (82/82) | **100% (82/82)** |
| MRR@5 | 0.992 | **0.992** |
| Required facts present (answered, answerable) | 79.5% (58/73) | 77.3% (58/75) |
| Answers containing all required facts | 78.8% (52/66) | 74.6% (50/67) |
| Answers citing an expected source | 97.3% (71/73) | 98.6% (71/72) |
| Answers citing a superseded version | 0 | **0** |
| Answers citing a forbidden (out-of-scope) source | 0 | **0** |
| Items where an unauthorized document was even a retrieval candidate | 0 | **0** |
| Pipeline latency p50 / p95 (CPU; embedding included) | 29 / 39 ms | 128 / 290 ms |

| Category | Baseline | Final |
|---|---|---|
| strong | 92.5% | 95.0% |
| paraphrase | 60.0% | 55.0% |
| multi-passage | 87.5% | 100% |
| partial | 12.5% | 50.0% |
| no-support | 100% | 100% |
| incorrect-assumption | 100% | 100% |
| ambiguous | 80.0% | 100% |
| conflict | 100%* | 75.0% |
| outdated | 100% | 100% |
| injection | 83.3% | 100% |
| claim-status | 100% | 100% |
| unavailable-tool | 100% | 100% |
| access-boundary | 100% | 100% |

\* At baseline, the conflict heuristic also flagged 2 non-conflicting answers (a primary-care question and a multi-passage question), so its 100% hid false positives.

### Changes made between runs, and why

1. **The extractive answerer picks sentences by embedding similarity (cutoff 0.70) instead of word overlap.** At baseline, partial-evidence questions such as an urgent-care copay were answered with loosely related sentences, such as the primary-care copay. This was the most important safety defect. Partial handling improved from 1/8 to 4/8; paraphrase dropped from 12/20 to 11/20.
2. **Conflict detection compares individual sentences** (content-word Jaccard ≥ 0.4) across all retrieved evidence, ignores guides for *different plans*, and shows both sides. This removed the false positives (for example, Gold $25 vs Bronze $50 PT copays are not a contradiction).
3. **Routing fixes:**
   - "What about it" and one-word questions now get a clarifying question.
   - "List every member's claims" and "you are now an admin" are declined.
   - "prescription drugs covered?" is no longer misrouted as medical advice.
4. **Number preference:** "how many/long/much" questions slightly favor sentences that contain numbers (fact recall 76.0% → 77.3%).

A tried-and-reverted change: an "unknown term" rule, which refused when a question word was absent from the evidence, dropped the overall score to 64.1% and was removed.

### Threshold calibration (pre-generation gate)

| `RAG_MIN_RELEVANCE` | Answerable kept (of 78) | Partial/no-support passing (of 23) |
|---|---|---|
| 0.66 | 97.4% | 39.1% |
| 0.70 (chosen) | 92.3% | 34.8% |
| 0.74 | 80.8% | 8.7% |
| 0.78 | 65.4% | 8.7% |

0.70 keeps most answerable questions. The unanswerable ones that pass the gate are mostly stopped by the second check: the extractive sentence cutoff (or, with Claude, the model's `evidence_sufficient`). At the sentence level, answerable and partial questions overlap: partial-evidence questions reach 0.77 similarity, and some answerable ones sit at 0.68. **Similarity alone can't reliably tell "related" from "answers the question".** That judgment needs an LLM or a reranker.

## 5. Remaining failures (final run)

- **Paraphrase (9/20 missed):** colloquial wording ("family doctor", "translator", "main doctor") scores below 0.70 against the sentence that answers it, so the system says it couldn't verify. That is safe but unhelpful.
- **Partial (4/8 still answered):** for example, "urgent care copay" is answered with the ER and primary-care sentences, cited correctly but not the asked-about service. The answer is shown with sources and the extractive disclaimer, but a reader could misread it. **Highest-priority limitation for any demo:** prefer `LLM_PROVIDER=anthropic` once approved, and re-measure.
- **Missing facts (17 answered items):** the right document was cited, but the sentence holding the fact (for example "Coverage is limited to 20 visits per plan year") wasn't among the ≤3 quoted sentences.
- **Conflict (1/4 missed):** one question retrieved only one side of the contradiction.

## 6. Security tests run (automated, PostgreSQL)

- Prompt-injection document ingested: quoted as data only, with no approval wording, keys or prompt text.
- The evidence tag-escaping unit test passes.
- Injection questions are routed to refusal: 6/6 behaviors matched in the evaluation.
- Session ownership: another user's session ID returns 404, both for chat and history, with an `ACCESS_DENIED` audit event.
- Audience and plan filters: 0 unauthorized candidates across all 131 items. API tests confirm members never see internal or other-plan documents and providers never see internal ones.
- Invalid citation markers are removed or downgraded to insufficient. Malformed model JSON, refusal, truncation and timeout all return a controlled 503.
- Request validation: empty, whitespace-only, over 4,000 characters, unknown fields and bad UUIDs return 422. Unauthenticated requests return 401. The rate limit returns 429.

## 7. Limitations of this evaluation

- The same 131 items were used to tune the thresholds and the fixes; there is no held-out set. Expect lower numbers on new questions. Next step: write `rag_eval_v2` with fresh questions before further tuning.
- Fact checks are substring matches; they can't detect a wrong statement placed next to a right one.
- It's a 14-document synthetic corpus, so results won't transfer to real policy documents.
- Latency was measured on one laptop with the model already loaded. The first request after start-up also loads the model (a few seconds).
