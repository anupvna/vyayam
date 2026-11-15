// One screen for both "Log in" and "Create account", switched by a link.
import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../api";
import { useAuth } from "../auth";

const MIN_PASSWORD = 10;

export function AuthPage() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isSignup = mode === "signup";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (isSignup && password.length < MIN_PASSWORD) {
      setError(`Use at least ${MIN_PASSWORD} characters for your password.`);
      return;
    }
    setBusy(true);
    try {
      await (isSignup ? signup : login)(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Can't reach the server. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <header className="brand">
        <span className="script" lang="kn">
          ವ್ಯಾಯಾಮ
        </span>
        <h1>Vyayam</h1>
        <p className="muted">A coach that plans each training day around you.</p>
      </header>

      <form className="panel" onSubmit={onSubmit} noValidate>
        <h2>{isSignup ? "Create your account" : "Welcome back"}</h2>

        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            inputMode="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <label>
          Password
          <div className="password-row">
            <input
              type={showPassword ? "text" : "password"}
              autoComplete={isSignup ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button
              type="button"
              className="secondary"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
          {isSignup && <span className="hint">At least {MIN_PASSWORD} characters.</span>}
        </label>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="primary" disabled={busy}>
          {busy ? "One moment…" : isSignup ? "Create account" : "Log in"}
        </button>

        <button
          type="button"
          className="link"
          onClick={() => {
            setMode(isSignup ? "login" : "signup");
            setError(null);
          }}
        >
          {isSignup ? "I already have an account" : "Create an account"}
        </button>
      </form>

      <p className="footnote">A training aid, not medical advice.</p>
    </main>
  );
}
