// Pure helpers for the plan screens (unit-tested).
import type { PlannedExercise } from "./types";

/** Today's date in the user's own time zone, as YYYY-MM-DD. */
export function localISO(d: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Parse YYYY-MM-DD as a local date (not UTC, which can shift the day). */
export function parseISO(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatRest(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s ? `${m}:${String(s).padStart(2, "0")}` : `${m} min`;
}

export function formatSets(e: Pick<PlannedExercise, "sets" | "reps">): string {
  const [lo, hi] = e.reps;
  return `${e.sets} × ${lo === hi ? lo : `${lo}–${hi}`}`;
}

/** Plain-language effort target from "reps in reserve". */
export function effortLabel(rir: number): string {
  if (rir >= 4) return "Easy: stop well before it gets hard";
  if (rir === 1) return "Hard: stop 1 rep before failure";
  return `Stop ${rir} reps before failure`;
}

export const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
export const WEEKDAY_FULL = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
