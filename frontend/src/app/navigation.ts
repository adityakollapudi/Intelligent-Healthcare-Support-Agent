// Role-aware navigation (doc 08 §3), driven by the permission list from GET /auth/me.
// This controls what is shown, not what is allowed: the backend enforces every request.
import type { Role } from "../types/api";

export interface NavItem {
  path: string;
  label: string;
  /** User needs at least one of these permissions to see the item. */
  anyOf: string[];
  /** Roles excluded from seeing this item even if they have a matching permission. */
  excludeRoles?: Role[];
}

export const NAV_ITEMS: NavItem[] = [
  { path: "/provider", label: "Workspace", anyOf: ["readiness:create"] },
  { path: "/chat", label: "Assistant", anyOf: ["chat:use"], excludeRoles: ["ADMIN"] },
  { path: "/claims", label: "My claims", anyOf: ["claims:read:own"] },
  { path: "/benefits", label: "Plan benefits", anyOf: ["benefits:read:own", "benefits:read:any"] },
  { path: "/plan-documents", label: "Plan documents", anyOf: ["knowledge:read"] },
  { path: "/documents", label: "Documents", anyOf: ["documents:upload"] },
  { path: "/readiness", label: "PA readiness", anyOf: ["readiness:create"] },
  { path: "/cases", label: "Support cases", anyOf: ["cases:read:own"] },
  { path: "/agent", label: "Case queue", anyOf: ["cases:read:queue"] },
  { path: "/admin", label: "Admin dashboard", anyOf: ["metrics:read"] },
  { path: "/users", label: "Users", anyOf: ["users:manage"] },
];

export const HOME_BY_ROLE: Record<Role, string> = {
  MEMBER: "/chat",
  PROVIDER: "/provider",
  SUPPORT_AGENT: "/agent",
  ADMIN: "/admin",
};

export function visibleNav(permissions: readonly string[], role?: Role): NavItem[] {
  return NAV_ITEMS.filter(
    (item) => item.anyOf.some((p) => permissions.includes(p)) && (!role || !item.excludeRoles?.includes(role))
  );
}
