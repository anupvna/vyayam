import { describe, expect, it } from "vitest";

import { artFor, filterExercises, sortExercises } from "./library";
import type { ExerciseSummary } from "./types";

const ex = (over: Partial<ExerciseSummary>): ExerciseSummary => ({
  id: "x",
  name: "X",
  pattern: "squat",
  kind: "accessory",
  primary: ["quads"],
  secondary: [],
  equipment: [[]],
  difficulty: 1,
  unilateral: false,
  available: true,
  safe: true,
  preference: "none",
  ...over,
});

const items = [
  ex({ id: "squat", name: "Back squat", primary: ["quads", "glutes"], equipment: [["barbell", "squat_rack"]] }),
  ex({ id: "press", name: "Leg press", available: false, equipment: [["leg_press"]] }),
  ex({ id: "curl", name: "Curl", primary: ["biceps"], preference: "favorite" }),
  ex({ id: "dip", name: "Dip", primary: ["chest"], secondary: ["triceps"], preference: "hidden" }),
];

describe("library helpers", () => {
  it("picks equipment art, or the bodyweight figure", () => {
    expect(artFor(items[0])).toBe("barbell");
    expect(artFor(ex({ equipment: [[], ["dumbbells"]] }))).toBe("dumbbells");
    expect(artFor(ex({ equipment: [[]] }))).toBe("bodyweight");
  });

  it("filters by search, muscle and scope", () => {
    const base = { query: "", muscle: null, scope: "all" as const };
    expect(filterExercises(items, { ...base, query: "PRESS" }).map((e) => e.id)).toEqual(["press"]);
    expect(filterExercises(items, { ...base, muscle: "triceps" }).map((e) => e.id)).toEqual(["dip"]);
    expect(filterExercises(items, { ...base, scope: "gym" }).map((e) => e.id)).toEqual(["squat", "curl"]);
    expect(filterExercises(items, { ...base, scope: "favorites" }).map((e) => e.id)).toEqual(["curl"]);
  });

  it("shows hidden exercises only under All", () => {
    const base = { query: "", muscle: null };
    expect(filterExercises(items, { ...base, scope: "all" }).some((e) => e.id === "dip")).toBe(true);
    expect(filterExercises(items, { ...base, scope: "gym" }).some((e) => e.id === "dip")).toBe(false);
  });

  it("sorts favorites, then available, then by name", () => {
    expect(sortExercises(items).map((e) => e.id)).toEqual(["curl", "squat", "dip", "press"]);
  });
});
