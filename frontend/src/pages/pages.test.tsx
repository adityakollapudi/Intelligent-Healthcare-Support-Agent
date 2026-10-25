import { screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatProvider, useChat } from "../features/chat/chat-state";
import { apiError, authRoutes, chatAnswer, CLAIM_101, json, mockApi } from "../test/fetch-mock";
import { renderSignedIn } from "../test/render";

afterEach(() => vi.unstubAllGlobals());

const CLAIM_PAGE = {
  items: [CLAIM_101, { ...CLAIM_101, claim_number: "SYN-CLM-2026-000104", status: "PROCESSED_PAID" }],
  next_cursor: null,
  data_environment: "SYNTHETIC_PROTOTYPE",
};
const CLAIM_DETAIL = { ...CLAIM_101, member_number: "SYN-M-000001", status_description: "Additional itemized bill requested (synthetic).", data_environment: "SYNTHETIC_PROTOTYPE" };
const GOLD = {
  plan_code: "SYN-PLAN-GOLD-01",
  plan_name: "Synthetic Gold Plan",
  plan_year: 2026,
  effective_start: "2026-01-01",
  effective_end: "2026-12-31",
  benefits: [
    { benefit_category: "IMAGING", service_name: "MRI (outpatient)", in_network_cost_share: "20% coinsurance", out_of_network_cost_share: null, prior_auth_required: true, visit_limit: null, limitations: null, source: null },
    { benefit_category: "PRIMARY_CARE", service_name: "Office visit", in_network_cost_share: "$20 copay", out_of_network_cost_share: "40% coinsurance", prior_auth_required: false, visit_limit: null, limitations: null, source: null },
  ],
  data_environment: "SYNTHETIC_PROTOTYPE",
};

describe("claims screen", () => {
  it("lists claims from the API and shows a looked-up claim", async () => {
    const { calls } = mockApi({
      ...authRoutes("MEMBER"),
      "GET /claims": () => json(200, CLAIM_PAGE),
      "GET /claims/SYN-CLM-2026-000101": () => json(200, CLAIM_DETAIL),
    });
    const { user, navigate } = await renderSignedIn();
    navigate("/claims");
    const table = await screen.findByRole("table");
    expect(within(table).getByText("SYN-CLM-2026-000104")).toBeInTheDocument();
    expect(within(table).getByText("Processed – paid")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Claim number"), "syn-clm-2026-000101");
    await user.click(screen.getByRole("button", { name: "Look up" }));
    const card = await screen.findByRole("article");
    expect(within(card).getByText("Additional itemized bill requested (synthetic).")).toBeInTheDocument();
    expect(within(card).getByText("Pending information")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/claims/SYN-CLM-2026-000101")).toBe(true); // normalized to upper case
  });

  it("validates the claim number without calling the API", async () => {
    const { calls } = mockApi({ ...authRoutes("MEMBER"), "GET /claims": () => json(200, CLAIM_PAGE) });
    const { user, navigate } = await renderSignedIn();
    navigate("/claims");
    await user.type(await screen.findByLabelText("Claim number"), "CLM-1");
    await user.click(screen.getByRole("button", { name: "Look up" }));
    expect(screen.getByText("Use the format SYN-CLM-2026-000101.")).toBeInTheDocument();
    expect(calls.some((c) => c.path.startsWith("/claims/"))).toBe(false);
  });

  it("explains a not-found claim without revealing whether it exists elsewhere", async () => {
    mockApi({ ...authRoutes("MEMBER"), "GET /claims": () => json(200, CLAIM_PAGE), "GET /claims/SYN-CLM-2026-000201": () => apiError(404, "RESOURCE_NOT_FOUND") });
    const { user, navigate } = await renderSignedIn();
    navigate("/claims");
    await user.type(await screen.findByLabelText("Claim number"), "SYN-CLM-2026-000201");
    await user.click(screen.getByRole("button", { name: "Look up" }));
    expect(await screen.findByText("No claim found")).toBeInTheDocument();
  });

  it("shows a retryable error when the service is down", async () => {
    let fail = true;
    mockApi({ ...authRoutes("MEMBER"), "GET /claims": () => (fail ? apiError(503, "SERVICE_UNAVAILABLE") : json(200, CLAIM_PAGE)) });
    const { user, navigate } = await renderSignedIn();
    navigate("/claims");
    expect(await screen.findByText("Service temporarily unavailable")).toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("table")).toBeInTheDocument();
  });

  it("filters by status through the API", async () => {
    const { fetchMock } = mockApi({
      ...authRoutes("MEMBER"),
      "GET /claims": ({ url }) =>
        json(200, url.searchParams.get("status") === "PROCESSED_PAID" ? { ...CLAIM_PAGE, items: [CLAIM_PAGE.items[1]] } : CLAIM_PAGE),
    });
    const { user, navigate } = await renderSignedIn();
    navigate("/claims");
    await screen.findByText("SYN-CLM-2026-000101");
    await user.selectOptions(screen.getByLabelText("Status"), "PROCESSED_PAID");
    expect(await screen.findByText("SYN-CLM-2026-000104")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("SYN-CLM-2026-000101")).not.toBeInTheDocument());
    expect(String(fetchMock.mock.calls.at(-1)![0])).toContain("status=PROCESSED_PAID");
  });
});

