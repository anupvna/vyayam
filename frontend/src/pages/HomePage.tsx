// Home ("Today"): check in, then do today's workout: targets per exercise, log each
// set, rest timer, PR celebrations. The safety layer comes first: a red flag in the
// check-in replaces the workout with "stop and get help".
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router";

import { ApiError, api } from "../api";
import { savedMinutes, saveMinutes } from "../coach";
import { CheckInCard } from "../components/CheckInCard";
import { EquipmentArt } from "../components/EquipmentArt";
import { ExerciseLogger } from "../components/ExerciseLogger";
import { RestTimer } from "../components/RestTimer";
import { ActivityCard, AfterWorkout, WarmupCard } from "../components/TodayExtras";
import { TabBar } from "../components/TabBar";
import { SYNCED_EVENT, getStatus, syncEvents } from "../offline/status";
import { goalName } from "../labels";
import { formatWeight } from "../logging";
import { WEEKDAY, WEEKDAY_FULL, addDaysISO, localISO, parseISO } from "../plan";
import type { ActivityToday, Catalog, Gym, LoggedSet, Profile, TrainingToday, Week } from "../types";
import { kgToLb, round1 } from "../units";

type Base = { profile: Profile; gym: Gym | undefined; gyms: Gym[]; week: Week; catalog: Catalog };

const MAT_PLACE = "home (mat only)";
type Load =
  | { state: "loading" }
  | { state: "needs-onboarding" }
  | { state: "needs-split" }
  | { state: "error" }
  | ({ state: "ready" } & Base);

