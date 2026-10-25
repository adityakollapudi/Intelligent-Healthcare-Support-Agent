// Phase 5 UI: tool records in chat, user-confirmed support-case creation, and the Cases screen.
import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { isChatResponse } from "../lib/validators";
import { apiError, authRoutes, chatAnswer, CLAIM_101, json, mockApi } from "../test/fetch-mock";
import { renderSignedIn } from "../test/render";

afterEach(() => vi.unstubAllGlobals());

const KEY = "6f1c1d2e-3a4b-4c5d-8e9f-0a1b2c3d4e5f";

const CASE_ACTION = {
  action_type: "CREATE_SUPPORT_CASE",
  label: "Create support case",
  requires_confirmation: true,
  available: true,
  prefill: { category: "CLAIM_INQUIRY", summary: "Member asks about claim SYN-CLM-2026-000101.", escalation_reason: "USER_REQUESTED_HUMAN", related_session_id: "s-1", idempotency_key: KEY },
};

const PROPOSAL_ANSWER = chatAnswer({
  intent: "SUPPORT_CASE_CREATE",
  answer_type: "TOOL_RESULT",
  evidence_status: "NOT_APPLICABLE",
  answer_text: 'I\'ve prepared a support case for a support agent. It has not been created yet: review the details and choose "Create support case" to submit it.',
  citations: [],
  tool_executions: [{ tool_name: "create_support_case", result_status: "CONFIRMATION_REQUIRED", summary: "Support case prepared; waiting for your confirmation" }],
  records: [],
  proposed_actions: [CASE_ACTION],
});

const CASE = {
  case_id: "c-1",
  case_number: "CASE-2026-000042",
  category: "CLAIM_INQUIRY",
  status: "OPEN",
  escalation_reason: "USER_REQUESTED_HUMAN",
  summary: "Member asks about claim SYN-CLM-2026-000101.",
  related_session_id: "s-1",
  related_claim_number: null,
  resolution_note: null,
  version: 1,
  events: [{ event_type: "CREATED", from_status: null, to_status: "OPEN", note: null, actor_display_name: "Priya Synthetic", created_at: "2026-10-25T12:00:00Z" }],
  created_at: "2026-10-25T12:00:00Z",
  updated_at: "2026-10-25T12:00:00Z",
  data_environment: "SYNTHETIC_PROTOTYPE",
};
const SUMMARY = { case_id: "c-1", case_number: "CASE-2026-000042", category: "CLAIM_INQUIRY", status: "OPEN", escalation_reason: "USER_REQUESTED_HUMAN", summary_preview: "Member asks about claim…", created_at: CASE.created_at, updated_at: CASE.updated_at };

async function ask(text: string) {
  const ctx = await renderSignedIn();
  ctx.navigate("/chat"); // providers and admins land on a different home screen
  await ctx.user.type(screen.getByLabelText("Your question"), text);
  await ctx.user.keyboard("{Enter}");
  return ctx;
}

