import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useSession } from "../features/auth/session";
import { AccessDeniedPage } from "../pages/StatusPages";

/** Sends signed-out users to /login, remembering where they were going. */
export function RequireSession({ children }: { children: ReactNode }) {
  const { status } = useSession();
  const location = useLocation();
  if (status !== "signed_in") {
    // Only an expired session returns to where it was; after a sign-out the next person starts fresh.
    return status === "expired" ? (
      <Navigate to="/login?expired=1" replace state={{ from: location.pathname }} />
    ) : (
      <Navigate to="/login" replace />
    );
  }
  return <>{children}</>;
}

/** UX guard only: hides screens the role can't use. The backend still authorizes every call. */
export function RequirePermission({ anyOf, children }: { anyOf: string[]; children: ReactNode }) {
  const { can } = useSession();
  return anyOf.some(can) ? <>{children}</> : <AccessDeniedPage />;
}
