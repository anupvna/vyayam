// Today's optional extras around the lifting: a warm-up (advised), a finisher and
// cool-down stretches (optional), and the activity card for logging any cardio or
// floor work, any day.
import { useState } from "react";

import { ApiError, QUEUED, api } from "../api";
import { describe, type Units } from "../activity";
import type { Activity, ActivityPart, ActivityToday, Catalog, Intensity, Suggestion } from "../types";
import { ActivityForm, saveActivity } from "./ActivityForm";

const PART_NAMES: Record<ActivityPart, string> = { warmup: "warm-up", main: "", finisher: "finisher", cooldown: "cool-down" };

type Base = { day: string; units: Units; weightKg: number; catalog: Catalog; onChange: () => void };

async function quickLog(
  base: Base,
  activity: string,
  minutes: number,
  part: ActivityPart,
  intensity: Intensity = "moderate",
) {
  await saveActivity(
    {
      id: crypto.randomUUID(),
      day: base.day,
      activity,
      part,
      minutes,
      intensity,
      speed_kmh: null,
      incline_pct: null,
      level: null,
      distance_km: null,
      calories: null,
      items: [],
      note: "",
    },
    base.catalog,
    base.weightKg,
  );
  base.onChange();
}

export function WarmupCard({ s, base }: { s: Suggestion; base: Base }) {
  const [busy, setBusy] = useState(false);
  return (
    <div className={`extra warmup ${s.done ? "done" : ""}`}>
      <div>
        <span className="extra-label">Warm-up · advised</span>
        <p>{s.text}</p>
      </div>
      {s.done ? (
        <span className="extra-done">✓ Done</span>
      ) : (
        <button
          type="button"
          className="action"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await quickLog(base, s.activity, s.minutes, "warmup", "easy").finally(() => setBusy(false));
          }}
        >
          Done, log {s.minutes} min
        </button>
      )}
    </div>
  );
}

export function AfterWorkout({ t, base }: { t: ActivityToday; base: Base }) {
  const [busy, setBusy] = useState(false);
  const stretchesDone = t.activities.some((a) => a.part === "cooldown");
  const log = async (activity: string, minutes: number, part: ActivityPart, intensity: Intensity) => {
    setBusy(true);
    await quickLog(base, activity, minutes, part, intensity).finally(() => setBusy(false));
  };
  return (
    <>
      {t.finisher && (
        <div className={`extra ${t.finisher.done ? "done" : ""}`}>
          <div>
            <span className="extra-label">Finisher · optional</span>
            <p>{t.finisher.text.replace(/^Optional: /, "")}</p>
          </div>
          {t.finisher.done ? (
            <span className="extra-done">✓ Done</span>
          ) : (
            <button
              type="button"
              className="action"
              disabled={busy}
              onClick={() => t.finisher && log(t.finisher.activity, t.finisher.minutes, "finisher", "hard")}
            >
              Done, log it
            </button>
          )}
        </div>
      )}
      {t.cooldown.length > 0 && (
        <details className="extra cooldown">
          <summary>
            <span className="extra-label">Cool-down · optional</span>
            <span>
              {t.cooldown.length} stretches, about {t.cooldown_minutes} min
            </span>
          </summary>
          <ul className="stretches">
            {t.cooldown.map((s) => (
              <li key={s.id}>
                <b>
                  {s.name} <small>{s.seconds} s{s.each_side ? " each side" : ""}</small>
                </b>
                <span>{s.how}</span>
              </li>
            ))}
          </ul>
          {stretchesDone ? (
            <span className="extra-done">✓ Stretched</span>
          ) : (
            <button type="button" className="action" disabled={busy} onClick={() => log("stretching", t.cooldown_minutes, "cooldown", "easy")}>
              Done, log stretches
            </button>
          )}
        </details>
      )}
    </>
  );
}

export function ActivityCard({ t, base, equipment }: { t: ActivityToday; base: Base; equipment: string[] }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pct = t.week_target ? Math.min(100, (t.week_done / t.week_target) * 100) : 0;

  async function remove(a: Activity) {
    setError(null);
    try {
      await api(`/activities/${a.id}`, { method: "DELETE", offline: () => QUEUED });
      base.onChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete. Try again.");
    }
  }

  return (
    <section className="card activity-card">
      <div className="card-head">
        <h2>Activity</h2>
        {t.week_target > 0 && (
          <span className="muted small">
            Cardio this week: {t.week_done} of {t.week_target} min
          </span>
        )}
      </div>
      {t.week_target > 0 && (
        <div className="cardio-bar" role="img" aria-label={`${t.week_done} of ${t.week_target} cardio minutes this week`}>
          <span style={{ width: `${pct}%` }} />
        </div>
      )}
      {t.rest_day && <p className="muted">{t.rest_day}</p>}

      {t.activities.length > 0 && (
        <ul className="activity-list">
          {t.activities.map((a) => (
            <li key={a.id}>
              <div>
                <b>
                  {a.name}
                  {a.part !== "main" && <small> · {PART_NAMES[a.part]}</small>}
                </b>
                <span className="muted small">{describe(a, base.units)}</span>
                {a.item_names.length > 0 && <span className="muted small">{a.item_names.join(", ")}</span>}
              </div>
              <button type="button" className="icon-btn" aria-label={`Delete ${a.name}`} onClick={() => remove(a)}>
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {open ? (
        <ActivityForm
          day={base.day}
          units={base.units}
          weightKg={base.weightKg}
          catalog={base.catalog}
          equipment={equipment}
          onSaved={() => {
            setOpen(false);
            base.onChange();
          }}
          onCancel={() => setOpen(false)}
        />
      ) : (
        <button type="button" className="secondary" onClick={() => setOpen(true)}>
          Log cardio or a mat workout
        </button>
      )}
      <p className="hint">Optional. Anything counts: treadmill, a walk, jump rope, or floor exercises at home.</p>
    </section>
  );
}
