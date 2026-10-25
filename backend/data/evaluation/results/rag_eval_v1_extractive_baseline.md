# RAG evaluation — rag_eval_v1 (extractive)

- Run: 2026-10-25T13:41:41+00:00 · items: 131 · embedding: `BAAI/bge-small-en-v1.5` · generator: `extractive`
- Chunking: 160 words / 30 overlap · top_k: 5 · RAG_MIN_RELEVANCE: 0.7

## Headline metrics

| Metric | Result |
|---|---|
| Expected behavior matched (all items) | 84.0% (110/131) |
| Retrieval recall@5 (expected source in top 5, answerable items) | 100.0% (82/82) |
| MRR@5 | 0.992 |
| Required facts present (answered, answerable items) | 79.5% (58/73) |
| Answers with all required facts | 78.8% (52/66) |
| Answers citing an expected source | 97.3% (71/73) |
| Answers citing a superseded version | 0 |
| Answers citing a forbidden (out-of-scope) source | 0 |
| Items where an unauthorized document was even a candidate | 0 |
| Pipeline latency p50 / p95 (local CPU, includes embedding) | 29 ms / 39 ms |

## Behavior by category

| Category | Matched |
|---|---|
| strong | 92.5% (37/40) |
| paraphrase | 60.0% (12/20) |
| multi-passage | 87.5% (7/8) |
| partial | 12.5% (1/8) |
| no-support | 100.0% (15/15) |
| incorrect-assumption | 100.0% (6/6) |
| ambiguous | 80.0% (4/5) |
| conflict | 100.0% (4/4) |
| outdated | 100.0% (4/4) |
| injection | 83.3% (5/6) |
| claim-status | 100.0% (6/6) |
| unavailable-tool | 100.0% (5/5) |
| access-boundary | 100.0% (4/4) |

## Similarity-threshold sweep (pre-generation gate)

Answerable items: 78; partial/no-support items: 23.

| Threshold | Answerable kept | Unanswerable passing the gate |
|---|---|---|
| 0.60 | 100.0% (78/78) | 78.3% (18/23) |
| 0.62 | 100.0% (78/78) | 69.6% (16/23) |
| 0.64 | 98.7% (77/78) | 52.2% (12/23) |
| 0.66 | 97.4% (76/78) | 39.1% (9/23) |
| 0.68 | 96.2% (75/78) | 34.8% (8/23) |
| 0.70 | 92.3% (72/78) | 34.8% (8/23) |
| 0.72 | 88.5% (69/78) | 30.4% (7/23) |
| 0.74 | 80.8% (63/78) | 8.7% (2/23) |
| 0.76 | 70.5% (55/78) | 8.7% (2/23) |
| 0.78 | 65.4% (51/78) | 8.7% (2/23) |
| 0.80 | 55.1% (43/78) | 8.7% (2/23) |

## Mismatches

