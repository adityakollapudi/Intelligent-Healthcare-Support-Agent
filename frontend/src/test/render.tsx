import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useNavigate, type NavigateFunction } from "react-router-dom";

import { App } from "../app/App";

/** Exposes the router's navigate() so tests can follow in-app links without a page reload. */
function NavigateProbe({ onReady }: { onReady: (navigate: NavigateFunction) => void }) {
  onReady(useNavigate());
  return null;
}

/** Renders the full app at `path` (signed out). */
export function renderApp(path = "/") {
  const user = userEvent.setup();
  let navigateFn: NavigateFunction = () => undefined;
  const utils = render(
    <MemoryRouter initialEntries={[path]}>
      <NavigateProbe onReady={(n) => (navigateFn = n)} />
      <App />
    </MemoryRouter>,
  );
  const navigate = (to: string | number) =>
    act(() => void (typeof to === "number" ? navigateFn(to) : navigateFn(to)));
  return { user, navigate, ...utils };
}

/** Renders the app and signs in through the real login form (fetch must be mocked). */
export async function renderSignedIn(path = "/login") {
  const ctx = renderApp(path);
  await ctx.user.type(screen.getByLabelText("Email"), "someone@example.test");
  await ctx.user.type(screen.getByLabelText("Password"), "a-test-password");
  await ctx.user.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByRole("navigation", { name: "Primary" });
  return ctx;
}
