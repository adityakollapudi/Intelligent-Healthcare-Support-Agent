// Phase 7 UI: agent queue and review actions, member case actions, readiness escalation and the
// admin dashboard's honesty about failures and missing data.
import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiError, authRoutes, json, mockApi } from "../test/fetch-mock";
import { renderSignedIn } from "../test/render";

afterEach(() => vi.unstubAllGlobals());

const SUMMARY = {
  case_id: "c-1",
  case_number: "CASE-2026-000007",
  category: "CLAIM_INQUIRY",
  status: "OPEN",
  escalation_reason: "NO_ADEQUATE_ANSWER",
  summary_preview: "Member asks about a pending claim…",
  assigned_to: null,
  created_at: "2026-10-25T10:00:00Z",
  updated_at: "2026-10-25T10:00:00Z",
};
const DETAIL = {
  ...SUMMARY,
  summary: "Member asks about a pending claim (synthetic).",
  related_session_id: null,
  related_claim_number: null,
  resolution_note: null,
  version: 1,
  events: [{ event_type: "CREATED", from_status: null, to_status: "OPEN", note: null, actor_display_name: "Priya Synthetic", created_at: "2026-10-25T10:00:00Z" }],
  data_environment: "SYNTHETIC_PROTOTYPE",
  view: "summary",
  created_by: { display_name: "Priya Synthetic", role: "MEMBER" },
  assigned_to: null,
  documents: [],
  conversation_excerpt: [],
  allowed_actions: ["assign_to_me"],
};
const ASSIGNED = { ...DETAIL, status: "ASSIGNED", version: 2, view: "full", assigned_to: { id: "u-agent", display_name: "Sam Reviewer" }, allowed_actions: ["add_note", "start", "release"] };
const page = (items: unknown[], next: string | null = null) => json(200, { items, next_cursor: next });

describe("agent workspace", () => {
  it("lists the queue from the server and takes a case only after confirmation", async () => {
    let current: Record<string, unknown> = DETAIL;
    const { calls } = mockApi({
      ...authRoutes("SUPPORT_AGENT"),
      "GET /support-cases": ({ url }) => page(url.searchParams.get("scope") === "queue" ? [SUMMARY] : []),
      "GET /support-cases/c-1": () => json(200, current),
      "PATCH /support-cases/c-1": ({ body }) => {
        expect(body).toEqual({ version: 1, assign_to_me: true });
        current = ASSIGNED;
        return json(200, ASSIGNED);
      },
    });
    const { user } = await renderSignedIn();
    expect(await screen.findByRole("heading", { level: 1, name: "Case queue" })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "CASE-2026-000007" }));
    const panel = await screen.findByRole("region", { name: "Case details" });
    expect(within(panel).getByText(/Nobody has reviewed it yet/)).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Assign to me" }));
    expect(calls.some((c) => c.method === "PATCH")).toBe(false); // nothing sent before confirming
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Assign to me" }));
    expect(await screen.findByText(/the case is now assigned/)).toBeInTheDocument();
    expect(await within(panel).findByRole("button", { name: "Start work" })).toBeInTheDocument();
    const queueCall = calls.find((c) => c.path === "/support-cases" && c.method === "GET");
    expect(queueCall).toBeTruthy();
  });

  it("requires a resolution note and reports a version conflict without claiming success", async () => {
    const inProgress = { ...ASSIGNED, status: "IN_PROGRESS", version: 3, allowed_actions: ["add_note", "request_info", "resolve"] };
    mockApi({
      ...authRoutes("SUPPORT_AGENT"),
      "GET /support-cases": () => page([{ ...SUMMARY, status: "IN_PROGRESS" }]),
      "GET /support-cases/c-1": () => json(200, inProgress),
      "PATCH /support-cases/c-1": () => apiError(409, "VERSION_CONFLICT", "The case was changed by someone else."),
    });
    const { user } = await renderSignedIn();
    await user.click(await screen.findByRole("tab", { name: "Assigned to me" }));
    await user.click(await screen.findByRole("button", { name: "CASE-2026-000007" }));
    await user.click(await screen.findByRole("button", { name: "Resolve" }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Resolve" }));
    expect(within(dialog).getByText("Please fill in the required information.")).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText(/Resolution/), "Explained the pending status.");
    await user.click(within(dialog).getByRole("button", { name: "Resolve" }));
    expect(await within(dialog).findByText("This case changed")).toBeInTheDocument();
    expect(screen.queryByText("Saved")).not.toBeInTheDocument();
  });

  it("shows an empty queue honestly and sends filters to the server", async () => {
    const { fetchMock } = mockApi({ ...authRoutes("SUPPORT_AGENT"), "GET /support-cases": () => page([]) });
    const { user } = await renderSignedIn();
    expect(await screen.findByText("The queue is empty")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Category"), "DOCUMENT_ISSUE");
    await waitFor(() =>
      expect(fetchMock.mock.calls.map(([u]) => String(u)).some((u) => u.includes("scope=queue") && u.includes("category=DOCUMENT_ISSUE"))).toBe(true),
    );
  });
});

