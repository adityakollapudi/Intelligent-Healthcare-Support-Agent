// Phase 8: answer feedback (FR-034) and automated accessibility checks (axe-core) on the main screens.
// axe in jsdom can't evaluate colour contrast or layout, so those were checked manually in a browser.
import { screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiError, authRoutes, chatAnswer, json, mockApi } from "../test/fetch-mock";
import { renderSignedIn } from "../test/render";

afterEach(() => vi.unstubAllGlobals());

async function violations() {
  const result = await axe.run(document.body, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } });
  expect(result.passes.length).toBeGreaterThan(10); // axe really evaluated rules on this page
  return result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

describe("answer feedback", () => {
  it("records a rating only after the API confirms it", async () => {
    const answer = chatAnswer({ message_id: "m-42" });
    const { calls } = mockApi({
      ...authRoutes("MEMBER"),
      "POST /chat": () => json(200, answer),
      "POST /chat/messages/m-42/feedback": () => json(200, { message_id: "m-42", rating: "HELPFUL", updated_at: "2026-10-27T10:00:00Z" }),
    });
    const { user } = await renderSignedIn();
    await user.type(screen.getByLabelText("Your question"), "How many PT visits?");
    await user.keyboard("{Enter}");
    await user.click(await screen.findByRole("button", { name: "👍 Yes" }));
    expect(await screen.findByText("Thanks, your rating was recorded.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "👍 Yes" })).toHaveAttribute("aria-pressed", "true");
    expect(calls.find((c) => c.path === "/chat/messages/m-42/feedback")!.body).toEqual({ rating: "HELPFUL" });
  });

  it("says so when the rating wasn't saved", async () => {
    mockApi({
      ...authRoutes("MEMBER"),
      "POST /chat": () => json(200, chatAnswer({ message_id: "m-43" })),
      "POST /chat/messages/m-43/feedback": () => apiError(500, "INTERNAL_ERROR"),
    });
    const { user } = await renderSignedIn();
    await user.type(screen.getByLabelText("Your question"), "How many PT visits?");
    await user.keyboard("{Enter}");
    await user.click(await screen.findByRole("button", { name: "👎 No" }));
    expect(await screen.findByText("Your rating wasn't saved. Please try again.")).toBeInTheDocument();
    expect(screen.queryByText("Thanks, your rating was recorded.")).not.toBeInTheDocument();
  });
});

describe("accessibility (axe-core, structural rules)", () => {
  const cases = [
    ["MEMBER", "/chat", "Assistant"],
    ["MEMBER", "/claims", "My claims"],
    ["MEMBER", "/benefits", "Plan benefits"],
    ["MEMBER", "/cases", "Support cases"],
    ["PROVIDER", "/documents", "Documents"],
    ["PROVIDER", "/readiness", "Prior authorization readiness"],
    ["SUPPORT_AGENT", "/agent", "Case queue"],
    ["ADMIN", "/admin", "Admin dashboard"],
  ] as const;

  it.each(cases)("%s %s has no detectable violations", async (role, path, heading) => {
    mockApi({
      ...authRoutes(role),
      "GET *": () => json(200, { items: [], next_cursor: null }),
      "GET /authorization/requirement-sets": () => json(200, []),
      "GET /admin/metrics": () => apiError(503, "SERVICE_UNAVAILABLE"),
    });
    const { navigate } = await renderSignedIn();
    navigate(path);
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/^Loading/)).not.toBeInTheDocument());
    expect(await violations()).toEqual([]);
  });

  it("the sign-in screen has no detectable violations", async () => {
    mockApi(authRoutes("MEMBER"));
    const { renderApp } = await import("../test/render");
    renderApp("/login");
    await screen.findByRole("heading", { name: "Sign in" });
    expect(await violations()).toEqual([]);
  });
});
