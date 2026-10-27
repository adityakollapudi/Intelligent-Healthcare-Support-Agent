# Phase 8 — Final Demonstration Guide

A reproducible walkthrough of the real application. Every step uses the live API and database; nothing is staged. All data is synthetic, and IHSA is not an Evernorth product.

## 0. Setup (about 10 minutes the first time)

1. Follow the deployment guide, path A: start PostgreSQL, run migrations, seed, ingest, then start the API and frontend.
2. Generate the sample documents with `cd backend; .\.venv\Scripts\python -m scripts.build_sample_documents`. They are written to `backend/data/samples/documents/`.
3. Open **http://localhost:5173**. The password for all accounts is `SEED_USER_PASSWORD` from `backend/.env`.

| Account | Role |
|---|---|
| `priya.member@example.test` | Member (claims SYN-CLM-2026-000101…105, plan SYN-PLAN-GOLD-01) |
| `jordan.provider@example.test` | Provider (Maplestone Family Clinic, fictional) |
| `sam.agent@example.test` | Support agent |
| `alex.admin@example.test` | Administrator |

**Contingency:** the demo runs in `LLM_PROVIDER=extractive` mode, so no model service is needed. Answers quote the cited passages and say so. If a reviewer asks about Claude, explain that it is integrated but **unverified live** (no approved key). The control flow is covered by scripted-client tests (`backend/tests/api/test_chat_tools.py`).

## 1. Member: questions, claims, benefits (about 5 minutes)

| # | Action | Expected result |
|---|---|---|
| 1 | Sign in as Priya → Assistant. Ask: *How many outpatient physical therapy visits are covered per plan year?* | Answer with markers like [C1], a **Supported by sources** badge, and a Sources list (Synthetic Gold Plan Benefit Guide, section, effective date, excerpt) |
| 2 | Click **👍 Yes** under the answer | "Thanks, your rating was recorded." (FR-034) |
| 3 | Ask: *Does my plan cover acupuncture?* | "I couldn't find information…", a **Couldn't verify** badge, no sources, and an **Ask a support agent** button |
| 4 | Ask: *What is the status of my claim SYN-CLM-2026-000101?* | Claim record card: **Pending information**, the status explanation cited from the Claims Status Guide, and a **Claim lookup** badge |
| 5 | My claims → look up `SYN-CLM-2026-000201` | Not found. It belongs to another member, and the app doesn't reveal that it exists |
| 6 | Plan benefits | Gold plan benefits come from the database (cost share, limits, prior-authorization flags) |
| 7 | Back to Assistant → **Ask a support agent** (from step 3) → review → **Create case** | "Support case CASE-2026-0000NN created". The number is returned by the backend, and the status says "Nobody has reviewed it yet". Note the number |

## 2. Provider: requirements, documents, readiness (about 7 minutes)

| # | Action | Expected result |
|---|---|---|
| 8 | Sign out → Jordan → Assistant: *What documents are required for a lumbar MRI prior authorization?* | Requirement list REQ-MRI-01…06, each with its source passage, and the "not an authorization approval" disclaimer |
| 9 | Documents → upload `pa_request_mri_incomplete.pdf` → **Upload** | "…stored. It hasn't been analyzed yet." |
| 10 | **Analyze document** | Polls, then "Analyzed with warnings": NPI and therapy duration **Not found**, other fields Valid with page 1 · Text |
| 11 | Upload and analyze `referral_letter_mri.pdf` and `pa_request_mri_mixed.pdf` | Referral: Analyzed. Mixed: page 2 "Could not be read · OCR unavailable", NPI **Not readable** (illegible, not missing) |
| 12 | PA readiness → set *Lumbar spine MRI* → tick the incomplete form + the referral → **Create checklist** | Documentation incomplete: 3 Satisfied, 2 **Missing**, 1 **Needs manual review**, each with evidence (file p.1) and its requirement source |
| 13 | New checklist with the **mixed** PDF + the referral | REQ-MRI-02 **Unreadable** (the unread page), showing all four statuses across steps 12–13 |
| 14 | Point at the banner "Not an authorization decision" and the reviewer summary | Readiness = documentation completeness only, never approval or denial |
| 15 | **Send to a support agent for review** → Create case | Linked case created; the checklist shows *Awaiting review* |

## 3. Support agent: human review (about 4 minutes)

| # | Action | Expected result |
|---|---|---|
| 16 | Sign out → Sam → Case queue | The cases from steps 7 and 15 are in **Unassigned queue** (summary view) |
| 17 | Open the step-15 case → **Assign to me** → confirm | Assigned to Sam. Full view: linked documents (expand to see fields) and the linked checklist |
| 18 | **Start work** → **Resolve** (enter a resolution note) | Status Resolved. History lists every step by actor and time |

## 4. Administrator: dashboard and audit (about 4 minutes)

| # | Action | Expected result |
|---|---|---|
| 19 | Sign out → Alex → Admin dashboard (Overview) | Counts from the database: cases created, open workload, answers by evidence, document jobs, feedback (HELPFUL ≥ 1), access-denied events. Dates are in UTC and marked "not live" |
| 20 | **Audit log** → Resource = the step-15 case number | SUPPORT_CASE_CREATED → ASSIGNED → STATUS_CHANGED (…→IN_PROGRESS) → STATUS_CHANGED (…→RESOLVED), with actors, and no note text |
| 21 | **Knowledge gaps** | Topics without a supported answer (topics from a single person are hidden) |

## 5. Access denied (about 1 minute)

| # | Action | Expected result |
|---|---|---|
| 22 | As Sam, try `http://localhost:8000/api/v1/admin/audit-events` with the token, or just note that the Admin menu is absent | API: 403 `FORBIDDEN` (recorded as `ACCESS_DENIED`). The UI doesn't offer the screen, and the backend refuses it anyway |
| 23 | As Priya, open Support cases and try the step-15 case ID in the URL `/cases?case=<id>` | "Not found". Not her case |

## Expected-value cheatsheet

| Item | Value |
|---|---|
| Claim SYN-CLM-2026-000101 | PENDING_INFORMATION, service 2026-08-14 |
| Gold plan PT | $25 copay, 20 visits/year |
| MRI checklist (incomplete + referral) | REQ-MRI-01 S, 02 M, 03 M, 04 S, 05 S, 06 NMR → DOCUMENTATION_INCOMPLETE |
| Mixed PDF without OCR | REQ-MRI-02 UNREADABLE |

Screenshots are not included. None were produced as artifacts in this phase.
