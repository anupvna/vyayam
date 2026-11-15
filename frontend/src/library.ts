// Small pure helpers for the exercise library screens (unit-tested).
import type { ExerciseSummary } from "./types";

export type LibraryFilter = { query: string; muscle: string | null; scope: "all" | "gym" | "favorites" };

/** The picture for an exercise: its first piece of equipment, or the bodyweight figure. */
export function artFor(e: Pick<ExerciseSummary, "equipment">): string {
  const first = e.equipment.find((option) => option.length > 0);
  return first ? first[0] : "bodyweight";
}

export function filterExercises(items: ExerciseSummary[], f: LibraryFilter): ExerciseSummary[] {
  const q = f.query.trim().toLowerCase();
  return items.filter((e) => {
    if (e.preference === "hidden" && f.scope !== "all") return false;
    if (f.scope === "gym" && !e.available) return false;
    if (f.scope === "favorites" && e.preference !== "favorite") return false;
    if (f.muscle && !e.primary.includes(f.muscle) && !e.secondary.includes(f.muscle)) return false;
    if (q && !e.name.toLowerCase().includes(q)) return false;
    return true;
  });
}

/** Favorites first, then exercises you can do at your gym, then alphabetical. */
export function sortExercises(items: ExerciseSummary[]): ExerciseSummary[] {
  return [...items].sort(
    (a, b) =>
      Number(b.preference === "favorite") - Number(a.preference === "favorite") ||
      Number(b.available) - Number(a.available) ||
      a.name.localeCompare(b.name),
  );
}
