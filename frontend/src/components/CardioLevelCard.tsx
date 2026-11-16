// How much cardio to aim for each week. "Auto" follows the goal (fat loss: regular;
// others: light). Cardio is always optional: this only sets the weekly target shown.
import { useEffect, useState } from "react";

import { ApiError, api } from "../api";
import { localISO } from "../plan";
import type { ActivityWeek, CardioLevel, CardioLevelInfo } from "../types";

export function CardioLevelCard({ levels }: { levels: CardioLevelInfo[] }) {
  const today = localISO();
  const [week, setWeek] = useState<ActivityWeek | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<ActivityWeek>(`/activities/week?today=${today}`)
      .then(setWeek)
      .catch(() => setWeek(null));
  }, [today]);

  async function choose(level: CardioLevel | null) {
    setError(null);
    try {
      setWeek(await api<ActivityWeek>(`/activities/level?today=${today}`, { method: "PUT", body: { level } }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save. Try again.");
    }
  }

  if (!week) return null;
  const auto = levels.find((l) => l.id === week.level);
  return (
    <section className="card">
      <div className="card-head">
        <h2>Cardio</h2>
        <span className="muted small">{week.target_minutes ? `${week.target_minutes} min a week` : "No target"}</span>
      </div>
      <div className="segmented wrap" role="group" aria-label="Cardio each week">
        <button type="button" aria-pressed={week.chosen === null} onClick={() => choose(null)}>
          Auto
        </button>
        {levels.map((l) => (
          <button key={l.id} type="button" aria-pressed={week.chosen === l.id} onClick={() => choose(l.id)}>
            {l.name}
          </button>
        ))}
      </div>
      <p className="muted small">
        {week.chosen === null
          ? `Auto follows your goal: ${auto?.name.toLowerCase()} (${week.target_minutes} minutes a week). `
          : ""}
        Always optional, on top of lifting. A 5-minute warm-up before lifting is advised either way.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