describe("benefits screen", () => {
  it("loads the member's own plan automatically and groups benefits", async () => {
    const { calls } = mockApi({ ...authRoutes("MEMBER"), "GET /benefits/SYN-PLAN-GOLD-01": () => json(200, GOLD) });
    const { navigate } = await renderSignedIn();
    navigate("/benefits");
    expect(await screen.findByRole("heading", { name: "Synthetic Gold Plan" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Imaging" })).toBeInTheDocument();
    expect(screen.getByText("Listed as required")).toBeInTheDocument();
    expect(screen.queryByLabelText("Plan code")).not.toBeInTheDocument(); // members can't search other plans
    expect(calls.some((c) => c.path === "/benefits/SYN-PLAN-GOLD-01")).toBe(true);
  });

  it("filters by category via the backend query parameter", async () => {
    const { fetchMock } = mockApi({
      ...authRoutes("MEMBER"),
      "GET /benefits/SYN-PLAN-GOLD-01": ({ url }) =>
        json(200, url.searchParams.get("benefit_category") === "IMAGING" ? { ...GOLD, benefits: [GOLD.benefits[0]] } : GOLD),
    });
    const { user, navigate } = await renderSignedIn();
    navigate("/benefits");
    await screen.findByRole("heading", { name: "Synthetic Gold Plan" });
    await user.selectOptions(screen.getByLabelText("Benefit category"), "IMAGING");
    await screen.findByText("MRI (outpatient)");
    expect(screen.queryByText("Office visit")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("benefit_category=IMAGING"))).toBe(true);
  });

  it("lets staff search plans and reports not-found plans", async () => {
    mockApi({ ...authRoutes("PROVIDER"), "GET /benefits/SYN-PLAN-NOPE-01": () => apiError(404, "RESOURCE_NOT_FOUND") });
    const { user, navigate } = await renderSignedIn();
    navigate("/benefits");
    await user.type(await screen.findByLabelText("Plan code"), "SYN-PLAN-NOPE-01");
    await user.click(screen.getByRole("button", { name: "Look up plan" }));
    expect(await screen.findByText("Plan not found")).toBeInTheDocument();
  });
});

describe("chat screen (Phase 4 API)", () => {
  it("sends the question to POST /chat and renders the answer with its sources", async () => {
    const { calls } = mockApi({ ...authRoutes("MEMBER"), "POST /chat": () => json(200, chatAnswer()) });
    const { user } = await renderSignedIn();
    await user.type(screen.getByLabelText("Your question"), "How many PT visits?");
    await user.keyboard("{Enter}");
    expect(await screen.findByText(/limited to 20 visits per plan year \[C1\]/)).toBeInTheDocument();
    expect(screen.getByText("Synthetic Gold Plan Benefit Guide")).toBeInTheDocument();
    expect(screen.getByText("Supported by sources")).toBeInTheDocument();
    const sent = calls.find((c) => c.path === "/chat")!;
    expect(sent.body).toMatchObject({ message: "How many PT visits?", session_id: null });
    expect(screen.getByLabelText("Your question")).toHaveValue("");
  });

  it("continues the same session and starts a fresh one after New conversation", async () => {
    const { calls } = mockApi({ ...authRoutes("MEMBER"), "POST /chat": () => json(200, chatAnswer()) });
    const { user } = await renderSignedIn();
    await user.type(screen.getByLabelText("Your question"), "first question");
    await user.keyboard("{Enter}");
    await screen.findByText(/20 visits per plan year \[C1\]/);
    await user.type(screen.getByLabelText("Your question"), "second question");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(calls.filter((c) => c.path === "/chat")).toHaveLength(2));
    expect(calls.filter((c) => c.path === "/chat")[1]!.body).toMatchObject({ session_id: "s-1" });
    await user.click(screen.getByRole("button", { name: "New conversation" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Start new" }));
    await user.type(screen.getByLabelText("Your question"), "third question");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(calls.filter((c) => c.path === "/chat")).toHaveLength(3));
    expect(calls.filter((c) => c.path === "/chat")[2]!.body).toMatchObject({ session_id: null });
  });

  it("shows insufficient evidence as a limitation (not an error) with an honestly disabled action", async () => {
    mockApi({
      ...authRoutes("MEMBER"),
      "POST /chat": () =>
        json(200, chatAnswer({
          answer_type: "INSUFFICIENT_EVIDENCE",
          evidence_status: "INSUFFICIENT",
          answer_text: "I couldn't find information about this in the documents available to me.",
          citations: [],
          escalation: { offered: true, reason: "NO_ADEQUATE_ANSWER" },
          proposed_actions: [{ action_type: "CREATE_SUPPORT_CASE", label: "Ask a support agent", requires_confirmation: true, available: false, prefill: {} }],
        })),
    });
    const { user } = await renderSignedIn();
    await user.type(screen.getByLabelText("Your question"), "Is acupuncture covered?");
    await user.keyboard("{Enter}");
    expect(await screen.findByText(/couldn't find information/)).toBeInTheDocument();
    expect(screen.getByText("Couldn't verify")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask a support agent" })).toBeDisabled();
    expect(screen.getByText("Not available yet in this prototype")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument(); // not presented as a failure
    expect(screen.queryByText(/Sources \(/)).not.toBeInTheDocument(); // no invented citations
  });

  it("links claim questions to the My claims screen", async () => {
    mockApi({
      ...authRoutes("MEMBER"),
      "GET /claims": () => json(200, CLAIM_PAGE),
      "POST /chat": () =>
        json(200, chatAnswer({
          answer_type: "UNSUPPORTED_REQUEST",
          evidence_status: "NOT_APPLICABLE",
          answer_text: "I can't look up individual claims in this chat yet.",
          citations: [],
          proposed_actions: [{ action_type: "VIEW_CLAIM", label: "Open My claims", requires_confirmation: false, available: true, prefill: {} }],
        })),
    });
    const { user } = await renderSignedIn();
    await user.type(screen.getByLabelText("Your question"), "status of my claim?");
    await user.keyboard("{Enter}");
    await user.click(await screen.findByRole("link", { name: "Open My claims" }));
    expect(await screen.findByRole("heading", { level: 1, name: "My claims" })).toBeInTheDocument();
  });

  it("on a service error restores the question and retries with the same client_message_id", async () => {
    let fail = true;
    const { calls } = mockApi({
      ...authRoutes("MEMBER"),
      "POST /chat": () => (fail ? apiError(503, "AI_SERVICE_UNAVAILABLE") : json(200, chatAnswer())),
    });
    const { user } = await renderSignedIn();
    await user.type(screen.getByLabelText("Your question"), "hello there");
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Service temporarily unavailable")).toBeInTheDocument();
    expect(screen.getByLabelText("Your question")).toHaveValue("hello there");
    expect(screen.queryByText("Assistant", { selector: ".message-sender" })).not.toBeInTheDocument();
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText(/20 visits per plan year \[C1\]/);
    const ids = calls.filter((c) => c.path === "/chat").map((c) => (c.body as { client_message_id: string }).client_message_id);
    expect(ids).toHaveLength(2);
    expect(ids[0]).toBe(ids[1]);
  });

  it("rejects malformed chat responses instead of showing them", async () => {
    mockApi({ ...authRoutes("MEMBER"), "POST /chat": () => json(200, { answer_text: "no ids or citations" }) });
    const { user } = await renderSignedIn();
    await user.type(screen.getByLabelText("Your question"), "hello there");
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Unexpected response")).toBeInTheDocument();
    expect(screen.queryByText("no ids or citations")).not.toBeInTheDocument();
  });

  it("lists recent conversations and reopens one from the server", async () => {
    mockApi({
      ...authRoutes("MEMBER"),
      "GET /chat/sessions": () =>
        json(200, { items: [{ session_id: "s-9", title: "Appeal deadline", last_message_at: "2026-10-25T12:00:00Z", created_at: "2026-10-25T11:00:00Z" }], next_cursor: null }),
      "GET /chat/sessions/s-9": () =>
        json(200, {
          session_id: "s-9",
          title: "Appeal deadline",
          messages: [
            { message_id: "u1", sender: "USER", content: "How long to appeal?", intent: "GENERAL_FAQ", answer_type: null, evidence_status: null, citations: [], proposed_actions: [], disclaimers: [], created_at: "2026-10-25T11:00:00Z" },
            { message_id: "a1", sender: "ASSISTANT", content: "Within 180 calendar days [C1].", intent: "GENERAL_FAQ", answer_type: "DOCUMENT_GROUNDED", evidence_status: "SUPPORTED", citations: chatAnswer().citations, proposed_actions: [], disclaimers: [], created_at: "2026-10-25T11:00:01Z" },
          ],
        }),
    });
    const { user } = await renderSignedIn();
    await user.click(await screen.findByRole("button", { name: /Appeal deadline/ }));
    expect(await screen.findByText("Within 180 calendar days [C1].")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Appeal deadline/ })).toHaveAttribute("aria-current", "true");
  });

  it("validates empty input", async () => {
    mockApi(authRoutes("MEMBER"));
    const { user } = await renderSignedIn();
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.getByText("Type a question first.")).toBeInTheDocument();
  });

  it("keeps the conversation draft when navigating away and back", async () => {
    mockApi({ ...authRoutes("MEMBER"), "GET /claims": () => json(200, CLAIM_PAGE) });
    const { user, navigate } = await renderSignedIn();
    await user.type(screen.getByLabelText("Your question"), "draft text");
    navigate("/claims");
    navigate("/chat");
    expect(await screen.findByLabelText("Your question")).toHaveValue("draft text");
  });

  it("requires confirmation before clearing a conversation", async () => {
    mockApi(authRoutes("MEMBER"));
    const { user } = await renderSignedIn();
    await user.type(screen.getByLabelText("Your question"), "draft text");
    await user.click(screen.getByRole("button", { name: "New conversation" }));
    const dialog = screen.getByRole("dialog", { name: "Start a new conversation?" });
    await user.keyboard("{Escape}");
    expect(dialog).not.toBeInTheDocument();
    expect(screen.getByLabelText("Your question")).toHaveValue("draft text");
    await user.click(screen.getByRole("button", { name: "New conversation" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Start new" }));
    expect(screen.getByLabelText("Your question")).toHaveValue("");
  });
});

describe("chat rendering safety and unavailable mode", () => {
  it("never sends while the feature flag is off, and keeps the draft", async () => {
    const { ChatPage } = await import("./ChatPage");
    const { SessionProvider } = await import("../features/auth/session");
    const { render } = await import("@testing-library/react");
    const userEvent = (await import("@testing-library/user-event")).default;
    const { calls } = mockApi(authRoutes("MEMBER"));
    render(
      <MemoryRouter>
        <SessionProvider>
          <ChatProvider available={false}>
            <ChatPage />
          </ChatProvider>
        </SessionProvider>
      </MemoryRouter>,
    );
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Your question"), "What does my plan cover?");
    await user.keyboard("{Enter}");
    expect(screen.getByText("Not sent")).toBeInTheDocument();
    expect(screen.getByLabelText("Your question")).toHaveValue("What does my plan cover?");
    expect(calls.some((c) => c.path === "/chat")).toBe(false);
  });

  // Renders ChatProvider directly against a stubbed /chat.
  async function setup(chatHandler: Parameters<typeof mockApi>[0][string]) {
    const { ChatPage } = await import("./ChatPage");
    const { SessionProvider } = await import("../features/auth/session");
    const { render } = await import("@testing-library/react");
    const userEvent = (await import("@testing-library/user-event")).default;
    mockApi({ ...authRoutes("MEMBER"), "POST /chat": chatHandler });
    render(
      <MemoryRouter>
        <SessionProvider>
          <ChatProvider available>
            <ChatPage />
          </ChatProvider>
        </SessionProvider>
      </MemoryRouter>,
    );
    return userEvent.setup();
  }

  it("renders answers as text with backend citations only", async () => {
    const user = await setup(() =>
      json(200, {
        session_id: "s1",
        message_id: "m1",
        intent: "GENERAL_FAQ",
        answer_type: "DOCUMENT_GROUNDED",
        evidence_status: "SUPPORTED",
        answer_text: "<img src=x onerror=alert(1)> Office visits cost $20 [C1].",
        citations: [{ marker: "C1", chunk_id: "c", document_id: "d", document_title: "Synthetic Gold Plan Benefit Guide", document_type: "BENEFIT_GUIDE", document_version: "1.0", effective_date: null, section_heading: "Primary care", page_start: 3, page_end: 3, excerpt: "Office visits: $20 copay." }],
        tool_executions: [],
        proposed_actions: [],
        escalation: { offered: false, reason: null },
        disclaimers: [],
        latency_ms: 10,
        created_at: "2026-10-25T12:00:00Z",
        data_environment: "SYNTHETIC_PROTOTYPE",
      }),
    );
    await user.type(screen.getByLabelText("Your question"), "cost?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText(/Office visits cost \$20/)).toBeInTheDocument();
    expect(document.querySelector(".messages img")).toBeNull(); // HTML is shown as text, never executed
    expect(screen.getByText("Synthetic Gold Plan Benefit Guide")).toBeInTheDocument();
    expect(screen.getByText("Effective date not stated")).toBeInTheDocument();
    expect(screen.getByText("Supported by sources")).toBeInTheDocument();
  });

  it("restores the question and offers retry when the request fails", async () => {
    const user = await setup(() => apiError(503, "AI_SERVICE_UNAVAILABLE"));
    await user.type(screen.getByLabelText("Your question"), "hello there");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Service temporarily unavailable")).toBeInTheDocument();
    expect(screen.getByLabelText("Your question")).toHaveValue("hello there");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("exposes the chat hook only inside its provider", () => {
    expect(() => useChat()).toThrow();
  });
});

describe("readiness screen basics", () => {
  it("explains readiness is not an approval and uses the four Phase 1 statuses", async () => {
    mockApi(authRoutes("PROVIDER"));
    const { navigate } = await renderSignedIn();
    navigate("/readiness");
    expect(await screen.findByText(/not an authorization approval, denial/)).toBeInTheDocument();
    for (const label of ["Satisfied", "Missing", "Unreadable", "Needs manual review"]) expect(screen.getAllByText(label).length).toBeGreaterThan(0);
  });
});