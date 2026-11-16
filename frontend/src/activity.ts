// Activity logging helpers (unit-tested): units, calorie estimates that match the
// backend (engine/cardio.py), and the line shown for each logged activity.
import type { Activity, ActivityIn, Intensity } from "./types";

const KM_PER_MI = 1.609344;
export type Units = "metric" | "imperial";

export const speedUnit = (u: Units) => (u === "metric" ? "km/h" : "mph");
export const distanceUnit = (u: Units) => (u === "metric" ? "km" : "mi");
export const toKm = (v: number, u: Units) => (u === "metric" ? v : v * KM_PER_MI);
export const fromKm = (km: number, u: Units) => Math.round((u === "metric" ? km : km / KM_PER_MI) * 10) / 10;

// MET by intensity (easy, moderate, hard), as in the backend. Speed-based activities
// (treadmill, walk, run) use the ACSM equations instead.
const MET: Record<string, [number, number, number]> = {
  stair_climber: [5.0, 8.8, 10.0],
  bike: [4.0, 6.8, 8.8],
  rower: [4.8, 7.0, 8.5],
  elliptical: [4.5, 5.5, 7.5],
  jump_rope: [8.8, 11.8, 12.3],
  mat_workout: [3.0, 3.8, 5.0],
  hiit: [6.0, 8.0, 10.0],
  stretching: [2.3, 2.5, 3.0],
  cycling: [5.8, 8.0, 10.0],
  swim: [5.8, 8.3, 9.8],
  sport: [4.0, 6.0, 8.0],
};
const DEFAULT_SPEED: Record<string, number> = { walk: 5.0, run: 9.5, treadmill: 5.5 };
const LEVELS: Intensity[] = ["easy", "moderate", "hard"];

export function metFromSpeed(kmh: number, inclinePct = 0): number {
  const s = (kmh * 1000) / 60;
  const g = Math.max(inclinePct, 0) / 100;
  const vo2 = kmh < 8 ? 0.1 * s + 1.8 * s * g + 3.5 : 0.2 * s + 0.9 * s * g + 3.5;
  return vo2 / 3.5;
}

export function estimateCalories(a: Pick<ActivityIn, "activity" | "minutes" | "intensity" | "speed_kmh" | "incline_pct">, weightKg: number): number {
  const met =
    a.activity in MET
      ? MET[a.activity][LEVELS.indexOf(a.intensity)]
      : metFromSpeed(a.speed_kmh ?? DEFAULT_SPEED[a.activity] ?? 5, a.incline_pct ?? 0);
  return Math.round(((met * 3.5 * weightKg) / 200) * a.minutes);
}

/** "30 min · 5.5 km/h · 2% incline · ≈ 232 kcal" */
export function describe(a: Activity, u: Units): string {
  const bits = [`${a.minutes} min`];
  if (a.speed_kmh) bits.push(`${fromKm(a.speed_kmh, u)} ${speedUnit(u)}`);
  if (a.incline_pct) bits.push(`${a.incline_pct}% incline`);
  if (a.level) bits.push(`level ${a.level}`);
  if (a.distance_km) bits.push(`${fromKm(a.distance_km, u)} ${distanceUnit(u)}`);
  bits.push(`${a.calories_estimated ? "≈ " : ""}${a.calories} kcal`);
  return bits.join(" · ");
}

/** What a logged activity looks like before the server has answered (offline). */
export function offlineActivity(body: ActivityIn, name: string, itemNames: string[], weightKg: number): Activity {
  return {
    ...body,
    name,
    calories: body.calories ?? estimateCalories(body, weightKg),
    calories_estimated: body.calories === null,
    item_names: itemNames,
  };
}

export function parsePositive(text: string): number | null {
  const v = Number(text.replace(",", "."));
  return text.trim() !== "" && Number.isFinite(v) && v > 0 ? v : null;
}
