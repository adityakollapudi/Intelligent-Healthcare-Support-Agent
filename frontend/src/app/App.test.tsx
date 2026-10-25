import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiError, authRoutes, json, mockApi } from "../test/fetch-mock";
import { renderApp, renderSignedIn } from "../test/render";

afterEach(() => vi.unstubAllGlobals());

const nav = () => within(screen.getByRole("navigation", { name: "Primary" }));
const navLabels = () => nav().getAllByRole("link").map((a) => a.textContent);
const EMPTY_CLAIMS = { items: [], next_cursor: null, data_environment: "SYNTHETIC_PROTOTYPE" };

describe("authentication", () => {
  it("redirects signed-out visitors to the login page", () => {
    mockApi(authRoutes("MEMBER"));
    renderApp("/claims");
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("validates the login form before calling the API", async () => {
    const { calls } = mockApi(authRoutes("MEMBER"));
    const { user } = renderApp("/login");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(calls).toHaveLength(0);
  });

  it("shows a safe error for wrong credentials and stays signed out", async () => {
    mockApi({ ...authRoutes("MEMBER"), "POST /auth/login": () => apiError(401, "INVALID_CREDENTIALS") });
    const { user } = renderApp("/login");
    await user.type(screen.getByLabelText("Email"), "a@example.test");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Email or password is incorrect.")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(screen.queryByRole("navigation", { name: "Primary" })).not.toBeInTheDocument();
  });

  it("explains rate limiting", async () => {
    mockApi({ ...authRoutes("MEMBER"), "POST /auth/login": () => json(429, { error: { code: "RATE_LIMITED", message: "x" } }, { "Retry-After": "300" }) });
    const { user } = renderApp("/login");
    await user.type(screen.getByLabelText("Email"), "a@example.test");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText(/wait about 5 minute/)).toBeInTheDocument();
  });

  it("toggles password visibility", async () => {
    mockApi(authRoutes("MEMBER"));
    const { user } = renderApp("/login");
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute("aria-pressed", "true");
  });

  it("expired session: sends the user to login with a notice, then back to the same page", async () => {
    const { fetchMock } = mockApi({ ...authRoutes("MEMBER"), "GET /claims": () => json(200, EMPTY_CLAIMS) });
    const { user, navigate } = await renderSignedIn();
    const working = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async () => apiError(401, "UNAUTHENTICATED"));
    navigate("/claims");
    expect(await screen.findByText("Your session ended")).toBeInTheDocument();

    fetchMock.mockImplementation(working);
    await user.type(screen.getByLabelText("Email"), "someone@example.test");
    await user.type(screen.getByLabelText("Password"), "a-test-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { level: 1, name: "My claims" })).toBeInTheDocument();
  });

  it("signs out, revokes the token and does not carry the old page to the next user", async () => {
    const { calls } = mockApi(authRoutes("MEMBER"));
    const { user, navigate } = await renderSignedIn();
    navigate("/benefits");
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST" && c.path === "/auth/logout")).toBe(true);

    await user.type(screen.getByLabelText("Email"), "someone@example.test");
    await user.type(screen.getByLabelText("Password"), "a-test-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Assistant" })).toBeInTheDocument();
  });
});

describe("role-aware navigation", () => {
  it.each([
    ["MEMBER", ["Assistant", "My claims", "Plan benefits", "Documents", "Support cases"], "Assistant"],
    ["PROVIDER", ["Workspace", "Assistant", "Plan benefits", "Documents", "PA readiness", "Support cases"], "Provider workspace"],
    ["SUPPORT_AGENT", ["Assistant", "Plan benefits", "Case queue"], "Case queue"],
    ["ADMIN", ["Assistant", "Plan benefits", "Admin dashboard"], "Admin dashboard"],
  ] as const)("%s sees only its screens and lands on its home page", async (role, expected, home) => {
    mockApi(authRoutes(role));
    await renderSignedIn();
    expect(navLabels()).toEqual(expected);
    expect(await screen.findByRole("heading", { level: 1, name: home })).toBeInTheDocument();
  });

  it("every visible link leads to a rendered screen (no not-found, no access denied)", async () => {
    mockApi({ ...authRoutes("PROVIDER"), "GET /claims": () => json(200, EMPTY_CLAIMS) });
    const { user } = await renderSignedIn();
    for (const label of navLabels()) {
      await user.click(nav().getByRole("link", { name: label! }));
      expect(nav().getByRole("link", { name: label! })).toHaveAttribute("aria-current", "page");
      expect(screen.queryByText("We couldn't find that page")).not.toBeInTheDocument();
      expect(screen.queryByText("You don't have access to this page")).not.toBeInTheDocument();
    }
  });

  it("shows access denied when a member opens an admin route", async () => {
    mockApi(authRoutes("MEMBER"));
    const { navigate } = await renderSignedIn();
    navigate("/admin");
    expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument();
  });

  it("renders the not-found page for unknown routes", async () => {
    mockApi(authRoutes("MEMBER"));
    const { navigate } = await renderSignedIn();
    navigate("/no-such-page");
    expect(await screen.findByText("We couldn't find that page")).toBeInTheDocument();
  });

  it("supports browser back navigation", async () => {
    mockApi({ ...authRoutes("MEMBER"), "GET /claims": () => json(200, EMPTY_CLAIMS) });
    const { user, navigate } = await renderSignedIn();
    await user.click(nav().getByRole("link", { name: "My claims" }));
    await user.click(nav().getByRole("link", { name: "Plan benefits" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Plan benefits" })).toBeInTheDocument();
    navigate(-1);
    expect(await screen.findByRole("heading", { level: 1, name: "My claims" })).toBeInTheDocument();
    navigate(1);
    expect(await screen.findByRole("heading", { level: 1, name: "Plan benefits" })).toBeInTheDocument();
  });

  it("opens and closes the mobile navigation", async () => {
    mockApi(authRoutes("MEMBER"));
    const { user } = await renderSignedIn();
    const toggle = screen.getByRole("button", { name: "Open navigation" });
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(toggle).toHaveAttribute("aria-expanded", "false"));
  });

  it("shows the real health status", async () => {
    mockApi({ ...authRoutes("MEMBER"), "GET /health": () => json(503, { status: "degraded", checks: { api: "ok", database: "unavailable" }, time: "x" }) });
    await renderSignedIn();
    expect(await screen.findByText("Service degraded")).toBeInTheDocument();
  });
});