describe("member case actions", () => {
  it("lets the requester add a note, with the server deciding which actions exist", async () => {
    const mine = { ...DETAIL, view: "full", status: "AWAITING_USER", version: 4, assigned_to: { display_name: "Sam Reviewer" }, allowed_actions: ["add_note"] };
    const { calls } = mockApi({
      ...authRoutes("MEMBER"),
      "GET /support-cases": () => page([{ ...SUMMARY, status: "AWAITING_USER" }]),
      "GET /support-cases/c-1": () => json(200, mine),
      "PATCH /support-cases/c-1": () => json(200, { ...mine, status: "IN_PROGRESS", version: 5 }),
    });
    const { navigate, user } = await renderSignedIn();
    navigate("/cases?case=c-1");
    const panel = await screen.findByRole("region", { name: "Case details" });
    expect(within(panel).queryByRole("button", { name: "Resolve" })).not.toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Add note" }));
    await user.type(screen.getByLabelText("Note"), "Uploaded the bill.");
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Add note" }));
    expect(await screen.findByText(/the case is now in progress/)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PATCH")!.body).toEqual({ version: 4, note: "Uploaded the bill." });
  });
});

const METRICS = {
  data_environment: "SYNTHETIC_PROTOTYPE",
  period: { from: "2026-09-26", to: "2026-10-25", timezone: "UTC" },
  generated_at: "2026-10-25T12:00:00Z",
  chat: { user_messages: 14, assistant_messages: 14, by_intent: {}, by_evidence_status: { SUPPORTED: 9, INSUFFICIENT: 3, CONFLICTING: 1, VERIFIED_RECORD: 1, NOT_APPLICABLE: 0 }, escalations_offered: 4, latency_ms: { p50: null, p95: null, sample_size: 0 } },
  tools: { get_claim_status: { SUCCEEDED: 5, EXECUTION_ERROR: 1 } },
  cases: {
    created: 6, created_by_status: { OPEN: 2, RESOLVED: 4 }, created_by_category: { CLAIM_INQUIRY: 6 }, created_by_escalation_reason: { NO_ADEQUATE_ANSWER: 6 },
    escalated_from_chat: 3, resolved_in_period: 4, median_hours_to_resolution: null,
    created_per_day: [{ date: "2026-10-24", count: 6 }], resolved_per_day: [],
    current_by_status: { OPEN: 2, RESOLVED: 4 }, current_open_workload: 2, current_unassigned_open: 1,
  },
  documents: { jobs_by_status: { COMPLETED: 3, FAILED: 1 }, failures_by_error_code: { OCR_FAILED: 1 }, top_field_issues: [{ field_name: "ordering_provider_npi", status: "ABSENT", count: "<3" }] },
  readiness: { by_status: { DOCUMENTATION_INCOMPLETE: 2 }, by_review_state: { AWAITING_REVIEW: 1 } },
  security: { access_denied_events: 7, rejected_case_updates: 2 },
  unavailable: ["feedback"],
};

describe("admin dashboard", () => {
  it("renders backend metrics, shows missing data as a dash, and names what isn't collected", async () => {
    mockApi({ ...authRoutes("ADMIN"), "GET /admin/metrics": () => json(200, METRICS) });
    await renderSignedIn();
    expect(await screen.findByText("Open workload now")).toBeInTheDocument();
    expect(screen.getByText("Median time to resolution: —")).toBeInTheDocument(); // null, not 0
    expect(screen.getByText(/0 answers/)).toBeInTheDocument(); // latency shown as "—", from 0 samples
    expect(screen.getByText(/Not collected in this build: feedback/)).toBeInTheDocument();
    const evidence = screen.getByRole("region", { name: "Answer evidence" });
    expect(within(evidence).getByText("Insufficient")).toBeInTheDocument();
    expect(screen.getByText(/ordering provider npi Absent \(<3\)/i)).toBeInTheDocument();
  });

  it("shows an error, not zeros, when metrics fail", async () => {
    mockApi({ ...authRoutes("ADMIN"), "GET /admin/metrics": () => apiError(500, "INTERNAL_ERROR") });
    await renderSignedIn();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("Open workload now")).not.toBeInTheDocument();
  });

  it("validates the date range before calling the API", async () => {
    const { fetchMock } = mockApi({ ...authRoutes("ADMIN"), "GET /admin/metrics": () => json(200, METRICS) });
    const { user } = await renderSignedIn();
    await screen.findByText("Open workload now");
    const before = fetchMock.mock.calls.length;
    const from = screen.getByLabelText("From");
    await user.clear(from);
    await user.type(from, "2030-01-01");
    expect(screen.getByText("'From' must be on or before 'to'.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled();
    expect(fetchMock.mock.calls.length).toBe(before);
  });

  it("pages through the read-only audit log", async () => {
    const event = (id: number) => ({ id, occurred_at: "2026-10-25T12:00:00Z", request_id: null, actor: { id: "u", display_name: "Sam Reviewer", role: "SUPPORT_AGENT" }, action: "SUPPORT_CASE_STATUS_CHANGED", resource_type: "support_case", resource_ref: "CASE-2026-000007", outcome: "SUCCESS", reason_code: null, metadata: { from_status: "ASSIGNED", to_status: "IN_PROGRESS" } });
    const { fetchMock } = mockApi({
      ...authRoutes("ADMIN"),
      "GET /admin/metrics": () => json(200, METRICS),
      "GET /admin/audit-events": ({ url }) => (url.searchParams.get("cursor") ? json(200, { items: [event(1)], next_cursor: null }) : json(200, { items: [event(3), event(2)], next_cursor: "2" })),
    });
    const { user } = await renderSignedIn();
    await user.click(await screen.findByRole("tab", { name: "Audit log" }));
    const table = await screen.findByRole("table", { name: "Audit events" });
    expect(within(table).getAllByText("SUPPORT_CASE_STATUS_CHANGED")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Load older events" }));
    await waitFor(() => expect(within(screen.getByRole("table", { name: "Audit events" })).getAllByText("SUPPORT_CASE_STATUS_CHANGED")).toHaveLength(3));
    expect(fetchMock.mock.calls.map(([u]) => String(u)).some((u) => u.includes("cursor=2"))).toBe(true);
    expect(screen.queryByRole("button", { name: /delete|edit/i })).not.toBeInTheDocument();
  });

  it("is not offered to other roles", async () => {
    mockApi(authRoutes("SUPPORT_AGENT"));
    mockApi({ ...authRoutes("SUPPORT_AGENT"), "GET /support-cases": () => page([]) });
    const { navigate } = await renderSignedIn();
    navigate("/admin");
    expect(await screen.findByRole("heading", { level: 1 })).not.toHaveTextContent("Admin dashboard");
  });
});
