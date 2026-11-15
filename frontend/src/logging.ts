// Pure helpers for logging sets (unit-tested). Weights are stored in kg; the screen
// shows and accepts the user's own units.
import type { LoggedSet, Target, UnitSystem } from "./types";
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

/** Pre-fill the next set: repeat the last logged set, else the target. */
export function nextSetDefaults(target: Target, logged: LoggedSet[], u: UnitSystem): { weight: string; reps: string } {
  const last = logged[logged.length - 1];
  if (last) return { weight: last.weight_kg ? String(toDisplay(last.weight_kg, u)) : "", reps: String(last.reps) };
  return {
    weight: target.weight_kg ? String(toDisplay(target.weight_kg, u)) : "",
    reps: String(target.reps),
  };
}

export function targetLine(t: Target, u: UnitSystem): string {
  if (t.weight_kg === null) return `Aim for ${t.reps}+ reps`;
  return `${formatWeight(t.weight_kg, u)} × ${t.reps}+ reps`;
}

/** Parse the inputs; returns an error message or the values to send. */
export function parseSet(
  weight: string,
  reps: string,
  u: UnitSystem,
): { error: string } | { weight_kg: number; reps: number } {
  const r = Number(reps);
  if (!reps.trim() || !Number.isInteger(r) || r < 0 || r > 100) return { error: "Enter reps as a whole number." };
  const w = weight.trim() === "" ? 0 : Number(weight);
  if (!Number.isFinite(w) || w < 0 || w > (u === "metric" ? 1000 : 2200)) return { error: "Enter a valid weight." };
  return { weight_kg: fromDisplay(w, u), reps: r };
}

export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
