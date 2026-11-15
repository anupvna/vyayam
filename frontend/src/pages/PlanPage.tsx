// Plan tab: this week day by day. Skip a day (the rest of the week re-plans around
// it) or restore it. Change split from here.
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router";

import { ApiError, api } from "../api";
import { TabBar } from "../components/TabBar";
import { WorkoutList } from "../components/WorkoutList";
import { WEEKDAY_FULL, localISO, parseISO } from "../plan";
import type { PlanDay, Week } from "../types";

export function PlanPage() {
  const today = localISO();
  const [week, setWeek] = useState<Week | null>(null);
  const [missing, setMissing] = useState<"split" | "profile" | null>(null);
  const [open, setOpen] = useState<string | null>(today);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api<Week>(`/plan/week?today=${today}`)
      .then(setWeek)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setMissing(err.message.includes("split") ? "split" : "profile");
        } else setError("Couldn't load your plan. Check your connection and refresh.");
      });
  }, [today]);

  useEffect(load, [load]);

  if (missing === "split") return <Navigate to="/plan/split" replace />;
  if (missing === "profile") return <Navigate to="/onboarding" replace />;
  if (!week) return <div className="splash">{error ?? "Loading…"}</div>;

  async function act(day: PlanDay, action: "skip" | "restore") {
    setBusy(true);
    setError(null);
    try {
      if (action === "skip") {
        setWeek(await api<Week>(`/plan/days/${day.date}/skip`, { method: "POST", body: { today } }));
      } else {
        await api(`/plan/days/${day.date}`, { method: "DELETE" });
        load();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <main className="page">
        <header className="page-head">
          <div>
            <p className="greeting">{week.split.name}</p>
            <h1>This week</h1>
          </div>
          <Link to="/plan/split" className="link small">
            Change split
          </Link>
        </header>

        {(week.deload || week.notes.length > 0) && (
          <ul className="advice">
            {week.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <ul className="days">
          {week.days.map((d) => {
            const date = parseISO(d.date);
            const isOpen = open === d.date;
            const past = d.date < today;
            return (
              <li key={d.date} className={`day ${d.status} ${d.date === today ? "is-today" : ""}`}>
                <button
                  type="button"
                  className="day-head"
                  aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? null : d.date)}
                  disabled={d.status === "rest"}
                >
                  <span className="day-date">
                    <b>{WEEKDAY_FULL[date.getDay()]}</b>
                    <small>{date.getDate()}</small>
                  </span>
                  <span className="day-title">
                    {d.status === "rest" ? "Rest" : d.status === "skipped" ? "Skipped" : d.session_name}
                    {d.status === "planned" && <small>{d.minutes} min</small>}
                    {(d.swapped || d.moved) && <small className="changed">{d.swapped ? "Swapped" : "Moved"}</small>}
                  </span>
                </button>
                {isOpen && d.status === "planned" && (
                  <div className="day-body">
                    {d.notes.map((n) => (
                      <p key={n} className="muted small">
                        {n}
                      </p>
                    ))}
                    <WorkoutList exercises={d.exercises} />
                    {!past && (
                      <button type="button" className="link danger" disabled={busy} onClick={() => act(d, "skip")}>
                        Skip this day
                      </button>
                    )}
                  </div>
                )}
                {isOpen && d.status === "skipped" && !past && (
                  <div className="day-body">
                    <button type="button" className="link" disabled={busy} onClick={() => act(d, "restore")}>
                      Train this day after all
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </main>
      <TabBar />
    </>
  );
}
