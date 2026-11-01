// Session state. The access token is kept in sessionStorage so a page refresh stays signed in (D-09,
// revised). It's erased when the tab closes and expires on the server after 30 minutes. Identity and
// role always come from GET /auth/me, never from client input, so nothing else is stored.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { LoadingState } from "../../components/ui";
import { configureSession } from "../../lib/api-client";
import { authService } from "../../services";
import type { MeResponse } from "../../types/api";

type Status = "restoring" | "signed_out" | "signed_in" | "expired";

interface SessionValue {
  status: Status;
  user: MeResponse | null;
  can: (permission: string) => boolean;
  signIn: (email: string, password: string) => Promise<MeResponse>;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);
const TOKEN_KEY = "ihsa.session";

// Storage can be blocked; the app then behaves as if the page has to be signed in to again.
function readToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function saveToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Signed-in state still works for this page view.
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const tokenRef = useRef<string | null>(readToken());
  const [user, setUser] = useState<MeResponse | null>(null);
  const [status, setStatus] = useState<Status>(tokenRef.current ? "restoring" : "signed_out");

  const expire = useCallback(() => {
    tokenRef.current = null;
    saveToken(null);
    setUser(null);
    setStatus("expired");
  }, []);

  useEffect(() => {
    configureSession({ getToken: () => tokenRef.current, onUnauthorized: expire });
  }, [expire]);

  // After a refresh, ask the backend who this token belongs to. A rejected token goes through `expire`.
  useEffect(() => {
    if (!tokenRef.current) return;
    authService
      .me()
      .then((me) => {
        setUser(me);
        setStatus("signed_in");
      })
      .catch(() => {
        if (!tokenRef.current) return;
        tokenRef.current = null; // service unreachable: the stored token can be retried on the next refresh
        setStatus("signed_out");
      });
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const login = await authService.login(email, password);
    tokenRef.current = login.access_token;
    try {
      const me = await authService.me();
      saveToken(login.access_token);
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
      saveToken(null);
      setUser(null);
      setStatus("signed_out");
    }
  }, []);

  const value = useMemo<SessionValue>(
    () => ({ status, user, can: (p) => Boolean(user?.permissions.includes(p)), signIn, signOut }),
    [status, user, signIn, signOut],
  );
  return (
    <SessionContext.Provider value={value}>{status === "restoring" ? <LoadingState /> : children}</SessionContext.Provider>
  );
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
