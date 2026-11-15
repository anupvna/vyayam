// Home ("Today"): today's workout from the planner, with controls to shorten it,
// change it, or skip it. Below: your week, your goal and your gym.
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router";

import { ApiError, api } from "../api";
import { EquipmentArt } from "../components/EquipmentArt";
import { TabBar } from "../components/TabBar";
import { WorkoutList } from "../components/WorkoutList";
import { goalName } from "../labels";
import { WEEKDAY, WEEKDAY_FULL, localISO, parseISO } from "../plan";
import type { Catalog, Gym, PlanDay, Profile, Week } from "../types";
import { kgToLb, round1 } from "../units";

type Load =
  | { state: "loading" }
  | { state: "needs-onboarding" }
  | { state: "needs-split" }
  | { state: "error" }
  | { state: "ready"; profile: Profile; gym: Gym | undefined; week: Week; catalog: Catalog };

function greeting(hour: number): string {
  if (hour < 5) return "Up late";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

const TIME_OPTIONS = [30, 45, 60];

export function HomePage() {
  const today = localISO();
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [day, setDay] = useState<PlanDay | null>(null);
  const [minutes, setMinutes] = useState<number | null>(null);
  const [changing, setChanging] = useState(false);
  const [pickMuscles, setPickMuscles] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const profile = await api<Profile>("/profile");
      const [gyms, catalog] = await Promise.all([api<Gym[]>("/gyms"), api<Catalog>("/catalog")]);
      let week: Week;
      try {
        week = await api<Week>(`/plan/week?today=${today}`);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return setLoad({ state: "needs-split" });
        throw err;
      }
      setLoad({ state: "ready", profile, gym: gyms.find((g) => g.is_active), week, catalog });
      setDay(week.days.find((d) => d.date === today) ?? null);
      setMinutes(null);
    } catch (err) {
      setLoad(err instanceof ApiError && err.status === 404 ? { state: "needs-onboarding" } : { state: "error" });
    }
  }, [today]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (load.state === "loading") return <div className="splash">Loading…</div>;
  if (load.state === "needs-onboarding") return <Navigate to="/onboarding" replace />;
  if (load.state === "needs-split") return <Navigate to="/plan/split" replace />;
  if (load.state === "error") return <div className="splash">Couldn't load. Check your connection and refresh.</div>;

  const { profile: p, gym, week, catalog } = load;
  const weight = (kg: number) => (p.unit_system === "metric" ? `${round1(kg)} kg` : `${round1(kgToLb(kg))} lb`);
  const timeline = p.advice.find((a) => a.code === "timeline");
  const gear = gym?.equipment.slice(0, 4) ?? [];
  const now = new Date();
  const fullDay = week.days.find((d) => d.date === today);
  const next = week.days.find((d) => d.date > today && d.status === "planned");
  const muscleName = (id: string) => catalog.muscles.find((m) => m.id === id)?.name ?? id;

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setChanging(false);
      setPickMuscles([]);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function shorten(m: number | null) {
    setMinutes(m);
    if (m === null) return setDay(fullDay ?? null);
    setDay(await api<PlanDay>(`/plan/today?today=${today}&minutes=${m}`));
  }

  return (
    <>
      <main className="page">
        <header className="page-head">
          <div>
            <p className="greeting">{greeting(now.getHours())}</p>
            <h1>Today</h1>
          </div>
        </header>

        <section className="today" aria-label="Today's workout">
          <div>
            <div className="today-day">{WEEKDAY_FULL[now.getDay()]}</div>
            {day?.status === "planned" && (
              <p className="today-state">
                {day.session_name}, about {day.minutes} minutes
              </p>
            )}
            {day?.status === "rest" && <p className="today-state">Rest day</p>}
            {day?.status === "skipped" && <p className="today-state">Skipped</p>}
            {week.deload && <p className="muted small">Deload week: lighter on purpose.</p>}
          </div>

          {day?.status === "planned" && (
            <>
              <div className="time-row" role="group" aria-label="Time available">
                <span className="muted small">Time today</span>
                <div className="segmented">
                  <button type="button" aria-pressed={minutes === null} onClick={() => shorten(null)}>
                    Full
                  </button>
                  {TIME_OPTIONS.filter((m) => m < (fullDay?.minutes ?? 0)).map((m) => (
                    <button key={m} type="button" aria-pressed={minutes === m} onClick={() => shorten(m)}>
                      {m} min
                    </button>
                  ))}
                </div>
              </div>
              {day.notes.map((n) => (
                <p key={n} className="muted small">
                  {n}
                </p>
              ))}
              <WorkoutList exercises={day.exercises} />
              <div className="actions">
                <button type="button" className="secondary" onClick={() => setChanging(!changing)}>
                  {changing ? "Keep this workout" : "Change today's workout"}
                </button>
                <button
                  type="button"
                  className="link danger"
                  disabled={busy}
                  onClick={() => {
                    if (window.confirm("Skip today? The rest of your week will be re-planned around it.")) {
                      void run(() => api(`/plan/days/${today}/skip`, { method: "POST", body: { today } }));
                    }
                  }}
                >
                  Skip today
                </button>
              </div>
            </>
          )}

          {day?.status === "rest" && (
            <p className="muted">
              Recovery is when muscle is built.
              {next && ` Next: ${next.session_name} on ${WEEKDAY_FULL[parseISO(next.date).getDay()]}.`}
            </p>
          )}

          {day?.status === "skipped" && (
            <div className="actions">
              <p className="muted">Your week was re-planned around it.</p>
              <button
                type="button"
                className="link"
                disabled={busy}
                onClick={() => run(() => api(`/plan/days/${today}`, { method: "DELETE" }))}
              >
                Train today after all
              </button>
            </div>
          )}

          {changing && day?.status === "planned" && (
            <div className="change-panel">
              <h3>Do a different session</h3>
              <div className="choices">
                {week.split.sessions
                  .filter((s) => s.key !== day.session_key)
                  .map((s) => (
                    <button
                      key={s.key}
                      type="button"
                      className="choice"
                      disabled={busy}
                      onClick={() =>
                        run(() =>
                          api(`/plan/days/${today}/swap`, { method: "POST", body: { session_key: s.key, today } }),
                        )
                      }
                    >
                      <strong>{s.name}</strong>
                      <small>{s.focus.map(muscleName).join(", ")}</small>
                    </button>
                  ))}
              </div>
              <h3>Or pick the muscles</h3>
              <div className="pills">
                {catalog.muscles.map((m) => {
                  const on = pickMuscles.includes(m.id);
                  return (
                    <button
                      key={m.id}
                      type="button"
                      className="pill"
                      aria-pressed={on}
                      onClick={() =>
                        setPickMuscles(on ? pickMuscles.filter((x) => x !== m.id) : [...pickMuscles, m.id].slice(0, 6))
                      }
                    >
                      {m.name}
                    </button>
                  );
                })}
              </div>
              <button
                type="button"
                className="primary"
                disabled={busy || pickMuscles.length === 0}
                onClick={() =>
                  run(() => api(`/plan/days/${today}/swap`, { method: "POST", body: { muscles: pickMuscles, today } }))
                }
              >
                Build my session
              </button>
              <p className="hint">
                Your planned session moves later in the week. Muscles trained yesterday are kept light.
              </p>
            </div>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          <div className="week" aria-label="This week">
            {week.days.map((d) => {
              const date = parseISO(d.date);
              return (
                <Link
                  to="/plan"
                  key={d.date}
                  className={`${d.status === "planned" ? "train" : d.status} ${d.date === today ? "is-today" : ""}`}
                  aria-label={`${WEEKDAY_FULL[date.getDay()]}: ${d.status === "planned" ? d.session_name : d.status}`}
                >
                  <i />
                  {WEEKDAY[date.getDay()].slice(0, 2)}
                </Link>
              );
            })}
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
