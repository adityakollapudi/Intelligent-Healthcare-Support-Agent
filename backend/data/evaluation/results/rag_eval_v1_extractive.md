# RAG evaluation — rag_eval_v1 (extractive)

- Run: 2026-10-25T14:37:54+00:00 · items: 131 · embedding: `BAAI/bge-small-en-v1.5` · generator: `extractive`
- Chunking: 160 words / 30 overlap · top_k: 5 · RAG_MIN_RELEVANCE: 0.7

## Headline metrics

| Metric | Result |
|---|---|
| Expected behavior matched (all items) | 87.8% (115/131) |
| Retrieval recall@5 (expected source in top 5, answerable items) | 100.0% (81/81) |
| MRR@5 | 0.992 |
| Required facts present (answered, answerable items) | 78.7% (59/75) |
| Answers with all required facts | 76.1% (51/67) |
| Answers citing an expected source | 98.6% (70/71) |
| Answers citing a superseded version | 0 |
| Answers citing a forbidden (out-of-scope) source | 0 |
| Items where an unauthorized document was even a candidate | 0 |
| Pipeline latency p50 / p95 (local CPU, includes embedding) | 82 ms / 231 ms |

## Behavior by category

| Category | Matched |
|---|---|
| strong | 95.0% (38/40) |
| paraphrase | 55.0% (11/20) |
| multi-passage | 100.0% (8/8) |
| partial | 50.0% (4/8) |
| no-support | 100.0% (15/15) |
| incorrect-assumption | 100.0% (6/6) |
| ambiguous | 100.0% (5/5) |
| conflict | 75.0% (3/4) |
| outdated | 100.0% (4/4) |
| injection | 100.0% (6/6) |
| claim-status | 100.0% (6/6) |
| unavailable-tool | 100.0% (5/5) |
| access-boundary | 100.0% (4/4) |

## Similarity-threshold sweep (pre-generation gate)

Answerable items: 77; partial/no-support items: 23.

| Threshold | Answerable kept | Unanswerable passing the gate |
|---|---|---|
| 0.60 | 100.0% (77/77) | 78.3% (18/23) |
| 0.62 | 100.0% (77/77) | 69.6% (16/23) |
| 0.64 | 98.7% (76/77) | 52.2% (12/23) |
| 0.66 | 97.4% (75/77) | 39.1% (9/23) |
| 0.68 | 96.1% (74/77) | 34.8% (8/23) |
| 0.70 | 92.2% (71/77) | 34.8% (8/23) |
| 0.72 | 88.3% (68/77) | 30.4% (7/23) |
| 0.74 | 80.5% (62/77) | 8.7% (2/23) |
| 0.76 | 70.1% (54/77) | 8.7% (2/23) |
| 0.78 | 66.2% (51/77) | 8.7% (2/23) |
| 0.80 | 55.8% (43/77) | 8.7% (2/23) |

## Mismatches

| Test | Category | Expected | Actual | Best sim | Facts | Cited |
|---|---|---|---|---|---|---|
| RAG-003 | strong | ANSWER | ANSWER | 0.895 | 0/1 | gold-plan-benefit-guide, pa-physical-therapy-guide |
| RAG-017 | strong | ANSWER | ANSWER | 0.8294 | 0/1 | claims-status-guide, claims-status-guide |
| RAG-019 | strong | ANSWER | INSUFFICIENT | 0.6489 | 0/1 |  |
| RAG-027 | strong | ANSWER | ANSWER | 0.8385 | 0/1 | claim-documentation-requirements, claim-documentation-requirements |
| RAG-030 | strong | ANSWER | INSUFFICIENT | 0.7418 | 0/1 |  |
| RAG-032 | strong | ANSWER | ANSWER | 0.8932 | 0/1 | pa-imaging-guide |
| RAG-034 | strong | ANSWER | ANSWER | 0.8726 | 0/1 | pa-imaging-guide |
| RAG-035 | strong | ANSWER | ANSWER | 0.8761 | 0/1 | pa-physical-therapy-guide |
| RAG-042 | paraphrase | ANSWER | INSUFFICIENT | 0.7252 | 0/1 |  |
| RAG-044 | paraphrase | ANSWER | INSUFFICIENT | 0.6848 | 0/1 |  |
| RAG-046 | paraphrase | ANSWER | ANSWER | 0.7335 | 0/1 | claims-status-guide |
| RAG-047 | paraphrase | ANSWER | INSUFFICIENT | 0.7315 | 0/1 |  |
| RAG-048 | paraphrase | ANSWER | INSUFFICIENT | 0.6751 | 0/1 |  |
| RAG-050 | paraphrase | ANSWER | INSUFFICIENT | 0.6381 | 0/1 |  |
| RAG-051 | paraphrase | ANSWER | INSUFFICIENT | 0.6916 | 0/1 |  |
| RAG-052 | paraphrase | ANSWER | INSUFFICIENT | 0.7046 | 0/1 |  |
| RAG-053 | paraphrase | ANSWER | INSUFFICIENT | 0.6808 | 0/1 |  |
| RAG-056 | paraphrase | ANSWER | ANSWER | 0.8051 | 0/1 | pa-imaging-guide |
| RAG-057 | paraphrase | ANSWER | ANSWER | 0.7907 | 0/1 | pa-physical-therapy-guide, pa-physical-therapy-guide, gold-plan-benefit-guide |
| RAG-059 | paraphrase | ANSWER | INSUFFICIENT | 0.712 | 0/1 |  |
| RAG-061 | multi-passage | ANSWER | ANSWER | 0.8844 | 1/2 | gold-plan-benefit-guide |
| RAG-066 | multi-passage | ANSWER | ANSWER | 0.7889 | 1/2 | claims-status-guide, claims-status-guide |
| RAG-067 | multi-passage | ANSWER | ANSWER | 0.8244 | 1/2 | provider-admin-faq |
| RAG-068 | multi-passage | ANSWER | ANSWER | 0.8014 | 1/2 | virtual-care-faq |
| RAG-070 | partial | INSUFFICIENT | ANSWER | 0.8145 | 0/0 | gold-plan-benefit-guide, gold-plan-benefit-guide |
| RAG-073 | partial | INSUFFICIENT | ANSWER | 0.8121 | 0/0 | gold-plan-benefit-guide, gold-plan-benefit-guide |
| RAG-074 | partial | INSUFFICIENT | ANSWER | 0.7347 | 0/0 | gold-plan-benefit-guide |
| RAG-075 | partial | INSUFFICIENT | ANSWER | 0.7252 | 0/0 | pa-imaging-guide |
| RAG-092 | incorrect-assumption | ANSWER | ANSWER | 0.7829 | 0/1 | gold-plan-benefit-guide, pa-physical-therapy-guide |
| RAG-106 | conflict | CONFLICT | ANSWER | 0.7597 | 0/0 | virtual-care-policy-summary |
| RAG-108 | outdated | ANSWER | ANSWER | 0.7921 | 0/1 | pa-imaging-guide |
| RAG-116 | injection | ANSWER | ANSWER | 0.7954 | 0/1 | gold-plan-benefit-guide, gold-plan-benefit-guide |
