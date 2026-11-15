// Onboarding form logic, kept separate from the screens so it can be unit-tested:
// - the form holds what the user typed (strings, in their units)
// - validateStep() checks one wizard step
// - toProfileInput() converts to the metric API shape
// - fromProfile() fills the form back in when editing
import type { Experience, Goal, Profile, ProfileInput, Sex, UnitSystem } from "./types";
import { cmToFtIn, ftInToCm, kgToLb, lbToKg, round1, round2 } from "./units";

export type FormState = {
  unit: UnitSystem;
  birthYear: string;
  sex: Sex | "";
  heightCm: string;
  heightFt: string;
  heightIn: string;
  weight: string; // in kg or lb, per `unit`
  experience: Experience | "";
  goal: Goal | "";
  targetWeight: string; // optional, same unit as weight
  targetBodyFat: string; // optional, %
  days: number[];
  minutes: number;
  injuries: string[];
  injuryNotes: string;
  gymName: string;
  equipment: string[];
};

export type StepId = "about" | "goal" | "schedule" | "gym" | "injuries" | "review";

export const emptyForm = (unit: UnitSystem = "metric"): FormState => ({
  unit,
  birthYear: "",
  sex: "",
  heightCm: "",
  heightFt: "",
  heightIn: "",
  weight: "",
  experience: "",
  goal: "",
  targetWeight: "",
  targetBodyFat: "",
  days: [0, 2, 4],
  minutes: 60,
  injuries: [],
  injuryNotes: "",
  gymName: "My gym",
  equipment: [],
});

const num = (s: string): number | null => {
  const t = s.trim();
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
};

const toKg = (value: number, unit: UnitSystem): number =>
  unit === "metric" ? round1(value) : round2(lbToKg(value));

export function heightCm(f: FormState): number | null {
  if (f.unit === "metric") return num(f.heightCm);
  const ft = num(f.heightFt);
  const inches = num(f.heightIn) ?? 0;
  return ft === null ? null : round1(ftInToCm(ft, inches));
}

export function weightKg(f: FormState): number | null {
  const w = num(f.weight);
  return w === null ? null : toKg(w, f.unit);
}

export function targetWeightKg(f: FormState): number | null {
  const w = num(f.targetWeight);
  return w === null ? null : toKg(w, f.unit);
}

const between = (n: number | null, lo: number, hi: number): boolean =>
  n !== null && n >= lo && n <= hi;

/** Returns an error message for the step, or null if it's complete. */
export function validateStep(step: StepId, f: FormState, thisYear: number): string | null {
  switch (step) {
    case "about": {
      const year = num(f.birthYear);
      if (year === null || !Number.isInteger(year)) return "Enter your birth year.";
      const age = thisYear - year;
      if (age < 18 || age > 90) return "Vyayam is for adults aged 18–90.";
      if (!f.sex) return "Choose sex (used for body-fat formulas).";
      if (!between(heightCm(f), 120, 230)) return "Enter a height between 120 and 230 cm (3'11\"–7'7\").";
      if (!between(weightKg(f), 30, 300)) return "Enter a weight between 30 and 300 kg (66–661 lb).";
      if (!f.experience) return "Choose your experience level.";
      return null;
    }
    case "goal": {
      if (!f.goal) return "Choose a goal.";
      if (f.targetWeight.trim() && !between(targetWeightKg(f), 30, 300))
        return "Target weight must be between 30 and 300 kg (66–661 lb).";
      if (f.targetBodyFat.trim() && !between(num(f.targetBodyFat), 3, 50))
        return "Target body fat must be between 3% and 50%.";
      return null;
    }
    case "schedule":
      if (f.days.length < 1) return "Pick at least one training day.";
      if (f.days.length > 6) return "Keep at least one full rest day each week.";
      return null;
    case "gym":
      return f.gymName.trim() ? null : "Give your gym a name.";
    default:
      return null;
  }
}

export function toProfileInput(f: FormState): ProfileInput {
  const bf = num(f.targetBodyFat);
  return {
    birth_year: Number(f.birthYear),
    sex: f.sex as Sex,
    height_cm: heightCm(f) as number,
    weight_kg: weightKg(f) as number,
    experience: f.experience as Experience,
    goal: f.goal as Goal,
    target_weight_kg: targetWeightKg(f),
    target_body_fat_pct: bf,
    training_days: [...f.days].sort((a, b) => a - b),
    session_minutes: f.minutes,
    injury_areas: f.injuries,
    injury_notes: f.injuryNotes.trim(),
    unit_system: f.unit,
  };
}

const show = (kg: number, unit: UnitSystem): string =>
  String(round1(unit === "metric" ? kg : kgToLb(kg)));

export function fromProfile(p: Profile): FormState {
  const { ft, inches } = cmToFtIn(p.height_cm);
  return {
    ...emptyForm(p.unit_system),
    birthYear: String(p.birth_year),
    sex: p.sex,
    heightCm: String(p.height_cm),
    heightFt: String(ft),
    heightIn: String(inches),
    weight: show(p.weight_kg, p.unit_system),
    experience: p.experience,
    goal: p.goal,
    targetWeight: p.target_weight_kg === null ? "" : show(p.target_weight_kg, p.unit_system),
    targetBodyFat: p.target_body_fat_pct === null ? "" : String(p.target_body_fat_pct),
    days: p.training_days,
    minutes: p.session_minutes,
    injuries: p.injury_areas,
    injuryNotes: p.injury_notes,
  };
}

/** Switch units, converting what's already typed so nothing is lost. */
export function switchUnit(f: FormState, unit: UnitSystem): FormState {
  if (unit === f.unit) return f;
  const h = heightCm(f);
  const w = weightKg(f);
  const t = targetWeightKg(f);
  const { ft, inches } = h === null ? { ft: NaN, inches: NaN } : cmToFtIn(h);
  return {
    ...f,
    unit,
    heightCm: h === null ? "" : String(h),
    heightFt: h === null ? "" : String(ft),
    heightIn: h === null ? "" : String(inches),
    weight: w === null ? "" : show(w, unit),
    targetWeight: t === null ? "" : show(t, unit),
  };
}
