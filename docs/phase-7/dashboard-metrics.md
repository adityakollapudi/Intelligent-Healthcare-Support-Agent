# Phase 7 — Dashboard Metrics and Knowledge Gaps

All values come from `app/services/admin_service.py`: SQL `COUNT`/`GROUP BY`/`percentile_cont` over persisted rows. Nothing is hard-coded, estimated, cached or computed in the browser. The data is the synthetic prototype's own activity. **These are not Evernorth business outcomes.**

## 1. Period, time zone and freshness

- **Range:** `GET /admin/metrics?from=YYYY-MM-DD&to=YYYY-MM-DD`, at most 366 days, with `from ≤ to` (else 422 `INVALID_PERIOD`). The default is the last 30 days ending today in UTC.
- **Boundaries:** the window is **[from 00:00 UTC, to + 1 day 00:00 UTC)**. A case created at 2020-03-31 23:59 UTC is in March; one at 2020-04-01 00:00 UTC is not (tested). The UI shows dates in UTC and labels them as such.
- **Freshness:** computed on each request when the Overview tab loads. The UI shows "calculated … when this page loaded (not live)". It does not auto-refresh.
- **Empty data:** an empty period returns real zeros for counts. Values that need data (medians, latency percentiles) return `null`, which the UI shows as "—", never 0. A failed request shows an error panel instead of numbers.

## 2. Metric dictionary (`GET /admin/metrics`, permission `metrics:read`)

| Metric | Definition | Source | Period-bound? |
|---|---|---|---|
| `chat.user_messages` | Messages with `sender = USER` | `conversation_messages.created_at` | yes |
| `chat.assistant_messages` | Messages with `sender = ASSISTANT` | same | yes |
| `chat.by_intent` / `by_evidence_status` | Assistant messages grouped by stored intent / evidence status (`SUPPORTED`, `INSUFFICIENT`, `CONFLICTING`, `VERIFIED_RECORD`, `NOT_APPLICABLE`) | same | yes |
| `chat.escalations_offered` | Assistant messages with `escalation_offered = true` (an offer, not a created case) | same | yes |
| `chat.latency_ms.p50/p95` | Continuous percentiles of the stored pipeline latency of assistant messages; `sample_size` = rows with latency | same | yes |
| `tools.{tool}.{status}` | Count of tool executions by result status | `tool_invocations.created_at` | yes |
| `cases.created` | Cases created in the period (distinct cases) | `support_cases.created_at` | yes |
| `cases.created_by_status / _category / _escalation_reason` | Those cases grouped by their **current** status / category / reason | same | yes |
| `cases.escalated_from_chat` | Those cases with a linked conversation session | same | yes |
| `cases.resolved_in_period` | Cases whose `resolved_at` is in the period (a reopened case has `resolved_at` cleared) | `support_cases.resolved_at` | yes |
| `cases.median_hours_to_resolution` | Median of `resolved_at − created_at` (hours) over `resolved_in_period` | same | yes |
| `cases.created_per_day` / `resolved_per_day` | Daily counts by UTC date; days with 0 are omitted | same | yes |
| `cases.current_by_status` | All cases by current status | `support_cases.status` | **no** (snapshot) |
| `cases.current_open_workload` | Current OPEN + ASSIGNED + IN_PROGRESS + AWAITING_USER. "Open" means not RESOLVED/CLOSED/CANCELLED; RESOLVED counts as not open because the agent has delivered a resolution | same | **no** |
| `cases.current_unassigned_open` | Current OPEN with no assignee (the queue size) | same | **no** |
| `documents.jobs_by_status` | Analysis jobs by status | `document_processing_jobs.created_at` | yes |
| `documents.failures_by_error_code` | FAILED jobs by `error_code` | same | yes |
| `documents.top_field_issues` | Top 10 (field, non-VALID status) pairs over those jobs' fields; counts below 3 are shown as `"<3"` | `extracted_fields` ⋈ jobs | yes |
| `readiness.by_status` / `by_review_state` | Checklists created in the period by readiness status / current review state | `authorization_checklists.created_at` | yes |
| `security.access_denied_events` | `ACCESS_DENIED` audit rows | `audit_logs.occurred_at` | yes |
| `security.rejected_case_updates` | `SUPPORT_CASE_UPDATE_REJECTED` audit rows | same | yes |
| `unavailable` | Metrics in the contract that this build doesn't collect: `feedback` (no feedback endpoint or table exists) | — | — |

**Counts don't double up.** Every count is over a single table (or a 1:N join counted at the child level, as for field issues, which counts fields), so joins don't inflate it. Event counts (messages, audit rows) and distinct-entity counts (cases) are kept separate.

## 3. Knowledge gaps (`GET /admin/knowledge-gaps`, permission `knowledge_gaps:read`)

| Output | How it's derived |
|---|---|
| `items` | Assistant messages with `evidence_status` `INSUFFICIENT` or `CONFLICTING` and a `gap_topic` (an identifier-free word label the pipeline stores, with IDs stripped), grouped by (topic, status). Each row gives occurrences, **distinct users**, last seen and intents |
| Suppression | A topic seen by fewer than **2 distinct users** is hidden. `suppressed_topics` reports how many were hidden, so one person's repeated question isn't flagged as a documentation gap and single individuals can't be singled out |
| `by_intent` | The same messages counted by intent and status (no text) |
| `requirement_set_misses` | `get_required_documents` calls that returned `NOT_FOUND`, grouped by the requested procedure code (a configured set may be missing) |
| `tool_failures` | Tool `EXECUTION_ERROR`s, grouped by tool. These are system faults, reported separately from content gaps |

How false gaps are kept down:
- Only evidence classifications count. AI service outages (503) never produce an assistant message, so they are never counted.
- Medical refusals and other unsupported requests are `NOT_APPLICABLE`, so they're excluded.
- Topics need ≥2 people.
- The output is labeled as a **recommendation** for knowledge-base review. Nothing is ingested or changed automatically.
- If the documents are updated, answers become `SUPPORTED`, and the topic stops appearing in later periods.

**Privacy:**
- The report never includes message text, user identities or session IDs; topics are short word labels.
- Raw conversation text stays in `conversation_messages` under the normal access rules. Only the assigned agent sees a case's 6-message excerpt.

## 4. Verification

`tests/api/test_case_review.py` inserts synthetic records dated March 2020 (a period no other test touches) and asserts exact, hand-computed values:
- 5 cases created, with case 6 at 04-01 00:00 UTC excluded;
- status split OPEN 2, IN_PROGRESS 1, RESOLVED 1, CLOSED 1;
- 1 case escalated from chat, 2 resolved;
- a median of 7.0 h, from cases resolved in 4 h and 10 h;
- daily series 03-10: 2, 03-11: 2, 03-31: 1;
- evidence INSUFFICIENT 3 and CONFLICTING 1;
- latency p50 300 / p95 480 over 100–500 ms;
- tool and requirement-miss rows;
- the gap "acupuncture coverage" with 3 occurrences from 2 users, and "telehealth copay" suppressed because it came from 1 user.

An empty period (January 2019) returns zeros and `null` medians. The live dev database was also cross-checked by direct SQL (see testing-report.md).