describe("tool results in chat", () => {
  it("renders claim records returned by the tool, not from the answer text", async () => {
    mockApi({
      ...authRoutes("MEMBER"),
      "POST /chat": () =>
        json(200, chatAnswer({
          answer_type: "TOOL_RESULT",
          evidence_status: "VERIFIED_RECORD",
          answer_text: "Here is what your claim record shows.",
          citations: [],
          tool_executions: [{ tool_name: "get_claim_status", result_status: "SUCCEEDED", summary: "1 claim record(s) retrieved" }],
          records: [{ kind: "claims", data: { claims: [CLAIM_101] } }],
        })),
    });
    await ask("status of SYN-CLM-2026-000101");
    const table = await screen.findByRole("region", { name: "Claim records" });
    expect(within(table).getByText("SYN-CLM-2026-000101")).toBeInTheDocument();
    expect(within(table).getByText("Pending information")).toBeInTheDocument();
    expect(screen.getByText("Claim lookup")).toBeInTheDocument();
    expect(screen.getByText("From your record")).toBeInTheDocument();
  });

  it("renders requirement lists with their source and disclaimer", async () => {
    mockApi({
      ...authRoutes("PROVIDER"),
      "POST /chat": () =>
        json(200, chatAnswer({
          answer_type: "TOOL_RESULT",
          records: [{
            kind: "requirements",
            data: {
              procedure_code: "SYN-PROC-MRI-LUMBAR", display_name: "Lumbar spine MRI", version: "2.0",
              source_document_title: "Synthetic Imaging Prior Authorization Guide", source_document_version: "2.0",
              evidence_status: "PARTIALLY_SUPPORTED",
              requirements: [
                { requirement_code: "REQ-MRI-01", description: "Signed order", is_mandatory: true, rule_type: "FIELD_PRESENT", source: { document_id: "d", document_title: "Guide", document_version: "2.0", effective_date: null, section_heading: null, page_start: null, chunk_id: "c", excerpt: "x" } },
                { requirement_code: "REQ-MRI-02", description: "Conservative therapy notes", is_mandatory: true, rule_type: "MANUAL", source: null },
              ],
              disclaimer: "Documentation requirements only. Meeting them is not an authorization approval.",
            },
          }],
        })),
    });
    await ask("What documents does a lumbar MRI request need?");
    const region = await screen.findByRole("region", { name: "Documentation requirements" });
    expect(within(region).getByText("REQ-MRI-01")).toBeInTheDocument();
    expect(within(region).getByText("Source passage not verified")).toBeInTheDocument();
    expect(within(region).getByText(/not an authorization approval/)).toBeInTheDocument();
  });

  it("rejects responses whose records are malformed", () => {
    expect(isChatResponse(chatAnswer({ records: [{ kind: "claims", data: { claims: [{ claim_number: 1 }] } }] }))).toBe(false);
    expect(isChatResponse(chatAnswer({ records: [{ kind: "sql_result", data: {} }] }))).toBe(false);
    expect(isChatResponse(chatAnswer({ records: [] }))).toBe(true);
  });
});

