// Who is logged in, shared with the whole app through React context.
// On startup we ask the server (/auth/me). The cookie is HttpOnly, so the app itself
// can't see it and has to ask.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { ApiError, api, setCsrfToken } from "./api";

export type User = { id: string; email: string };
type SessionResponse = { user: User; csrf_token: string };

type AuthState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; user: User };

type AuthContextValue = {
  state: AuthState;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  const startSession = useCallback((s: SessionResponse) => {
    setCsrfToken(s.csrf_token);
    setState({ status: "authenticated", user: s.user });
  }, []);

  useEffect(() => {
    api<SessionResponse>("/auth/me")
      .then(startSession)
      .catch((err) => {
        if (!(err instanceof ApiError && err.status === 401)) console.error(err);
        setState({ status: "anonymous" });
      });
  }, [startSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      state,
      login: async (email, password) =>
        startSession(
          await api<SessionResponse>("/auth/login", {
            method: "POST",
            body: { email, password },
          }),
        ),
      signup: async (email, password) =>
        startSession(
          await api<SessionResponse>("/auth/signup", {
            method: "POST",
            body: { email, password },
          }),
        ),
      logout: async () => {
        await api<void>("/auth/logout", { method: "POST" });
        setCsrfToken(null);
        setState({ status: "anonymous" });
      },
    }),
    [state, startSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
