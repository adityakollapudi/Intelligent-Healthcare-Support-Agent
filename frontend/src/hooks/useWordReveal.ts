// Shows a finished answer a few words at a time. The whole answer has already arrived from the server;
// this only paces how it appears. Tests and reduced-motion users get the full text at once.
import { useEffect, useMemo, useState } from "react";

const TICK_MS = 35;
const MAX_MS = 6000; // long answers speed up rather than keep the reader waiting

function reduceMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function useWordReveal(text: string, enabled: boolean, onStep?: () => void, tickMs = TICK_MS) {
  const active = enabled && import.meta.env.MODE !== "test" && !reduceMotion();
  return useReveal(text, active, onStep, tickMs);
}

export function useReveal(text: string, active: boolean, onStep?: () => void, tickMs = TICK_MS) {
  const tokens = useMemo(() => text.split(/(\s+)/), [text]);
  const perTick = Math.max(1, Math.ceil((tokens.length * tickMs) / MAX_MS));
  const [count, setCount] = useState(active ? 0 : tokens.length);

  useEffect(() => {
    if (count >= tokens.length) return;
    const timer = setTimeout(() => setCount((c) => Math.min(c + perTick, tokens.length)), tickMs);
    return () => clearTimeout(timer);
  }, [count, perTick, tickMs, tokens.length]);

  useEffect(() => onStep?.(), [count, onStep]);

  const done = count >= tokens.length;
  return { shown: done ? text : tokens.slice(0, count).join(""), done };
}
