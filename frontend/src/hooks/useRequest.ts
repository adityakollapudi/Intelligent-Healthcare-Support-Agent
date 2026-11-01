import { useCallback, useEffect, useRef, useState } from "react";

import { isApiError } from "../lib/errors";

export type RequestState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: unknown };

/**
 * Runs an async request on demand. A newer call aborts the previous one, and results from
 * stale or unmounted calls are ignored.
 */
export function useRequest<T, A extends unknown[]>(fn: (signal: AbortSignal, ...args: A) => Promise<T>) {
  const [state, setState] = useState<RequestState<T>>({ status: "idle" });
  const controller = useRef<AbortController | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => () => controller.current?.abort(), []);

  const start = useCallback(async (showLoading: boolean, args: A) => {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    if (showLoading) setState({ status: "loading" });
    try {
      const data = await fnRef.current(current.signal, ...args);
      if (!current.signal.aborted) setState({ status: "success", data });
      return data;
    } catch (error) {
      if (current.signal.aborted || (isApiError(error) && error.kind === "aborted")) return undefined;
      setState({ status: "error", error });
      return undefined;
    }
  }, []);

  const run = useCallback((...args: A) => start(true, args), [start]);
  // Fetches again while the current result stays on screen, for polling and background updates.
  const refresh = useCallback((...args: A) => start(false, args), [start]);

  const reset = useCallback(() => {
    controller.current?.abort();
    setState({ status: "idle" });
  }, []);

  return { state, run, refresh, reset };
}
