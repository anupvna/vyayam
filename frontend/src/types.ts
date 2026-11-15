// Shapes of the data the API sends and receives. Kept in one file so the backend's
// Pydantic models and these types are easy to compare side by side.

export type Sex = "male" | "female";
export type Experience = "beginner" | "intermediate" | "advanced";
export type Goal = "fat_loss" | "muscle_gain" | "recomposition" | "strength";
export type UnitSystem = "metric" | "imperial";

export type ProfileInput = {
  birth_year: number;
  sex: Sex;
  height_cm: number;
  weight_kg: number;
  experience: Experience;
  goal: Goal;
  target_weight_kg: number | null;
  target_body_fat_pct: number | null;
  training_days: number[]; // 0 = Monday ... 6 = Sunday
  session_minutes: number;
  injury_areas: string[];
  injury_notes: string;
  unit_system: UnitSystem;
};

export type Advice = { code: string; level: "info" | "warning"; message: string };

export type Profile = ProfileInput & { age: number; bmi: number; advice: Advice[] };

export type CatalogItem = { id: string; name: string };
export type Equipment = CatalogItem & { category: string };
export type Preset = CatalogItem & { description: string; equipment: string[] };

export type Catalog = {
  categories: CatalogItem[];
  equipment: Equipment[];
  presets: Preset[];
  body_parts: CatalogItem[];
  muscles: CatalogItem[];
  patterns: CatalogItem[];
};

export type Gym = { id: string; name: string; equipment: string[]; is_active: boolean };

export type Preference = "favorite" | "hidden" | "none";

export type ExerciseSummary = {
  id: string;
  name: string;
  pattern: string;
  kind: "main" | "accessory";
  primary: string[];
  secondary: string[];
  equipment: string[][]; // any one of these sets is enough; [] = bodyweight
  difficulty: number;
  unilateral: boolean;
  available: boolean;
  safe: boolean;
  preference: Preference;
};

export type ExerciseDetail = ExerciseSummary & {
  loads: string[];
  injury_conflicts: string[];
  setup: string[];
  execution: string[];
  breathing: string;
  mistakes: string[];
  safety: string;
  alternatives: ExerciseSummary[];
};
