// One exercise in today's workout: target, the sets you've logged, and a row to log
// the next set. Each set gets an id made here (crypto.randomUUID), so a retry after a
// network blip can never save it twice.
import { useState } from "react";
import { Link } from "react-router";

import { ApiError, QUEUED, api } from "../api";
import { askWhy } from "../coach";
import { offlineSet } from "../offline/queue";
import {
  MAX_SETS,
  clampSets,
  formatWeight,
  isBarbell,
  lastLine,
  nextSetDefaults,
  parseSet,
  targetLine,
  weightHint,
} from "../logging";
import { effortLabel, formatRest, formatSets } from "../plan";
import type { LastSession, Load, LoggedSet, PlannedExercise, Target, UnitSystem } from "../types";

type Props = {
  exercise: PlannedExercise;
  target: Target;
  logged: LoggedSet[];
  load?: Load;
  last?: LastSession | null;
  units: UnitSystem;
  day: string;
  onLogged: (set: LoggedSet) => void;
  onDeleted: (id: string) => void;
};

// Today's set count for one exercise, if the user changed it. Kept on this device.
const setsKey = (day: string, id: string) => `vyayam:sets:${day}:${id}`;
function savedSets(day: string, id: string): number | null {
  try {
    const v = Number(localStorage.getItem(setsKey(day, id)));
    return v > 0 ? v : null;
  } catch {
    return null;
  }
}

export function ExerciseLogger({ exercise: e, target, logged, load, last, units, day, onLogged, onDeleted }: Props) {
  const defaults = nextSetDefaults(target, logged, units, last);
  const [weight, setWeight] = useState(defaults.weight);
  const [reps, setReps] = useState(defaults.reps);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [wanted, setWanted] = useState(() => savedSets(day, e.exercise_id) ?? e.sets);
  const sets = clampSets(wanted, e.sets, logged.length);
  const done = logged.length >= sets;
  const [open, setOpen] = useState(!done);

  function changeSets(n: number) {
    const next = clampSets(n, e.sets, logged.length);
    setWanted(next);
    try {
      if (next === e.sets) localStorage.removeItem(setsKey(day, e.exercise_id));
      else localStorage.setItem(setsKey(day, e.exercise_id), String(next));
    } catch {
      // private mode: the change lasts until the page reloads
    }
    if (next > logged.length) setOpen(true);
  }

  // After a set is logged or undone, pre-fill the next one (a pyramid's next step).
  function prefill(after: LoggedSet[]) {
    const d = nextSetDefaults(target, after, units, last);
    setWeight(d.weight);
    setReps(d.reps);
  }

  async function logSet() {
    const parsed = parseSet(weight, reps, units, load);
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
      };
      // No signal: the set is kept on the phone and synced later (shown the same way).
      const saved = await api<LoggedSet>("/logs", { method: "POST", body, offline: () => offlineSet(body) });
      onLogged(saved);
      prefill([...logged, saved]);
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
      prefill(logged.filter((s) => s.id !== id));
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
        <span className="workout-sets">{done ? "✓" : `${logged.length}/${sets}`}</span>
        <span className="workout-meta">
          {formatSets({ ...e, sets })}. {effortLabel(e.rir)}. Rest {formatRest(e.rest_seconds)}.
        </span>
      </button>

      {open && (
        <div className="logger-body">
          <p className="target">
            <b>Target: {targetLine(target, units, load)}</b>
            <small>{target.reason}</small>
            {last && <small className="last-time">Last time, {lastLine(last, units)}</small>}
            <Link className="link small ask" to={`/coach?ask=${encodeURIComponent(askWhy(e.name))}`}>
              Ask the coach why
            </Link>
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
                  <span className="hint">{weightHint(load, units)}</span>
                  <input
                    inputMode="decimal"
                    value={weight}
                    placeholder={isBarbell(load) ? "Bar + plates" : load === null ? "Body" : ""}
                    onChange={(ev) => setWeight(ev.target.value)}
                  />
                </label>
                <label>
                  <span className="hint">Reps</span>
                  <input inputMode="numeric" value={reps} onChange={(ev) => setReps(ev.target.value)} />
                </label>
                <button type="button" className="primary" disabled={busy} onClick={logSet}>
                  {busy ? "…" : `Log set ${logged.length + 1}`}
                </button>
              </div>
            </>
          )}
          <div className="set-count">
            <span className="hint">Sets today</span>
            <div className="stepper">
              <button type="button" aria-label="One set fewer" disabled={sets <= Math.max(1, logged.length)} onClick={() => changeSets(sets - 1)}>
                −
              </button>
              <output aria-live="polite">{sets}</output>
              <button type="button" aria-label="One more set" disabled={sets >= Math.max(MAX_SETS, e.sets)} onClick={() => changeSets(sets + 1)}>
                +
              </button>
            </div>
            <small className="hint">
              {sets >= Math.max(MAX_SETS, e.sets)
                ? `${sets} is the most that helps in one session. For more, train it on another day.`
                : sets !== e.sets
                  ? `Planned: ${e.sets}.`
                  : ""}
            </small>
          </div>
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
