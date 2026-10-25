// Test-only fetch stub. Routes are matched on "METHOD path" relative to the API base URL.
import { vi } from "vitest";

export type Handler = (req: { url: URL; init: RequestInit; body: unknown }) => Response | Promise<Response>;

export const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "X-Request-ID": "req-test", ...headers },
  });

export const apiError = (status: number, code: string, message = "error") =>
  json(status, { error: { code, message, details: [], request_id: "req-test" } });

export function mockApi(routes: Record<string, Handler>) {
  const calls: { method: string; path: string; headers: Headers; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input));
    const method = init.method ?? "GET";
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const body = typeof init.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ method, path, headers: new Headers(init.headers), body });
    const handler = routes[`${method} ${path}`] ?? routes[`${method} *`];
    if (!handler) return apiError(404, "RESOURCE_NOT_FOUND");
    return handler({ url, init, body });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, calls };
}

export const ME = {
  MEMBER: {
    id: "u-member",
    display_name: "Priya Synthetic",
    email: "priya.member@example.test",
    role: "MEMBER",
    organization: null,
    member: { member_number: "SYN-M-000001", plan_code: "SYN-PLAN-GOLD-01" },
    permissions: ["benefits:read:own", "cases:create", "cases:read:own", "cases:update:own", "chat:use", "claims:read:own", "documents:read:own", "documents:upload", "feedback:create", "knowledge:read", "requirements:read"],
  },
  PROVIDER: {
    id: "u-provider",
    display_name: "Jordan Example",
    email: "jordan.provider@example.test",
    role: "PROVIDER",
    organization: { id: "o1", name: "Maplestone Family Clinic (fictional)" },
    member: null,
    permissions: ["benefits:read:any", "cases:create", "cases:read:own", "cases:update:own", "chat:use", "documents:read:own", "documents:upload", "feedback:create", "knowledge:read", "readiness:create", "readiness:read:own", "requirements:read"],
  },
  SUPPORT_AGENT: {
    id: "u-agent",
    display_name: "Sam Reviewer",
    email: "sam.agent@example.test",
    role: "SUPPORT_AGENT",
    organization: { id: "o2", name: "IHSA Synthetic Support Center" },
    member: null,
    permissions: ["benefits:read:any", "cases:assign:self", "cases:read:assigned", "cases:read:queue", "cases:update:assigned", "chat:use", "claims:read:case_linked", "documents:read:case_linked", "feedback:create", "knowledge:read", "readiness:read:case_linked", "requirements:read"],
  },
  ADMIN: {
    id: "u-admin",
    display_name: "Alex Operator",
    email: "alex.admin@example.test",
    role: "ADMIN",
    organization: null,
    member: null,
    permissions: ["audit:read", "benefits:read:any", "cases:assign:any", "cases:read:metadata_all", "chat:use", "config:manage", "feedback:create", "knowledge:read", "knowledge_gaps:read", "metrics:read", "requirements:read"],
  },
} as const;

export const authRoutes = (role: keyof typeof ME): Record<string, Handler> => ({
  "POST /auth/login": () => json(200, { access_token: `token-${role}`, token_type: "bearer", expires_in: 1800, user: { id: ME[role].id, display_name: ME[role].display_name, role } }),
  "GET /auth/me": () => json(200, ME[role]),
  "POST /auth/logout": () => new Response(null, { status: 204 }),
  "GET /health": () => json(200, { status: "ok", checks: { api: "ok", database: "ok" }, time: "2026-10-25T12:00:00Z" }),
  "GET /chat/sessions": () => json(200, { items: [], next_cursor: null }),
});

export const chatAnswer = (overrides: Record<string, unknown> = {}) => ({
  session_id: "s-1",
  message_id: `m-${Math.random().toString(36).slice(2)}`,
  intent: "GENERAL_FAQ",
  answer_type: "DOCUMENT_GROUNDED",
  evidence_status: "SUPPORTED",
  answer_text: "Physical therapy is limited to 20 visits per plan year [C1].",
  citations: [
    {
      marker: "C1",
      chunk_id: "c-1",
      document_id: "d-1",
      document_title: "Synthetic Gold Plan Benefit Guide",
      document_type: "BENEFIT_GUIDE",
      document_version: "1.0",
      effective_date: "2026-01-01",
      section_heading: "Physical therapy",
      page_start: null,
      page_end: null,
      excerpt: "Coverage is limited to 20 visits per plan year.",
    },
  ],
  tool_executions: [],
  proposed_actions: [],
  escalation: { offered: false, reason: null },
  disclaimers: ["Information comes from synthetic prototype documents and is not a coverage or authorization decision."],
  latency_ms: 50,
  created_at: "2026-10-25T12:00:00Z",
  data_environment: "SYNTHETIC_PROTOTYPE",
  ...overrides,
});

export const CLAIM_101 = {
  claim_number: "SYN-CLM-2026-000101",
  plan_code: "SYN-PLAN-GOLD-01",
  provider_name: "Maplestone Family Clinic (fictional)",
  service_date: "2026-08-14",
  submission_date: "2026-08-20",
  status: "PENDING_INFORMATION",
  status_reason_code: "PI-01",
  last_status_change_at: "2026-09-02T10:15:00Z",
};
