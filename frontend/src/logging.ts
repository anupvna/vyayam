// Pure helpers for logging sets (unit-tested). Weights are stored in kg; the screen
// shows and accepts the user's own units.
import type { LastSession, Load, LoggedSet, Target, UnitSystem } from "./types";
import { kgToLb, lbToKg, round1 } from "./units";

export const unitLabel = (u: UnitSystem): string => (u === "metric" ? "kg" : "lb");

/** kg -> number to show, rounded to 0.1 (so 61.235 kg shows as 135 lb). */
export const toDisplay = (kg: number, u: UnitSystem): number => round1(u === "metric" ? kg : kgToLb(kg));

/** What the user typed, in their units -> kg for the API. */
export const fromDisplay = (value: number, u: UnitSystem): number =>
  u === "metric" ? value : Math.round(lbToKg(value) * 1e6) / 1e6;

export function formatWeight(kg: number, u: UnitSystem): string {
  return kg === 0 ? "Bodyweight" : `${toDisplay(kg, u)} ${unitLabel(u)}`;
}

/** Pre-fill the next set: repeat the last logged set, else the target. If last time used a
 * different weight on each set (40, 45, 50) and the target keeps the same weight, set N
 * starts from last time's set N, so a pyramid doesn't have to be retyped. */
export function nextSetDefaults(
  target: Target,
  logged: LoggedSet[],
  u: UnitSystem,
  last?: LastSession | null,
): { weight: string; reps: string } {
  const show = (kg: number) => (kg ? String(toDisplay(kg, u)) : "");
  const before = last?.sets[logged.length];
  const pyramid = !!last && new Set(last.sets.map((s) => s.weight_kg)).size > 1;
  if (pyramid && before && (target.change === "hold" || target.change === "more_reps"))
    return { weight: show(before.weight_kg), reps: String(target.reps) };
  const prev = logged[logged.length - 1];
  if (prev) return { weight: show(prev.weight_kg), reps: String(prev.reps) };
  return { weight: show(target.weight_kg ?? 0), reps: String(target.reps) };
}

export const isBarbell = (load: Load | undefined) => load === "barbell_lower" || load === "barbell_upper";

/** A standard (Olympic) bar. Curl and fixed bars are often lighter, so it's only a hint. */
export const barWeight = (u: UnitSystem): string => (u === "metric" ? "20 kg" : "45 lb");

/** The label above the weight box: dumbbells are per dumbbell, barbells include the bar. */
export function weightHint(load: Load | undefined, u: UnitSystem): string {
  const unit = unitLabel(u);
  if (load === "dumbbell") return `${unit}, each dumbbell`;
  if (isBarbell(load)) return `${unit}, bar included`;
  if (load === null) return `Added ${unit}`;
  return unit;
}

/** "Nov 21: 40 × 16, 45 × 16, 50 × 14 lb", or "Nov 21: 3 sets of 9 reps" */
export function lastLine(last: LastSession, u: UnitSystem): string {
  const date = new Date(`${last.day}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const unit = last.sets.some((s) => s.weight_kg) ? ` ${unitLabel(u)}` : "";
  const one = (s: { weight_kg: number; reps: number }) =>
    s.weight_kg ? `${toDisplay(s.weight_kg, u)} × ${s.reps}` : `${s.reps} reps`;
  const all = last.sets.map(one);
  if (all.length > 1 && all.every((x) => x === all[0])) return `${date}: ${all.length} sets of ${all[0]}${unit}`;
  return `${date}: ${all.join(", ")}${unit}`;
}

/** Sets per exercise: you can change today's number, from what's already logged (at least
 * 1) up to 6, or the plan's number if that's higher. Past about 6 hard sets of one
 * exercise in a session, extra sets add fatigue more than growth. */
export const MAX_SETS = 6;
export function clampSets(wanted: number, planned: number, loggedCount: number): number {
  const lo = Math.max(1, loggedCount);
  const hi = Math.max(MAX_SETS, planned, loggedCount);
  return Math.min(hi, Math.max(lo, Math.round(wanted)));
}

export function targetLine(t: Target, u: UnitSystem, load?: Load): string {
  if (t.weight_kg === null) return `Aim for ${t.reps}+ reps`;
  return `${formatWeight(t.weight_kg, u)}${load === "dumbbell" ? " each" : ""} × ${t.reps}+ reps`;
}

/** Parse the inputs; returns an error message or the values to send. */
export function parseSet(
  weight: string,
  reps: string,
  u: UnitSystem,
  load?: Load,
): { error: string } | { weight_kg: number; reps: number } {
  const r = Number(reps);
  if (!reps.trim() || !Number.isInteger(r) || r < 0 || r > 100) return { error: "Enter reps as a whole number." };
  const w = weight.trim() === "" ? 0 : Number(weight);
  if (!Number.isFinite(w) || w < 0 || w > (u === "metric" ? 1000 : 2200)) return { error: "Enter a valid weight." };
  if (w === 0 && isBarbell(load)) return { error: `Include the bar's weight (a standard bar is ${barWeight(u)}).` };
  return { weight_kg: fromDisplay(w, u), reps: r };
}

export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
