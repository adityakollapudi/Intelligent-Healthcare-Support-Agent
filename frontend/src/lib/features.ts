// Which backend capabilities exist. Flip a flag only when the backend endpoint is implemented.
export interface FeatureInfo {
  available: boolean;
  phase: number;
  endpoints: string[];
  description: string;
}

export const features = {
  claims: { available: true, phase: 2, endpoints: ["GET /claims", "GET /claims/{claim_number}"], description: "Claim lookup" },
  benefits: { available: true, phase: 2, endpoints: ["GET /benefits/{plan_code}"], description: "Plan benefits" },
  chat: { available: false, phase: 4, endpoints: ["POST /chat"], description: "AI assistant answers with citations" },
  documents: {
    available: false,
    phase: 6,
    endpoints: ["POST /documents", "POST /documents/{id}/analyze"],
    description: "Document upload and analysis",
  },
  readiness: {
    available: false,
    phase: 6,
    endpoints: ["POST /authorization/readiness"],
    description: "Prior authorization readiness checklists",
  },
  supportCases: {
    available: false,
    phase: 5,
    endpoints: ["POST /support-cases", "GET /support-cases"],
    description: "Support case creation and tracking",
  },
  agentWorkspace: {
    available: false,
    phase: 7,
    endpoints: ["GET /support-cases?scope=queue", "PATCH /support-cases/{id}"],
    description: "Assigned-case review",
  },
  adminDashboard: {
    available: false,
    phase: 7,
    endpoints: ["GET /admin/metrics", "GET /admin/audit-events"],
    description: "Aggregate metrics and audit events",
  },
} satisfies Record<string, FeatureInfo>;

export type FeatureKey = keyof typeof features;
