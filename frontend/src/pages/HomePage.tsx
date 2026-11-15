// Home ("Today"): what kind of day it is, your week at a glance, your goal and your gym.
// The training session itself fills the Today card once the planner exists.
import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router";

import { ApiError, api } from "../api";
import { EquipmentArt } from "../components/EquipmentArt";
import { TabBar } from "../components/TabBar";
import { DAY_FULL, DAY_NAMES, goalName, todayIndex } from "../labels";
import type { Gym, Profile } from "../types";
import { kgToLb, round1 } from "../units";

type Load =
  | { state: "loading" }
  | { state: "needs-onboarding" }
  | { state: "error" }
  | { state: "ready"; profile: Profile; gym: Gym | undefined };

function greeting(hour: number): string {
  if (hour < 5) return "Up late";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function nextTrainingDay(days: number[], today: number): number | null {
  for (let step = 1; step <= 7; step++) {
    const d = (today + step) % 7;
    if (days.includes(d)) return d;
  }
  return null;
}

export function HomePage() {
  const [load, setLoad] = useState<Load>({ state: "loading" });

  useEffect(() => {
    Promise.all([api<Profile>("/profile"), api<Gym[]>("/gyms")])
      .then(([profile, gyms]) => setLoad({ state: "ready", profile, gym: gyms.find((g) => g.is_active) }))
      .catch((err) =>
        setLoad(err instanceof ApiError && err.status === 404 ? { state: "needs-onboarding" } : { state: "error" }),
      );
  }, []);

  if (load.state === "loading") return <div className="splash">Loading…</div>;
  if (load.state === "needs-onboarding") return <Navigate to="/onboarding" replace />;
  if (load.state === "error")
    return <div className="splash">Couldn't load. Check your connection and refresh.</div>;

  const { profile: p, gym } = load;
  const now = new Date();
  const today = todayIndex(now);
  const isTraining = p.training_days.includes(today);
  const next = nextTrainingDay(p.training_days, today);
  const weight = (kg: number) => (p.unit_system === "metric" ? `${round1(kg)} kg` : `${round1(kgToLb(kg))} lb`);
  const timeline = p.advice.find((a) => a.code === "timeline");
  const gear = gym?.equipment.slice(0, 4) ?? [];

  return (
    <>
      <main className="page">
        <header className="page-head">
          <div>
            <p className="greeting">{greeting(now.getHours())}</p>
            <h1>Today</h1>
          </div>
        </header>

        <section className="today" aria-label="Today">
          <div>
            <div className="today-day">{DAY_FULL[today]}</div>
            <p className="today-state">{isTraining ? `Training day, ${p.session_minutes} minutes` : "Rest day"}</p>
            <p className="muted" style={{ marginTop: "0.5rem" }}>
              {isTraining
                ? "Your exercises for today will appear here once your plan is ready."
                : next !== null
                  ? `Recovery is when muscle is built. Next session: ${DAY_FULL[next]}.`
                  : "Recovery is when muscle is built."}
            </p>
          </div>
          <div className="week" aria-label="This week">
            {DAY_NAMES.map((name, i) => (
              <div
                key={name}
                className={`${p.training_days.includes(i) ? "train" : ""} ${i === today ? "is-today" : ""}`}
                aria-label={`${DAY_FULL[i]}: ${p.training_days.includes(i) ? "training" : "rest"}`}
              >
                <i />
                {name.slice(0, 2)}
              </div>
            ))}
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>{goalName(p.goal)}</h2>
            <Link to="/profile" className="link small">
              Details
            </Link>
          </div>
          <div className="stats">
            <div className="stat">
              <span className="muted small">Now</span>
              <b>{weight(p.weight_kg)}</b>
            </div>
            <div className="stat">
              <span className="muted small">Target</span>
              <b>
                {p.target_weight_kg !== null
                  ? weight(p.target_weight_kg)
                  : p.target_body_fat_pct !== null
                    ? `${p.target_body_fat_pct}% fat`
                    : "Not set"}
              </b>
            </div>
          </div>
          {timeline && <p className="muted small">{timeline.message}</p>}
        </section>

        <section className="card">
          <div className="card-head">
            <div>
              <h2>{gym?.name ?? "No gym yet"}</h2>
              <span className="muted small">
                {gym ? `${gym.equipment.length} pieces of equipment` : "Add one so your plan knows what's there."}
              </span>
            </div>
            <Link to="/gyms" className="link small">
              Change
            </Link>
          </div>
          {gear.length > 0 && (
            <div className="gear">
              {gear.map((id) => (
                <span key={id}>
                  <EquipmentArt id={id} size={34} />
                </span>
              ))}
              {gym && gym.equipment.length > gear.length && (
                <span className="more">+{gym.equipment.length - gear.length}</span>
              )}
            </div>
          )}
        </section>
      </main>
      <TabBar />
    </>
  );
}