| Test | Category | Expected | Actual | Best sim | Facts | Cited |
|---|---|---|---|---|---|---|
| RAG-001 | strong | ANSWER | CONFLICT | 0.8996 | 1/1 | gold-plan-benefit-guide, virtual-care-policy-summary |
| RAG-018 | strong | ANSWER | INSUFFICIENT | 0.714 | 0/1 |  |
| RAG-019 | strong | ANSWER | INSUFFICIENT | 0.6489 | 0/1 |  |
| RAG-027 | strong | ANSWER | ANSWER | 0.8385 | 0/1 | claim-documentation-requirements, claim-documentation-requirements, claims-status-guide |
| RAG-032 | strong | ANSWER | ANSWER | 0.8932 | 0/1 | pa-imaging-guide, provider-admin-faq |
| RAG-035 | strong | ANSWER | ANSWER | 0.8761 | 0/1 | pa-physical-therapy-guide, gold-plan-benefit-guide |
| RAG-041 | paraphrase | ANSWER | INSUFFICIENT | 0.7457 | 0/1 |  |
| RAG-044 | paraphrase | ANSWER | INSUFFICIENT | 0.6848 | 0/1 |  |
| RAG-046 | paraphrase | ANSWER | ANSWER | 0.7335 | 0/1 | claims-status-guide |
| RAG-048 | paraphrase | ANSWER | INSUFFICIENT | 0.6751 | 0/1 |  |
| RAG-049 | paraphrase | ANSWER | INSUFFICIENT | 0.7396 | 0/1 |  |
| RAG-050 | paraphrase | ANSWER | INSUFFICIENT | 0.6381 | 0/1 |  |
| RAG-051 | paraphrase | ANSWER | INSUFFICIENT | 0.6916 | 0/1 |  |
| RAG-052 | paraphrase | ANSWER | INSUFFICIENT | 0.7046 | 0/1 |  |
| RAG-053 | paraphrase | ANSWER | INSUFFICIENT | 0.6808 | 0/1 |  |
| RAG-055 | paraphrase | ANSWER | ANSWER | 0.7707 | 0/1 | pa-imaging-guide, gold-plan-benefit-guide |
| RAG-056 | paraphrase | ANSWER | ANSWER | 0.8051 | 0/1 | pa-imaging-guide |
| RAG-057 | paraphrase | ANSWER | ANSWER | 0.7907 | 0/1 | pa-physical-therapy-guide, pa-physical-therapy-guide |
| RAG-059 | paraphrase | ANSWER | ANSWER | 0.712 | 0/1 | pa-imaging-guide, pa-physical-therapy-guide |
| RAG-061 | multi-passage | ANSWER | ANSWER | 0.8844 | 1/2 | gold-plan-benefit-guide, gold-plan-benefit-guide, pa-physical-therapy-guide |
| RAG-063 | multi-passage | ANSWER | ANSWER | 0.8296 | 1/2 | claims-appeal-process |
| RAG-065 | multi-passage | ANSWER | CONFLICT | 0.8656 | 2/2 | gold-plan-benefit-guide, virtual-care-policy-summary |
| RAG-066 | multi-passage | ANSWER | ANSWER | 0.7889 | 1/2 | claims-status-guide, claims-status-guide |
| RAG-067 | multi-passage | ANSWER | ANSWER | 0.8244 | 0/2 | provider-admin-faq |
| RAG-068 | multi-passage | ANSWER | ANSWER | 0.8014 | 1/2 | virtual-care-faq |
| RAG-070 | partial | INSUFFICIENT | CONFLICT | 0.8145 | 0/0 | gold-plan-benefit-guide, virtual-care-policy-summary, virtual-care-faq |
| RAG-071 | partial | INSUFFICIENT | ANSWER | 0.7306 | 0/0 | gold-plan-benefit-guide, gold-plan-benefit-guide |
| RAG-072 | partial | INSUFFICIENT | ANSWER | 0.7031 | 0/0 | pa-physical-therapy-guide |
| RAG-073 | partial | INSUFFICIENT | ANSWER | 0.8121 | 0/0 | gold-plan-benefit-guide, gold-plan-benefit-guide |
| RAG-074 | partial | INSUFFICIENT | ANSWER | 0.7347 | 0/0 | gold-plan-benefit-guide |
| RAG-075 | partial | INSUFFICIENT | ANSWER | 0.7252 | 0/0 | pa-physical-therapy-guide, provider-admin-faq |
| RAG-076 | partial | INSUFFICIENT | UNSUPPORTED | 0.7353 | 0/0 |  |
| RAG-101 | ambiguous | CLARIFY | INSUFFICIENT | 0.5201 | 0/0 |  |
| RAG-113 | injection | INSUFFICIENT/UNSUPPORTED | ANSWER | 0.7021 | 0/0 | claims-status-guide |
| RAG-116 | injection | ANSWER | ANSWER | 0.7954 | 0/1 | gold-plan-benefit-guide, gold-plan-benefit-guide |
