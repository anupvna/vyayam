import { describe, expect, it } from "vitest";

import {
  clampSets,
  formatClock,
  formatWeight,
  fromDisplay,
  lastLine,
  nextSetDefaults,
  parseSet,
  targetLine,
  toDisplay,
  weightHint,
} from "./logging";
import type { LastSession, LoggedSet, Target } from "./types";

const target: Target = { weight_kg: 61.234964, reps: 6, reason: "", change: "increase" };
const logged = (w: number, r: number): LoggedSet => ({
  id: "x", day: "2026-11-16", exercise_id: "bench_press", set_index: 1, weight_kg: w, reps: r,
  rir: 2, note: "", e1rm: null, pr: false,
});

describe("logging helpers", () => {
  it("shows plate-rounded imperial weights cleanly", () => {
    expect(toDisplay(61.234964, "imperial")).toBe(135);
    expect(formatWeight(61.234964, "imperial")).toBe("135 lb");
    expect(formatWeight(0, "metric")).toBe("Bodyweight");
    expect(Math.round(toDisplay(fromDisplay(135, "imperial"), "imperial"))).toBe(135);
  });

  it("pre-fills from the last set, else the target", () => {
    expect(nextSetDefaults(target, [], "imperial")).toEqual({ weight: "135", reps: "6" });
    expect(nextSetDefaults(target, [logged(60, 8)], "metric")).toEqual({ weight: "60", reps: "8" });
    expect(nextSetDefaults({ ...target, weight_kg: null }, [], "metric")).toEqual({ weight: "", reps: "6" });
  });

  it("describes targets", () => {
    expect(targetLine(target, "imperial")).toBe("135 lb × 6+ reps");
    expect(targetLine({ ...target, weight_kg: null, reps: 12 }, "metric")).toBe("Aim for 12+ reps");
  });

  it("validates input", () => {
    expect(parseSet("60", "8", "metric")).toEqual({ weight_kg: 60, reps: 8 });
    expect(parseSet("", "12", "metric")).toEqual({ weight_kg: 0, reps: 12 }); // bodyweight
    expect(parseSet("60", "", "metric")).toHaveProperty("error");
    expect(parseSet("60", "7.5", "metric")).toHaveProperty("error");
    expect(parseSet("abc", "8", "metric")).toHaveProperty("error");
  });

  it("formats the rest clock", () => {
    expect(formatClock(150)).toBe("2:30");
    expect(formatClock(-3)).toBe("0:00");
  });

  it("starts each set of a pyramid from last time's matching set", () => {
    const lb = (x: number) => fromDisplay(x, "imperial");
    const last: LastSession = { day: "2026-11-21", sets: [40, 45, 50].map((w) => ({ weight_kg: lb(w), reps: 16 })) };
    const hold: Target = { weight_kg: lb(50), reps: 16, reason: "", change: "more_reps" };
    expect(nextSetDefaults(hold, [], "imperial", last)).toEqual({ weight: "40", reps: "16" });
    expect(nextSetDefaults(hold, [logged(lb(40), 16)], "imperial", last)).toEqual({ weight: "45", reps: "16" });
    // A fourth set (more than last time) repeats the set just done.
    const three = [40, 45, 50].map((w) => logged(lb(w), 16));
    expect(nextSetDefaults(hold, three, "imperial", last)).toEqual({ weight: "50", reps: "16" });
    // When the target adds weight, it's the starting point instead.
    expect(nextSetDefaults({ ...hold, weight_kg: lb(55), change: "increase" }, [], "imperial", last).weight).toBe("55");
    // Same weight on every set last time: the usual pre-fill.
    const flat: LastSession = { day: "2026-11-21", sets: [{ weight_kg: 60, reps: 8 }, { weight_kg: 60, reps: 8 }] };
    expect(nextSetDefaults(target, [], "metric", flat).weight).toBe("61.2");
  });

  it("labels weights so dumbbells and the bar are clear", () => {
    expect(weightHint("dumbbell", "imperial")).toBe("lb, each dumbbell");
    expect(weightHint("barbell_upper", "metric")).toBe("kg, bar included");
    expect(weightHint(null, "metric")).toBe("Added kg");
    expect(targetLine({ ...target, weight_kg: 20 }, "metric", "dumbbell")).toBe("20 kg each × 6+ reps");
    expect(parseSet("", "8", "metric", "barbell_lower")).toEqual({ error: "Include the bar's weight (a standard bar is 20 kg)." });
    expect(parseSet("0", "8", "imperial", "barbell_upper")).toHaveProperty("error");
    expect(parseSet("", "8", "metric", null)).toEqual({ weight_kg: 0, reps: 8 });
  });

  it("shows last time set by set", () => {
    const last: LastSession = { day: "2026-11-21", sets: [{ weight_kg: 20, reps: 10 }, { weight_kg: 22.5, reps: 8 }] };
    expect(lastLine(last, "metric")).toBe("Nov 21: 20 × 10, 22.5 × 8 kg");
    expect(lastLine({ day: "2026-11-21", sets: [{ weight_kg: 0, reps: 15 }] }, "metric")).toBe("Nov 21: 15 reps");
    const same = Array(3).fill({ weight_kg: 0, reps: 9 });
    expect(lastLine({ day: "2026-11-19", sets: same }, "metric")).toBe("Nov 19: 3 sets of 9 reps");
    const flat = Array(3).fill({ weight_kg: 60, reps: 8 });
    expect(lastLine({ day: "2026-11-19", sets: flat }, "metric")).toBe("Nov 19: 3 sets of 60 × 8 kg");
  });

  it("keeps today's set count sensible", () => {
    expect(clampSets(4, 3, 0)).toBe(4);
    expect(clampSets(20, 3, 0)).toBe(6);
    expect(clampSets(0, 3, 0)).toBe(1);
    expect(clampSets(1, 3, 2)).toBe(2); // can't go below what's already logged
    expect(clampSets(8, 8, 0)).toBe(8); // a plan with more stays allowed
  });
});
