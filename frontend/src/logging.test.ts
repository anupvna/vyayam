import { describe, expect, it } from "vitest";

import { formatClock, formatWeight, fromDisplay, nextSetDefaults, parseSet, targetLine, toDisplay } from "./logging";
import type { LoggedSet, Target } from "./types";

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
});
