// Training progress: weekly summary, recovery body map, volume per muscle vs target,
// push/pull balance, strength (e1RM) with PRs, and a consistency calendar.
import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import { Chart } from "../charts/Chart";
import { ACCENT, INK, STATUS, baseOption } from "../charts/theme";
import { MuscleMap } from "../components/MuscleMap";
import { kgToDisplay } from "../body";
import { parseISO } from "../plan";
import type {
  CalendarDay,
  Catalog,
  HistoryPoint,
  LoggedExercise,
  MuscleRecovery,
  Profile,
  VolumeStats,
  WeeklySummary,
} from "../types";

type Props = { today: string; profile: Profile; catalog: Catalog };

const MAJOR = ["chest", "lats", "upper_back", "front_delts", "quads", "glutes", "hamstrings"];
const STATE_LABEL = { fresh: "Fresh", recovering: "Recovering", fatigued: "Needs rest" };
const CAL_LABEL: Record<CalendarDay["status"], string> = {
  done: "Trained",
  missed: "Missed",
  skipped: "Skipped",
  rest: "Rest",
  upcoming: "Planned",
};

export function TrainingSection({ today, profile, catalog }: Props) {
  const u = profile.unit_system;
  const [summary, setSummary] = useState<WeeklySummary | null>(null);
  const [recovery, setRecovery] = useState<MuscleRecovery[]>([]);
  const [volume, setVolume] = useState<VolumeStats | null>(null);
  const [calendar, setCalendar] = useState<CalendarDay[]>([]);
  const [exercises, setExercises] = useState<LoggedExercise[]>([]);
  const [pick, setPick] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [allMuscles, setAllMuscles] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    Promise.all([
      api<WeeklySummary>(`/stats/summary?today=${today}`),
      api<MuscleRecovery[]>(`/stats/recovery?today=${today}`),
      api<VolumeStats>(`/stats/volume?today=${today}&weeks=8`),
      api<CalendarDay[]>(`/stats/calendar?today=${today}&weeks=12`),
      api<LoggedExercise[]>("/stats/exercises"),
    ])
      .then(([s, r, v, c, e]) => {
        setSummary(s);
        setRecovery(r);
        setVolume(v);
        setCalendar(c);
        setExercises(e);
        setPick(e[0]?.exercise_id ?? null);
      })
      .catch(() => setError(true));
  }, [today]);

  useEffect(() => {
    if (pick) api<HistoryPoint[]>(`/exercises/${pick}/history`).then(setHistory).catch(() => setHistory([]));
  }, [pick]);

  const muscleName = (id: string) => catalog.muscles.find((m) => m.id === id)?.name ?? id;

  const strengthOption = useMemo(() => {
    const pts = history.filter((h) => h.best_e1rm !== null);
    if (pts.length === 0) return null;
    const o = baseOption();
    return {
      ...o,
      yAxis: { ...o.yAxis, name: u === "metric" ? "kg" : "lb", nameTextStyle: { color: INK.muted } },
      tooltip: {
        ...o.tooltip,
        formatter: (ps: { data: [string, number, boolean] }[]) => {
          const p = ps[0].data;
          return `${p[0]}<br/>Estimated 1-rep max: <b>${p[1]}</b>${p[2] ? " · PR" : ""}`;
        },
      },
      series: [
        {
          name: "Estimated 1-rep max",
          type: "line",
          lineStyle: { width: 2, color: ACCENT },
          itemStyle: { color: ACCENT, borderColor: INK.surface, borderWidth: 2 },
          symbolSize: (v: [string, number, boolean]) => (v[2] ? 13 : 8),
          data: pts.map((h) => [h.day, kgToDisplay(h.best_e1rm as number, u), h.pr]),
        },
      ],
    };
  }, [history, u]);

  if (error) return <p className="muted">Couldn't load training stats. Check your connection and refresh.</p>;
  if (!summary || !volume) return <p className="muted">Loading…</p>;

  const colors = Object.fromEntries(recovery.map((r) => [r.muscle, STATUS[r.state]]));
  const tired = recovery.filter((r) => r.state === "fatigued").map((r) => muscleName(r.muscle));
  const rows = volume.muscles.filter((m) => allMuscles || MAJOR.includes(m.muscle));
  const thisWeek = (m: VolumeStats["muscles"][number]) => m.weekly[m.weekly.length - 1];
  const scale = Math.max(...rows.map((m) => Math.max(m.target_high, thisWeek(m))), 1);
  const total = volume.push_sets + volume.pull_sets;
  const weeks: CalendarDay[][] = [];
  calendar.forEach((d, i) => {
    if (i % 7 === 0) weeks.push([]);
    weeks[weeks.length - 1].push(d);
  });
  const trained = calendar.filter((d) => d.status === "done").length;
  const due = calendar.filter((d) => d.status === "done" || d.status === "missed").length;

  return (
    <div className="stack-tight progress-section">
      <section className="card summary-card">
        <h2>This week</h2>
        {summary.lines.map((l) => (
          <p key={l}>{l}</p>
        ))}
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Recovery</h2>
          <span className="muted small">Today</span>
        </div>
        <div className="mm-card">
          <MuscleMap primary={[]} secondary={[]} colors={colors} size={300} />
        </div>
        <ul className="legend" aria-label="Legend">
          {(["fresh", "recovering", "fatigued"] as const).map((s) => (
            <li key={s}>
              <i className="dot" style={{ background: STATUS[s] }} />
              {STATE_LABEL[s]}
            </li>
          ))}
        </ul>
        <p className="muted small">
          {tired.length ? `Needs rest: ${tired.join(", ")}.` : "Everything is recovered. Good to train."} Muscles need
          about 48 to 72 hours between hard sessions.
        </p>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Sets this week</h2>
          <button type="button" className="link small" onClick={() => setAllMuscles(!allMuscles)}>
            {allMuscles ? "Big muscles only" : "All muscles"}
          </button>
        </div>
        <ul className="volume" aria-label="Hard sets per muscle this week compared with the target range">
          {rows.map((m) => {
            const v = thisWeek(m);
            const state = v < m.target_low ? "under" : v > m.target_high ? "over" : "in";
            return (
              <li key={m.muscle}>
                <span className="vol-name">{muscleName(m.muscle)}</span>
                <span className="vol-track">
                  <span
                    className="vol-band"
                    style={{ left: `${(m.target_low / scale) * 100}%`, width: `${((m.target_high - m.target_low) / scale) * 100}%` }}
                  />
                  <span className={`vol-bar ${state}`} style={{ width: `${(v / scale) * 100}%` }} />
                </span>
                <span className="vol-num">
                  {v} <small>/ {m.target_low}–{m.target_high}</small>
                </span>
              </li>
            );
          })}
        </ul>
        <p className="hint">The shaded band is your weekly target. Half a set counts when a muscle helps but isn't the main mover.</p>
        <div className="balance">
          <span>Push {volume.push_sets}</span>
          <span className={`balance-track ${total ? "" : "empty"}`}>
            <span style={{ width: total ? `${(volume.push_sets / total) * 100}%` : "0%" }} />
          </span>
          <span>Pull {volume.pull_sets}</span>
        </div>
        {total > 6 && Math.abs(volume.push_sets - volume.pull_sets) / total > 0.25 && (
          <p className="muted small">
            Pushing and pulling are out of balance this week. Roughly equal work keeps shoulders healthy.
          </p>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Strength</h2>
        </div>
        {exercises.length === 0 ? (
          <p className="muted">Log a few workouts and your strength curve shows up here.</p>
        ) : (
          <>
            <select className="select" value={pick ?? ""} onChange={(e) => setPick(e.target.value)} aria-label="Exercise">
              {exercises.map((e) => (
                <option key={e.exercise_id} value={e.exercise_id}>
                  {e.name} ({e.sessions} {e.sessions === 1 ? "session" : "sessions"})
                </option>
              ))}
            </select>
            {strengthOption && <Chart option={strengthOption} height={210} label="Estimated one-rep max over time, larger dots are personal records" />}
            <p className="hint">Estimated 1-rep max (Epley: weight × (1 + reps ÷ 30)). Bigger dots are personal records.</p>
          </>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Consistency</h2>
          <span className="muted small">
            {trained} of {due} planned days trained
          </span>
        </div>
        <div className="cal" role="grid" aria-label="Last 12 weeks">
          {weeks.map((w) => (
            <div key={w[0].day} className="cal-week" role="row">
              {w.map((d) => (
                <span
                  key={d.day}
                  role="gridcell"
                  className={`cal-day ${d.status} ${d.day === today ? "is-today" : ""}`}
                  title={`${parseISO(d.day).toDateString()}: ${CAL_LABEL[d.status]}`}
                  aria-label={`${d.day}: ${CAL_LABEL[d.status]}`}
                />
              ))}
            </div>
          ))}
        </div>
        <ul className="legend">
          {(["done", "missed", "skipped", "rest", "upcoming"] as const).map((s) => (
            <li key={s}>
              <i className={`cal-day ${s}`} />
              {CAL_LABEL[s]}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
