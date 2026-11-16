import { describe as group, expect, it } from "vitest";

import { describe, estimateCalories, fromKm, metFromSpeed, offlineActivity, parsePositive, toKm } from "./activity";
import type { ActivityIn } from "./types";

const base: ActivityIn = {
  id: "a",
  day: "2026-11-16",
  activity: "treadmill",
  part: "main",
  minutes: 30,
  intensity: "moderate",
  speed_kmh: 5,
  incline_pct: 5,
  level: null,
  distance_km: null,
  calories: null,
  items: [],
  note: "",
};

group("activity helpers", () => {
  it("matches the backend's ACSM numbers", () => {
    expect(metFromSpeed(5)).toBeCloseTo(3.381, 2);
    expect(metFromSpeed(5, 5)).toBeCloseTo(5.524, 2);
    expect(metFromSpeed(10)).toBeCloseTo(10.52, 2);
    expect(estimateCalories(base, 80)).toBe(232); // same as the API test
    expect(estimateCalories({ ...base, speed_kmh: 10, incline_pct: 0 }, 70)).toBe(387);
  });

  it("uses MET by intensity for machines", () => {
    const bike = { ...base, activity: "bike", speed_kmh: null, incline_pct: null };
    expect(estimateCalories({ ...bike, intensity: "easy" }, 70)).toBeLessThan(estimateCalories(bike, 70));
  });

  it("converts miles", () => {
    expect(toKm(3, "imperial")).toBeCloseTo(4.828, 3);
    expect(fromKm(4.828, "imperial")).toBe(3);
    expect(fromKm(5, "metric")).toBe(5);
  });

  it("describes a session, marking estimates", () => {
    const a = offlineActivity(base, "Treadmill", [], 80);
    expect(describe(a, "metric")).toBe("30 min · 5 km/h · 5% incline · ≈ 232 kcal");
    const machine = offlineActivity({ ...base, calories: 250 }, "Treadmill", [], 80);
    expect(describe(machine, "imperial")).toBe("30 min · 3.1 mph · 5% incline · 250 kcal");
  });

  it("parses optional numbers", () => {
    expect(parsePositive("5,5")).toBe(5.5);
    expect(parsePositive("")).toBeNull();
    expect(parsePositive("-2")).toBeNull();
  });
});
