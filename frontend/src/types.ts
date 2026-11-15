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

export type PlannedExercise = {
  exercise_id: string;
  name: string;
  kind: "main" | "accessory";
  primary: string[];
  sets: number;
  reps: [number, number];
  rir: number; // reps in reserve: how many more reps you could do at the end of a set
  rest_seconds: number;
  light: boolean;
};

export type PlanDay = {
  date: string; // YYYY-MM-DD
  status: "rest" | "planned" | "skipped";
  session_key: string | null;
  session_name: string | null;
  focus: string[];
  minutes: number;
  exercises: PlannedExercise[];
  notes: string[];
  swapped: boolean;
  moved: boolean;
};

export type SplitSession = { key: string; name: string; focus: string[] };

export type Split = {
  id: string;
  name: string;
  blurb: string;
  designed_for: number[];
  sessions: SplitSession[];
  fit_note: string | null;
};

export type Splits = { recommended: string; reason: string; current: string | null; splits: Split[] };

export type Week = {
  start: string;
  week_index: number;
  deload: boolean;
  notes: string[];
  split: Split;
  days: PlanDay[];
};