describe("support case confirmation from chat", () => {
  it("creates the case only after confirmation, with the server-issued idempotency key", async () => {
    const { calls } = mockApi({
      ...authRoutes("MEMBER"),
      "POST /chat": () => json(200, PROPOSAL_ANSWER),
      "POST /support-cases": () => json(201, CASE),
    });
    const { user } = await ask("I want to talk to a human");
    await user.click(await screen.findByRole("button", { name: "Create support case" }));
    const dialog = screen.getByRole("dialog", { name: "Create a support case?" });
    expect(within(dialog).getByText("Nothing has been created yet.", { exact: false })).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/support-cases")).toBe(false); // nothing sent before confirming

    await user.click(within(dialog).getByRole("button", { name: "Create case" }));
    expect(await screen.findByText("Support case CASE-2026-000042 created")).toBeInTheDocument();
    const post = calls.filter((c) => c.method === "POST" && c.path === "/support-cases");
    expect(post).toHaveLength(1);
    expect(post[0]!.headers.get("Idempotency-Key")).toBe(KEY);
    expect(post[0]!.body).toEqual({ category: "CLAIM_INQUIRY", summary: "Member asks about claim SYN-CLM-2026-000101.", escalation_reason: "USER_REQUESTED_HUMAN", related_session_id: "s-1" });
  });

  it("cancelling sends nothing", async () => {
    const { calls } = mockApi({ ...authRoutes("MEMBER"), "POST /chat": () => json(200, PROPOSAL_ANSWER) });
    const { user } = await ask("open a support case");
    await user.click(await screen.findByRole("button", { name: "Create support case" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(calls.some((c) => c.path === "/support-cases")).toBe(false);
  });

  it("on failure shows no case number and retries with the same key", async () => {
    let attempt = 0;
    const { calls } = mockApi({
      ...authRoutes("MEMBER"),
      "POST /chat": () => json(200, PROPOSAL_ANSWER),
      "POST /support-cases": () => (++attempt === 1 ? apiError(500, "CASE_CREATION_FAILED") : json(200, CASE)),
    });
    const { user } = await ask("open a support case");
    await user.click(await screen.findByRole("button", { name: "Create support case" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Create case" }));
    expect(await within(screen.getByRole("dialog")).findByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.queryByText(/CASE-2026/)).not.toBeInTheDocument();

    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Support case CASE-2026-000042 created")).toBeInTheDocument();
    const keys = calls.filter((c) => c.path === "/support-cases").map((c) => c.headers.get("Idempotency-Key"));
    expect(keys).toEqual([KEY, KEY]);
  });

  it("keeps unavailable actions disabled", async () => {
    mockApi({
      ...authRoutes("ADMIN"),
      "POST /chat": () => json(200, chatAnswer({ proposed_actions: [{ ...CASE_ACTION, available: false }] })),
    });
    await ask("talk to a person");
    expect(await screen.findByRole("button", { name: "Create support case" })).toBeDisabled();
  });
});

describe("cases screen", () => {
  it("lists the user's cases and opens one", async () => {
    const { calls } = mockApi({
      ...authRoutes("MEMBER"),
      "GET /support-cases": () => json(200, { items: [SUMMARY], next_cursor: null }),
      "GET /support-cases/c-1": () => json(200, CASE),
    });
    const { navigate, user } = await renderSignedIn();
    navigate("/cases");
    await user.click(await screen.findByRole("button", { name: "CASE-2026-000042" }));
    const detail = await screen.findByRole("region", { name: "Case details" });
    expect(within(detail).getByText("Member asks about claim SYN-CLM-2026-000101.")).toBeInTheDocument();
    expect(within(detail).getByText(/Created \(Open\) by Priya Synthetic/)).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/support-cases/c-1")).toBe(true);
  });

  it("filters by status through the API", async () => {
    const { fetchMock } = mockApi({ ...authRoutes("PROVIDER"), "GET /support-cases": () => json(200, { items: [], next_cursor: null }) });
    const { navigate, user } = await renderSignedIn();
    navigate("/cases");
    await screen.findByText("No cases to show");
    await user.selectOptions(screen.getByLabelText("Status"), "RESOLVED");
    await waitFor(() =>
      expect(fetchMock.mock.calls.map(([u]) => String(u)).some((u) => u.includes("/support-cases?status=RESOLVED"))).toBe(true),
    );
    expect(await screen.findByText("No cases have this status.")).toBeInTheDocument();
  });

  it("creates a case from the form after validation and confirmation", async () => {
    const { calls } = mockApi({
      ...authRoutes("MEMBER"),
      "GET /support-cases": () => json(200, { items: [], next_cursor: null }),
      "POST /support-cases": () => json(201, { ...CASE, category: "BENEFITS_QUESTION" }),
      "GET /support-cases/c-1": () => json(200, CASE),
    });
    const { navigate, user } = await renderSignedIn();
    navigate("/cases");
    await user.click(await screen.findByRole("button", { name: "New case" }));
    await user.type(screen.getByLabelText("What do you need help with?"), "short");
    await user.click(screen.getByRole("button", { name: "Review and create" }));
    expect(screen.getByText(/at least 10 characters/)).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("What do you need help with?"), " question about my imaging benefit");
    await user.selectOptions(screen.getByLabelText("Category"), "BENEFITS_QUESTION");
    await user.click(screen.getByRole("button", { name: "Review and create" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Create case" }));
    expect(await screen.findByText("Support case CASE-2026-000042 created")).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST" && c.path === "/support-cases")!;
    expect(post.body).toEqual({ category: "BENEFITS_QUESTION", summary: "short question about my imaging benefit" });
    expect(post.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("support agents don't see the member case screen", async () => {
    mockApi(authRoutes("SUPPORT_AGENT"));
    const { navigate } = await renderSignedIn();
    navigate("/cases");
    expect(await screen.findByRole("heading", { level: 1 })).not.toHaveTextContent("Support cases");
  });
});
