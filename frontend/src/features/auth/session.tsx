// Session state. The access token lives only in memory (doc 11 D-09): a page reload signs the
// user out. Identity and role always come from GET /auth/me, never from client input.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { configureSession } from "../../lib/api-client";
import { authService } from "../../services";
import type { MeResponse } from "../../types/api";

type Status = "signed_out" | "signed_in" | "expired";

interface SessionValue {
  status: Status;
  user: MeResponse | null;
  can: (permission: string) => boolean;
  signIn: (email: string, password: string) => Promise<MeResponse>;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const tokenRef = useRef<string | null>(null);
  const [user, setUser] = useState<MeResponse | null>(null);
  const [status, setStatus] = useState<Status>("signed_out");

  const expire = useCallback(() => {
    tokenRef.current = null;
    setUser(null);
    setStatus("expired");
  }, []);

  useEffect(() => {
    configureSession({ getToken: () => tokenRef.current, onUnauthorized: expire });
  }, [expire]);

  const signIn = useCallback(async (email: string, password: string) => {
    const login = await authService.login(email, password);
    tokenRef.current = login.access_token;
    try {
      const me = await authService.me();
      setUser(me);
      setStatus("signed_in");
      return me;
    } catch (error) {
      tokenRef.current = null;
      throw error;
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      if (tokenRef.current) await authService.logout();
    } catch {
      // The token is discarded locally regardless; the server-side revocation is best effort.
    } finally {
      tokenRef.current = null;
      setUser(null);
      setStatus("signed_out");
    }
  }, []);

  const value = useMemo<SessionValue>(
    () => ({ status, user, can: (p) => Boolean(user?.permissions.includes(p)), signIn, signOut }),
    [status, user, signIn, signOut],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
