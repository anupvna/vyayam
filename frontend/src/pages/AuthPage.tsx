// One screen for both "Log in" and "Create account", switched by a link.
import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../api";
import { useAuth } from "../auth";
import { MIN_PASSWORD, confirmHint, newPasswordProblem } from "../authForm";

export function AuthPage() {
  const { login, signup, demo } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [tried, setTried] = useState(false); // after a submit, show the mismatch even mid-typing
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isSignup = mode === "signup";
  const hint = tried && password !== confirm ? "The passwords don't match." : confirmHint(password, confirm);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const problem = isSignup ? newPasswordProblem(password, confirm) : null;
    if (problem) {
      setTried(true);
      // A mismatch is already shown under the confirm field; don't say it twice.
      setError(password.length < MIN_PASSWORD ? problem : null);
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

  async function tryDemo() {
    setError(null);
    setBusy(true);
    try {
      await demo();
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

        {isSignup && (
          <label>
            Confirm password
            <input
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              aria-describedby="confirm-hint"
              required
            />
            {hint && (
              <span id="confirm-hint" className={`hint ${password === confirm ? "ok" : "bad"}`} aria-live="polite">
                {hint}
              </span>
            )}
          </label>
        )}

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
            setConfirm("");
            setTried(false);
            setError(null);
          }}
        >
          {isSignup ? "I already have an account" : "Create an account"}
        </button>
      </form>

      <section className="demo-box">
        <p>
          <b>Just looking?</b> Explore a sample account with four weeks of training. No sign-up, and it's shared,
          so don't enter anything personal.
        </p>
        <button type="button" className="secondary" disabled={busy} onClick={tryDemo}>
          Try the demo
        </button>
      </section>

      <p className="footnote">A training aid, not medical advice.</p>
    </main>
  );
}
