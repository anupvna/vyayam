// Profile: your setup in one place, with the goal check, an edit button and log out.
import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router";

import { ApiError, api } from "../api";
import { unsyncedChanges, useAuth } from "../auth";
import { AdviceList } from "../components/AdviceList";
import { TabBar } from "../components/TabBar";
import { DAY_NAMES, EXPERIENCE, goalName } from "../labels";
import type { Profile } from "../types";
import { cmToFtIn, kgToLb, round1 } from "../units";

export function ProfilePage() {
  const { state, logout } = useAuth();
  const [profile, setProfile] = useState<Profile | null | "missing">(null);
  const [error, setError] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  async function onLogout() {
    const n = unsyncedChanges();
    if (n > 0 && !window.confirm(`${n} ${n === 1 ? "change hasn't" : "changes haven't"} synced yet. Logging out deletes ${n === 1 ? "it" : "them"} from this phone. Log out anyway?`))
      return;
    setLogoutError(null);
    try {
      await logout();
    } catch (err) {
      setLogoutError(err instanceof ApiError ? err.message : "Couldn't log out. Try again.");
    }
  }

  useEffect(() => {
    api<Profile>("/profile")
      .then(setProfile)
      .catch((err) => (err instanceof ApiError && err.status === 404 ? setProfile("missing") : setError(true)));
  }, []);

  if (profile === "missing") return <Navigate to="/onboarding" replace />;
  if (error) return <div className="splash">Couldn't load. Check your connection and refresh.</div>;
  if (!profile) return <div className="splash">Loading…</div>;

  const p = profile;
  const metric = p.unit_system === "metric";
  const weight = (kg: number) => (metric ? `${round1(kg)} kg` : `${round1(kgToLb(kg))} lb`);
  const { ft, inches } = cmToFtIn(p.height_cm);
  const email = state.status === "authenticated" ? state.user.email : "";

  return (
    <>
      <main className="page">
        <header className="page-head">
          <div>
            <p className="greeting">{email}</p>
            <h1>Profile</h1>
          </div>
        </header>

        <section className="card">
          <div className="card-head">
            <h2>Your setup</h2>
            <Link to="/onboarding" className="link small">
              Edit
            </Link>
          </div>
          <dl className="summary">
            <dt>Goal</dt>
            <dd>{goalName(p.goal)}</dd>
            <dt>Target</dt>
            <dd>
              {[
                p.target_weight_kg !== null ? weight(p.target_weight_kg) : null,
                p.target_body_fat_pct !== null ? `${p.target_body_fat_pct}% body fat` : null,
              ]
                .filter(Boolean)
                .join(", ") || "Not set"}
            </dd>
            <dt>Body</dt>
            <dd>
              {metric ? `${p.height_cm} cm` : `${ft} ft ${inches} in`}, {weight(p.weight_kg)}, BMI {p.bmi}
            </dd>
            <dt>Experience</dt>
            <dd>{EXPERIENCE.find((x) => x.id === p.experience)?.name}</dd>
            <dt>Training days</dt>
            <dd>
              {p.training_days.map((d) => DAY_NAMES[d]).join(", ")}, {p.session_minutes} min
            </dd>
            <dt>Injuries</dt>
            <dd>{p.injury_areas.length ? p.injury_areas.map((a) => a.charAt(0).toUpperCase() + a.slice(1).replace("_", " ")).join(", ") : "None"}</dd>
          </dl>
        </section>

        {p.advice.length > 0 && (
          <section className="card">
            <h2>Goal check</h2>
            <AdviceList advice={p.advice} />
          </section>
        )}

        <section className="card">
          <div className="card-head">
            <h2>Your gyms</h2>
            <Link to="/gyms" className="link small">
              Manage
            </Link>
          </div>
          <p className="muted small">Switch gyms or edit equipment. Your plan only uses what's there.</p>
        </section>

        <button className="secondary" onClick={() => void onLogout()}>
          Log out
        </button>
        {logoutError && (
          <p className="error" role="alert">
            {logoutError}
          </p>
        )}
        <p className="footnote">A training aid, not medical advice.</p>
      </main>
      <TabBar />
    </>
  );
}
