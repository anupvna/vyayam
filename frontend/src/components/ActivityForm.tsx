// Log any cardio or floor work: pick what you did, enter the time, and only the fields
// that make sense for it appear (speed and incline for a treadmill, level for a bike,
// the moves you did for a mat workout). Calories are optional: without the machine's
// number, an estimate is shown and saved as an estimate.
import { useMemo, useState } from "react";

import { ApiError, api } from "../api";
import { distanceUnit, estimateCalories, offlineActivity, parsePositive, speedUnit, toKm, type Units } from "../activity";
import type { Activity, ActivityIn, ActivityKind, Catalog, FloorMove, Intensity } from "../types";

const GROUPS: { id: ActivityKind["group"]; label: string }[] = [
  { id: "machine", label: "Machines" },
  { id: "floor", label: "On the floor" },
  { id: "outdoor", label: "Outside" },
  { id: "other", label: "Other" },
];
const MOVE_GROUPS: { id: FloorMove["group"]; label: string }[] = [
  { id: "core", label: "Core & abs" },
  { id: "legs", label: "Legs & glutes" },
  { id: "upper", label: "Upper body" },
  { id: "hiit", label: "HIIT" },
  { id: "stretch", label: "Stretches" },
];
const INTENSITY: { id: Intensity; label: string }[] = [
  { id: "easy", label: "Easy" },
  { id: "moderate", label: "Moderate" },
  { id: "hard", label: "Hard" },
];

type Props = {
  day: string;
  units: Units;
  weightKg: number;
  catalog: Catalog;
  equipment: string[]; // machines at today's gym are listed first
  onSaved: (a: Activity) => void;
  onCancel: () => void;
};

/** Save one activity; with no connection it waits on the phone and shows as typed. */
export async function saveActivity(body: ActivityIn, catalog: Catalog, weightKg: number): Promise<Activity> {
  const name = catalog.activities.find((a) => a.id === body.activity)?.name ?? body.activity;
  const items = body.items.map((i) => catalog.floor_moves.find((m) => m.id === i)?.name ?? i);
  const preview = offlineActivity(body, name, items, weightKg);
  return api<Activity>("/activities", { method: "POST", body: { ...body, preview }, offline: () => preview });
}

