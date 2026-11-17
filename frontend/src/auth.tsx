// Who is logged in, shared with the whole app through React context.
// On startup we ask the server (/auth/me). The cookie is HttpOnly, so the app itself
// can't see it and has to ask. With no connection, the app opens as the last signed-in
// user (their saved screens and outbox) and checks with the server once it's back.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { ApiError, api, setCsrfToken, setSessionUser } from "./api";
import { SIGNED_OUT_EVENT, syncEvents, updateStatus } from "./offline/status";
import { startSync } from "./offline/sync";
import { clearUser } from "./offline/store";

export type User = { id: string; email: string };
type SessionResponse = { user: User; csrf_token: string };

type AuthState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; user: User };

type AuthContextValue = {
  state: AuthState;
  login: (email: string, password: string) => Promise<void>;
  demo: () => Promise<void>; // the shared demo account, one tap
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

// Only the id and email (no token), so the app knows whose saved data to open offline.
const LAST_USER = "vyayam:last-user";

function rememberUser(user: User | null): void {
  try {
    if (user) localStorage.setItem(LAST_USER, JSON.stringify(user));
    else localStorage.removeItem(LAST_USER);
  } catch {
    // storage unavailable: offline start just won't remember who you are
  }
}

function lastUser(): User | null {
  try {
    const raw = localStorage.getItem(LAST_USER);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}


export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  const startSession = useCallback((s: SessionResponse) => {
    setCsrfToken(s.csrf_token);
    setSessionUser(s.user.id);
    rememberUser(s.user);
    setState({ status: "authenticated", user: s.user });
  }, []);

  const endSession = useCallback(() => {
    setCsrfToken(null);
    setSessionUser(null);
    rememberUser(null);
    updateStatus({ pending: 0, failed: [] });
    setState({ status: "anonymous" });
  }, []);

  useEffect(() => {
    api<SessionResponse>("/auth/me")
      .then(startSession)
      .catch((err) => {
        const offline = err instanceof ApiError && err.status === 0;
        const last = offline ? lastUser() : null;
        if (last) {
          // No connection: open as the last user. The sync loop re-checks the session.
          setSessionUser(last.id);
          setState({ status: "authenticated", user: last });
          return;
        }
        if (!(err instanceof ApiError && (err.status === 401 || offline))) console.error(err);
        endSession();
      });
  }, [startSession, endSession]);

  // Send waiting changes while signed in; drop to the sign-in screen if the session ended.
  const signedIn = state.status === "authenticated";
  useEffect(() => {
    if (!signedIn) return;
    const stop = startSync();
    syncEvents.addEventListener(SIGNED_OUT_EVENT, endSession);
    return () => {
      stop();
      syncEvents.removeEventListener(SIGNED_OUT_EVENT, endSession);
    };
  }, [signedIn, endSession]);

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
      demo: async () => startSession(await api<SessionResponse>("/auth/demo", { method: "POST" })),
      signup: async (email, password) =>
        startSession(
          await api<SessionResponse>("/auth/signup", {
            method: "POST",
            body: { email, password },
          }),
        ),
      logout: async () => {
        await api<void>("/auth/logout", { method: "POST" });
        if (state.status === "authenticated") await clearUser(state.user.id).catch(() => undefined);
        endSession();
      },
    }),
    [state, startSession, endSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
