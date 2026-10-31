import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useReveal, useWordReveal } from "./useWordReveal";

describe("useReveal", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("adds words gradually, keeping line breaks, and ends on the exact text", () => {
    const text = "First line here\nSecond line";
    const { result } = renderHook(() => useReveal(text, true, undefined, 10));
    expect(result.current).toEqual({ shown: "", done: false });
    act(() => void vi.advanceTimersByTime(30));
    expect(result.current.shown.length).toBeGreaterThan(0);
    expect(text.startsWith(result.current.shown)).toBe(true);
    expect(result.current.done).toBe(false);
    for (let i = 0; i < 20; i += 1) act(() => void vi.advanceTimersByTime(10));
    expect(result.current).toEqual({ shown: text, done: true });
  });

  it("shows inactive text at once", () => {
    const { result } = renderHook(() => useReveal("Reopened history", false));
    expect(result.current).toEqual({ shown: "Reopened history", done: true });
  });

  it("finishes very long answers within the time cap", () => {
    const text = Array.from({ length: 2000 }, (_, i) => `word${i}`).join(" ");
    const { result } = renderHook(() => useReveal(text, true));
    for (let i = 0; i < 200 && !result.current.done; i += 1) act(() => void vi.advanceTimersByTime(35));
    expect(result.current.done).toBe(true);
  });
});

describe("useWordReveal", () => {
  it("is off in tests so rendered text is immediate", () => {
    const { result } = renderHook(() => useWordReveal("Hello", true));
    expect(result.current).toEqual({ shown: "Hello", done: true });
  });
});
