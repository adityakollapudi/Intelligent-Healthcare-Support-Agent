import { useEffect, useState } from "react";

import { isApiError } from "../../lib/errors";
import { healthService } from "../../services";

type State = "checking" | "ok" | "degraded" | "unreachable";
const LABEL: Record<State, string> = {
  checking: "Checking service…",
  ok: "Service connected",
  degraded: "Service degraded",
  unreachable: "Service unreachable",
};
const POLL_MS = 60_000;

/** Shows the real result of GET /api/v1/health, refreshed every minute. */
export function HealthIndicator() {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    let controller = new AbortController();
    const check = async () => {
      controller.abort();
      controller = new AbortController();
      try {
        const result = await healthService.get(controller.signal);
        setState(result.status === "ok" ? "ok" : "degraded");
      } catch (error) {
        if (isApiError(error) && error.kind === "aborted") return;
        // /health answers 503 when the database is down: the API itself is reachable.
        setState(isApiError(error) && error.status === 503 ? "degraded" : "unreachable");
      }
    };
    void check();
    const timer = setInterval(() => void check(), POLL_MS);
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, []);

  return (
    <span className={`health health-${state}`} role="status" aria-live="polite">
      <span className="health-dot" aria-hidden="true" />
      {LABEL[state]}
    </span>
  );
}
