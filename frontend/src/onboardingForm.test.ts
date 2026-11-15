import { describe, expect, it } from "vitest";

import {
  emptyForm,
  fromProfile,
  switchUnit,
  toProfileInput,
  validateStep,
  type FormState,
} from "./onboardingForm";
import type { Profile } from "./types";

const YEAR = 2026;

const filled = (overrides: Partial<FormState> = {}): FormState => ({
  ...emptyForm("metric"),
  birthYear: "2002",
  sex: "male",
  heightCm: "178",
  weight: "80",
  experience: "intermediate",
  goal: "fat_loss",
  targetWeight: "72",
  ...overrides,
});

describe("validateStep", () => {
  it("accepts a complete form", () => {
    for (const step of ["about", "goal", "schedule", "gym"] as const) {
      expect(validateStep(step, filled(), YEAR)).toBeNull();
    }
  });

  it("enforces adults only", () => {
    expect(validateStep("about", filled({ birthYear: "2010" }), YEAR)).toMatch(/adults/);
  });

  it("requires a rest day", () => {
    const sevenDays = filled({ days: [0, 1, 2, 3, 4, 5, 6] });
    expect(validateStep("schedule", sevenDays, YEAR)).toMatch(/rest day/);
  });

  it("validates imperial height and weight ranges", () => {
    const tiny = filled({ unit: "imperial", heightFt: "2", heightIn: "0", weight: "180" });
    expect(validateStep("about", tiny, YEAR)).toMatch(/height/);
  });

  it("allows an empty target but rejects a nonsense one", () => {
    expect(validateStep("goal", filled({ targetWeight: "" }), YEAR)).toBeNull();
    expect(validateStep("goal", filled({ targetWeight: "abc" }), YEAR)).toMatch(/Target weight/);
  });
});

describe("toProfileInput", () => {
  it("converts imperial input to metric for the API", () => {
    const input = toProfileInput(
      filled({ unit: "imperial", heightFt: "5", heightIn: "10", weight: "176", targetWeight: "" }),
    );
    expect(input.height_cm).toBe(177.8);
    expect(input.weight_kg).toBe(79.83);
    expect(input.target_weight_kg).toBeNull();
    expect(input.unit_system).toBe("imperial");
  });

  it("sorts training days", () => {
    expect(toProfileInput(filled({ days: [4, 0, 2] })).training_days).toEqual([0, 2, 4]);
  });
});

describe("unit switching and editing", () => {
  it("keeps values when switching units", () => {
    const imperial = switchUnit(filled(), "imperial");
    expect(imperial.weight).toBe("176.4");
    expect([imperial.heightFt, imperial.heightIn]).toEqual(["5", "10"]);
    const back = switchUnit(imperial, "metric");
    expect(Number(back.weight)).toBeCloseTo(80, 1);
  });

  it("round-trips imperial weights exactly (176 lb stays 176 lb)", () => {
    for (let lb = 100; lb <= 400; lb++) {
      const saved: Profile = {
        ...toProfileInput(filled({ unit: "imperial", heightFt: "5", heightIn: "10",
          weight: String(lb), targetWeight: "" })),
        age: 24,
        bmi: 25,
        advice: [],
      };
      expect(fromProfile(saved).weight).toBe(String(lb));
    }
  });

  it("fills the form from a saved profile", () => {
    const profile: Profile = {
      ...toProfileInput(filled()),
      age: 24,
      bmi: 25.2,
      advice: [],
    };
    const form = fromProfile(profile);
    expect(toProfileInput(form)).toEqual(toProfileInput(filled()));
  });
});