function greeting(hour: number): string {
  if (hour < 5) return "Up late";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

const TIME_OPTIONS = [30, 45, 60];

function skippedCheckInKey(day: string) {
  return `vy-checkin-skipped-${day}`;
}

export function HomePage() {
  const today = localISO();
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [training, setTraining] = useState<TrainingToday | null>(null);
  const [minutes, setMinutes] = useState<number | null>(null);
  const [checkInSkipped, setCheckInSkipped] = useState(() => {
    try {
      return localStorage.getItem(skippedCheckInKey(today)) === "1";
    } catch {
      return false;
    }
  });
  const [easyChosen, setEasyChosen] = useState(false);
  const [changing, setChanging] = useState(false);
  const [pickMuscles, setPickMuscles] = useState<string[]>([]);
  const [rest, setRest] = useState<{ endsAt: number; total: number } | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [extras, setExtras] = useState<ActivityToday | null>(null);

  const loadExtras = useCallback(async () => {
    try {
      setExtras(await api<ActivityToday>(`/activities/today?today=${today}`));
    } catch {
      setExtras(null); // optional extras: the workout still works without them
    }
  }, [today]);

  const loadTraining = useCallback(
    async (m: number | null) => {
      const q = m ? `&minutes=${m}` : "";
      setTraining(await api<TrainingToday>(`/training/today?today=${today}${q}`));
    },
    [today],
  );

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
      const kept = savedMinutes(today); // "shorten today" survives a reload
      await loadTraining(kept);
      setMinutes(kept);
      setLoad({ state: "ready", profile, gym: gyms.find((g) => g.is_active), gyms, week, catalog });
      void loadExtras();
    } catch (err) {
      setLoad(err instanceof ApiError && err.status === 404 ? { state: "needs-onboarding" } : { state: "error" });
    }
  }, [today, loadTraining, loadExtras]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // After offline sets sync, reload so records (PRs) worked out by the server show up.
  useEffect(() => {
    const onSynced = () => {
      void loadTraining(minutes).catch(() => undefined);
      void loadExtras();
    };
    syncEvents.addEventListener(SYNCED_EVENT, onSynced);
    return () => syncEvents.removeEventListener(SYNCED_EVENT, onSynced);
  }, [loadTraining, loadExtras, minutes]);

  // Save tomorrow's workout on the phone too, so it opens at a gym with no signal.
  useEffect(() => {
    if (load.state !== "ready" || !getStatus().online) return;
    const tomorrow = addDaysISO(today, 1);
    const id = window.setTimeout(() => {
      api(`/plan/week?today=${tomorrow}`)
        .then(() => api(`/training/today?today=${tomorrow}`))
        .catch(() => undefined);
    }, 2000);
    return () => window.clearTimeout(id);
  }, [load.state, today]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(id);
  }, [toast]);

  const endRest = useCallback(() => setRest(null), []);

  if (load.state === "loading") return <div className="splash">Loading…</div>;
  if (load.state === "needs-onboarding") return <Navigate to="/onboarding" replace />;
  if (load.state === "needs-split") return <Navigate to="/plan/split" replace />;
  if (load.state === "error" || !training)
    return (
      <div className="splash">
        {getStatus().online
          ? "Couldn't load. Check your connection and refresh."
          : "You're offline, and today's workout isn't saved on this phone yet. Open the app once with a connection before you head to the gym."}
      </div>
    );

  const { profile: p, gym, gyms, week, catalog } = load;
  const units = p.unit_system;
  const weight = (kg: number) => (units === "metric" ? `${round1(kg)} kg` : `${round1(kgToLb(kg))} lb`);
  const timeline = p.advice.find((a) => a.code === "timeline");
  const gear = gym?.equipment.slice(0, 4) ?? [];
  const now = new Date();
  const day = training.day;
  const fullMinutes = week.days.find((d) => d.date === today)?.minutes ?? day.minutes;
  const next = week.days.find((d) => d.date > today && d.status === "planned");
  const muscleName = (id: string) => catalog.muscles.find((m) => m.id === id)?.name ?? id;
  const needsCheckIn = day.status === "planned" && !training.readiness && !checkInSkipped;
  const planned = day.status === "planned" && !training.stop;
  const setsDone = training.exercises.reduce((n, e) => n + e.logged.length, 0);
  const setsTotal = day.exercises.reduce((n, e) => n + e.sets, 0);
  const extraBase = { day: today, units, weightKg: p.weight_kg, catalog, onChange: () => void loadExtras() };
  const placeGym = day.place && day.place !== MAT_PLACE ? gyms.find((g) => g.name === day.place) : undefined;
  const placeValue = day.place === MAT_PLACE ? "mat" : (placeGym?.id ?? gym?.id ?? "");
  const placeEquipment = day.place === MAT_PLACE ? ["mat"] : (placeGym ?? gym)?.equipment ?? [];

  function choosePlace(value: string) {
    void run(async () => {
      if (value === "mat") await api(`/plan/days/${today}/place`, { method: "PUT", body: { today, mat: true } });
      else if (value === gym?.id) await api(`/plan/days/${today}/place`, { method: "DELETE" });
      else await api(`/plan/days/${today}/place`, { method: "PUT", body: { today, gym_id: value } });
    });
  }

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
    saveMinutes(today, m);
    await loadTraining(m);
  }

  function onLogged(exerciseId: string, set: LoggedSet) {
    if (!training) return;
    setTraining({
      ...training,
      exercises: training.exercises.map((x) =>
        x.exercise_id === exerciseId ? { ...x, logged: [...x.logged.filter((s) => s.id !== set.id), set] } : x,
      ),
    });
    const ex = day.exercises.find((x) => x.exercise_id === exerciseId);
    if (ex) setRest({ endsAt: Date.now() + ex.rest_seconds * 1000, total: ex.rest_seconds });
    if (set.pr) {
      setToast(`New personal record! ${ex?.name}: ${formatWeight(set.weight_kg, units)} × ${set.reps}`);
      navigator.vibrate?.(80);
    }
  }

  function onDeleted(exerciseId: string, id: string) {
    if (!training) return;
    setTraining({
      ...training,
      exercises: training.exercises.map((x) =>
        x.exercise_id === exerciseId ? { ...x, logged: x.logged.filter((s) => s.id !== id) } : x,
      ),
    });
  }

  function skipCheckIn() {
    setCheckInSkipped(true);
    try {
      localStorage.setItem(skippedCheckInKey(today), "1");
    } catch {
      // storage unavailable: skipping still works for this visit
    }
  }

  return (
    <>
      <main className="page">
        <header className="page-head">
          <div>
            <p className="greeting">{greeting(now.getHours())}</p>
            <h1>Today</h1>
          </div>
          <div className="head-right">
            {planned && setsDone > 0 && (
              <span className="badge">
                {setsDone}/{setsTotal} sets
              </span>
            )}
            <Link to="/profile" className="avatar" aria-label="Profile and gyms">
              <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
                <path
                  d="M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8zM4 21c1-4 4-6 8-6s7 2 8 6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              </svg>
            </Link>
          </div>
        </header>

        {training.stop && (
          <section className="stop-card" role="alert">
            <h2>Stop. No training today.</h2>
            {training.readiness?.messages.map((m) => <p key={m}>{m}</p>)}
            <p className="small">You can update today's check-in if you ticked something by mistake.</p>
            <button type="button" className="secondary" onClick={() => setTraining({ ...training, readiness: null, stop: false })}>
              Redo check-in
            </button>
          </section>
        )}

        {!training.stop && needsCheckIn && (
          <CheckInCard
            today={today}
            catalog={catalog}
            onDone={() => {
              window.scrollTo(0, 0);
              void loadTraining(minutes);
            }}
            onSkip={() => {
              window.scrollTo(0, 0);
              skipCheckIn();
            }}
          />
        )}

        {!training.stop && !needsCheckIn && (
          <section className="today" aria-label="Today's workout">
            <div>
              <div className="today-day">{WEEKDAY_FULL[now.getDay()]}</div>
              {day.status === "planned" && (
                <p className="today-state">
                  {day.session_name}, about {day.minutes} minutes
                </p>
              )}
              {day.status === "rest" && <p className="today-state">Rest day</p>}
              {day.status === "skipped" && <p className="today-state">Skipped</p>}
              {training.deload && <p className="muted small">Deload week: lighter on purpose.</p>}
            </div>

            {training.suggest_rest && !easyChosen && (
              <div className="advice-block">
                <p>{training.readiness?.messages[0]}</p>
                <div className="actions">
                  <button
                    type="button"
                    className="primary"
                    disabled={busy}
                    onClick={() => run(() => api(`/plan/days/${today}/skip`, { method: "POST", body: { today } }))}
                  >
                    Rest today
                  </button>
                  <button type="button" className="secondary" onClick={() => setEasyChosen(true)}>
                    Do the easy version
                  </button>
                </div>
              </div>
            )}

            {planned && (!training.suggest_rest || easyChosen) && (
              <>
                {setsDone === 0 || day.place ? (
                  <label className="place-row">
                    <span className="muted small">Training at</span>
                    <select className="select" value={placeValue} disabled={busy || setsDone > 0} onChange={(e) => choosePlace(e.target.value)}>
                      {gyms.map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.name}
                          {g.is_active ? " (usual)" : ""}
                        </option>
                      ))}
                      <option value="mat">Home, mat only</option>
                    </select>
                  </label>
                ) : null}
                <div className="time-row" role="group" aria-label="Time available">
                  <span className="muted small">Time today</span>
                  <div className="segmented">
                    <button type="button" aria-pressed={minutes === null} onClick={() => shorten(null)}>
                      Full
                    </button>
                    {TIME_OPTIONS.filter((m) => m < fullMinutes).map((m) => (
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
                {extras?.warmup && <WarmupCard s={extras.warmup} base={extraBase} />}
                <ol className="workout">
                  {day.exercises.map((e) => {
                    const t = training.exercises.find((x) => x.exercise_id === e.exercise_id);
                    return t ? (
                      <ExerciseLogger
                        key={`${e.exercise_id}-${minutes}`}
                        exercise={e}
                        target={t.target}
                        logged={t.logged}
                        units={units}
                        day={today}
                        onLogged={(s) => onLogged(e.exercise_id, s)}
                        onDeleted={(id) => onDeleted(e.exercise_id, id)}
                      />
                    ) : null;
                  })}
                </ol>
                {extras && <AfterWorkout t={extras} base={extraBase} />}
                {setsDone === 0 && (
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
                )}
              </>
            )}

            {day.status === "rest" && (
              <p className="muted">
                Recovery is when muscle is built.
                {next && ` Next: ${next.session_name} on ${WEEKDAY_FULL[parseISO(next.date).getDay()]}.`}
              </p>
            )}

            {day.status === "skipped" && (
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

            {changing && planned && (
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
                          run(() => api(`/plan/days/${today}/swap`, { method: "POST", body: { session_key: s.key, today } }))
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
                        onClick={() => setPickMuscles(on ? pickMuscles.filter((x) => x !== m.id) : [...pickMuscles, m.id].slice(0, 6))}
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
                  onClick={() => run(() => api(`/plan/days/${today}/swap`, { method: "POST", body: { muscles: pickMuscles, today } }))}
                >
                  Build my session
                </button>
                <p className="hint">Your planned session moves later in the week. Muscles trained yesterday are kept light.</p>
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
                const doneDay = (d.logged_sets ?? 0) > 0 || (d.date === today && setsDone > 0);
                return (
                  <Link
                    to="/plan"
                    key={d.date}
                    className={`${d.status === "planned" ? "train" : d.status} ${d.date === today ? "is-today" : ""} ${doneDay ? "done" : ""}`}
                    aria-label={`${WEEKDAY_FULL[date.getDay()]}: ${doneDay ? "done" : d.status === "planned" ? d.session_name : d.status}`}
                  >
                    <i>{doneDay ? "✓" : ""}</i>
                    {WEEKDAY[date.getDay()].slice(0, 2)}
                  </Link>
                );
              })}
            </div>
          </section>
        )}

        {!training.stop && extras && <ActivityCard t={extras} base={extraBase} equipment={placeEquipment} />}

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
              {gym && gym.equipment.length > gear.length && <span className="more">+{gym.equipment.length - gear.length}</span>}
            </div>
          )}
        </section>
      </main>
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
      {rest && <RestTimer endsAt={rest.endsAt} total={rest.total} onDone={endRest} />}
      <TabBar />
    </>
  );
}
