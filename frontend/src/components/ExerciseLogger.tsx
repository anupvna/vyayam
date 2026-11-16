// One exercise in today's workout: target, the sets you've logged, and a row to log
// the next set. Each set gets an id made here (crypto.randomUUID), so a retry after a
// network blip can never save it twice.
import { useState } from "react";
import { Link } from "react-router";

import { ApiError, QUEUED, api } from "../api";
import { offlineSet } from "../offline/queue";
import { formatWeight, nextSetDefaults, parseSet, targetLine, unitLabel } from "../logging";
import { effortLabel, formatRest, formatSets } from "../plan";
import type { LoggedSet, PlannedExercise, Target, UnitSystem } from "../types";

type Props = {
  exercise: PlannedExercise;
  target: Target;
  logged: LoggedSet[];
  units: UnitSystem;
  day: string;
  onLogged: (set: LoggedSet) => void;
  onDeleted: (id: string) => void;
};

const EFFORT = [
  { rir: 0, label: "Failure" },
  { rir: 1, label: "1 left" },
  { rir: 2, label: "2 left" },
  { rir: 3, label: "3 left" },
  { rir: 4, label: "4+" },
];

export function ExerciseLogger({ exercise: e, target, logged, units, day, onLogged, onDeleted }: Props) {
  const defaults = nextSetDefaults(target, logged, units);
  const [weight, setWeight] = useState(defaults.weight);
  const [reps, setReps] = useState(defaults.reps);
  const [rir, setRir] = useState<number>(e.rir);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const done = logged.length >= e.sets;
  const [open, setOpen] = useState(!done);

  async function logSet() {
    const parsed = parseSet(weight, reps, units);
    if ("error" in parsed) return setError(parsed.error);
    setBusy(true);
    setError(null);
    try {
      const body = {
        id: crypto.randomUUID(),
        day,
        exercise_id: e.exercise_id,
        set_index: logged.length + 1,
        ...parsed,
        rir,
      };
      // No signal: the set is kept on the phone and synced later (shown the same way).
      const saved = await api<LoggedSet>("/logs", { method: "POST", body, offline: () => offlineSet(body) });
      onLogged(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save the set. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await api(`/logs/${id}`, { method: "DELETE", offline: () => QUEUED });
      onDeleted(id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't undo the set. Try again.");
    }
  }

  return (
    <li className={`logger ${done ? "done" : ""}`}>
      <button type="button" className="logger-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="workout-name">
          {e.name}
          {e.kind === "main" && <span className="badge">Main lift</span>}
          {e.light && <span className="badge quiet">Light today</span>}
        </span>
        <span className="workout-sets">{done ? "✓" : `${logged.length}/${e.sets}`}</span>
        <span className="workout-meta">
          {formatSets(e)}. {effortLabel(e.rir)}. Rest {formatRest(e.rest_seconds)}.
        </span>
      </button>

      {open && (
        <div className="logger-body">
          <p className="target">
            <b>Target: {targetLine(target, units)}</b>
            <small>{target.reason}</small>
          </p>

          {logged.length > 0 && (
            <ol className="sets">
              {logged.map((s) => (
                <li key={s.id}>
                  <span>Set {s.set_index}</span>
                  <span>
                    {formatWeight(s.weight_kg, units)} × {s.reps}
                  </span>
                  {s.pr && <span className="badge pr">PR</span>}
                  <button type="button" className="link small danger" aria-label={`Delete set ${s.set_index}`} onClick={() => remove(s.id)}>
                    Undo
                  </button>
                </li>
              ))}
            </ol>
          )}

          {!done && (
            <>
              <div className="set-entry">
                <label>
                  <span className="hint">{unitLabel(units)}</span>
                  <input inputMode="decimal" value={weight} placeholder="Body" onChange={(ev) => setWeight(ev.target.value)} />
                </label>
                <label>
                  <span className="hint">Reps</span>
                  <input inputMode="numeric" value={reps} onChange={(ev) => setReps(ev.target.value)} />
                </label>
                <button type="button" className="primary" disabled={busy} onClick={logSet}>
                  {busy ? "…" : `Log set ${logged.length + 1}`}
                </button>
              </div>
              <div className="effort" role="group" aria-label="Reps left in the tank">
                <span className="hint">Reps left in the tank</span>
                <div className="segmented">
                  {EFFORT.map((x) => (
                    <button key={x.rir} type="button" aria-pressed={rir === x.rir} onClick={() => setRir(x.rir)}>
                      {x.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <Link to={`/exercises/${e.exercise_id}`} className="link small">
            How to do it, and alternatives
          </Link>
        </div>
      )}
    </li>
  );
}