export function ActivityForm({ day, units, weightKg, catalog, equipment, onSaved, onCancel }: Props) {
  const [kind, setKind] = useState<string | null>(null);
  const [minutes, setMinutes] = useState("");
  const [speed, setSpeed] = useState("");
  const [incline, setIncline] = useState("");
  const [level, setLevel] = useState("");
  const [distance, setDistance] = useState("");
  const [calories, setCalories] = useState("");
  const [intensity, setIntensity] = useState<Intensity>("moderate");
  const [items, setItems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activity = catalog.activities.find((a) => a.id === kind) ?? null;
  const has = (f: string) => !!activity?.fields.includes(f as never);
  const ordered = (group: ActivityKind["group"]) =>
    catalog.activities
      .filter((a) => a.group === group)
      .sort((a, b) => Number(!!b.equipment && equipment.includes(b.equipment)) - Number(!!a.equipment && equipment.includes(a.equipment)));

  const body: ActivityIn | null = useMemo(() => {
    const m = parsePositive(minutes);
    if (!activity || !m) return null;
    const sp = has("speed") ? parsePositive(speed) : null;
    const di = has("distance") ? parsePositive(distance) : null;
    return {
      id: crypto.randomUUID(),
      day,
      activity: activity.id,
      part: "main",
      minutes: m,
      intensity,
      speed_kmh: sp ? Math.round(toKm(sp, units) * 10) / 10 : null,
      incline_pct: has("incline") ? parsePositive(incline) : null,
      level: has("level") ? (parsePositive(level) ? Math.round(parsePositive(level) as number) : null) : null,
      distance_km: di ? Math.round(toKm(di, units) * 100) / 100 : null,
      calories: parsePositive(calories) ? Math.round(parsePositive(calories) as number) : null,
      items: has("items") ? items : [],
      note: "",
    };
  }, [activity, minutes, speed, incline, level, distance, calories, intensity, items, day, units]);

  const estimate = body ? estimateCalories(body, weightKg) : null;

  async function save() {
    if (!body) return;
    setBusy(true);
    setError(null);
    try {
      onSaved(await saveActivity(body, catalog, weightKg));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const movesFor = (g: FloorMove["group"]) => catalog.floor_moves.filter((m) => m.group === g);
  const moveGroups = kind === "hiit" ? ["hiit", "core", "legs", "upper"] : ["core", "legs", "upper", "stretch", "hiit"];

  return (
    <div className="activity-form">
      <div className="card-head">
        <h3>Log activity</h3>
        <button type="button" className="link small" onClick={onCancel}>
          Cancel
        </button>
      </div>

      {GROUPS.map((g) => (
        <div key={g.id} className="chip-group">
          <span className="hint">{g.label}</span>
          <div className="chips">
            {ordered(g.id).map((a) => (
              <button key={a.id} type="button" className="chip" aria-pressed={kind === a.id} onClick={() => setKind(a.id)}>
                {a.name}
              </button>
            ))}
          </div>
        </div>
      ))}

      {activity && (
        <div className="fields compact">
          <div className="two">
            <label>
              <span className="hint">Minutes</span>
              <input inputMode="decimal" value={minutes} onChange={(e) => setMinutes(e.target.value)} placeholder="e.g. 20" autoFocus />
            </label>
            {has("speed") && (
              <label>
                <span className="hint">Speed ({speedUnit(units)})</span>
                <input inputMode="decimal" value={speed} onChange={(e) => setSpeed(e.target.value)} placeholder="optional" />
              </label>
            )}
            {has("incline") && (
              <label>
                <span className="hint">Incline (%)</span>
                <input inputMode="decimal" value={incline} onChange={(e) => setIncline(e.target.value)} placeholder="optional" />
              </label>
            )}
            {has("level") && (
              <label>
                <span className="hint">Level</span>
                <input inputMode="numeric" value={level} onChange={(e) => setLevel(e.target.value)} placeholder="optional" />
              </label>
            )}
            {has("distance") && (
              <label>
                <span className="hint">Distance ({distanceUnit(units)})</span>
                <input inputMode="decimal" value={distance} onChange={(e) => setDistance(e.target.value)} placeholder="optional" />
              </label>
            )}
            <label>
              <span className="hint">Calories</span>
              <input
                inputMode="numeric"
                value={calories}
                onChange={(e) => setCalories(e.target.value)}
                placeholder={estimate ? `≈ ${estimate}` : "optional"}
              />
            </label>
          </div>

          {has("intensity") && (
            <div className="segmented" role="group" aria-label="How hard">
              {INTENSITY.map((i) => (
                <button key={i.id} type="button" aria-pressed={intensity === i.id} onClick={() => setIntensity(i.id)}>
                  {i.label}
                </button>
              ))}
            </div>
          )}

          {has("items") && (
            <div className="moves">
              <span className="hint">What did you do? Tap all that apply.</span>
              {moveGroups.map((g) => {
                const moves = movesFor(g as FloorMove["group"]);
                if (!moves.length) return null;
                return (
                  <div key={g} className="chip-group">
                    <span className="hint small">{MOVE_GROUPS.find((x) => x.id === g)?.label}</span>
                    <div className="chips">
                      {moves.map((mv) => {
                        const on = items.includes(mv.id);
                        return (
                          <button
                            key={mv.id}
                            type="button"
                            className="chip small-chip"
                            aria-pressed={on}
                            onClick={() => setItems(on ? items.filter((x) => x !== mv.id) : [...items, mv.id])}
                          >
                            {mv.name}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <p className="hint">
            {calories ? "Using the calories you entered." : "No machine number? We'll save an estimate from your weight and effort."}
          </p>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button type="button" className="primary" disabled={!body || busy} onClick={save}>
            {busy ? "Saving…" : `Save ${activity.name.toLowerCase()}`}
          </button>
        </div>
      )}
    </div>
  );
}
