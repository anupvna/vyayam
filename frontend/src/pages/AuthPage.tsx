// One screen for both "Log in" and "Create account", switched by a toggle.
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
      setError(`Password must be at least ${MIN_PASSWORD} characters.`);
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

  function switchMode() {
    setMode(isSignup ? "login" : "signup");
    setError(null);
  }

  return (
    <main className="auth">
      <div className="brand">
        <img src="/icons/icon-192.png" alt="" width={56} height={56} />
        <h1>Vyayam</h1>
        <p className="muted">Your personal gym coach</p>
      </div>

      <form className="card" onSubmit={onSubmit} noValidate>
        <h2>{isSignup ? "Create account" : "Log in"}</h2>

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
              className="ghost"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
          {isSignup && <small className="muted">At least {MIN_PASSWORD} characters</small>}
        </label>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Please wait…" : isSignup ? "Create account" : "Log in"}
        </button>

        <button type="button" className="link" onClick={switchMode}>
          {isSignup ? "Already have an account? Log in" : "New here? Create an account"}
        </button>
      </form>

      <p className="disclaimer muted">A training aid, not medical advice.</p>
    </main>
  );
}
