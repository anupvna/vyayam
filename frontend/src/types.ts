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
  activities: ActivityKind[];
  floor_moves: FloorMove[];
  cardio_levels: CardioLevelInfo[];
};

export type ActivityField = "speed" | "incline" | "level" | "distance" | "intensity" | "items";
export type ActivityKind = {
  id: string;
  name: string;
  group: "machine" | "outdoor" | "floor" | "other";
  fields: ActivityField[];
  equipment: string | null;
};
export type FloorMove = { id: string; name: string; group: "core" | "legs" | "upper" | "hiit" | "stretch" };
export type CardioLevel = "none" | "light" | "regular" | "lots";
export type CardioLevelInfo = { id: CardioLevel; name: string; minutes: number };
export type Intensity = "easy" | "moderate" | "hard";
export type ActivityPart = "warmup" | "main" | "finisher" | "cooldown";

export type ActivityIn = {
  id: string;
  day: string;
  activity: string;
  part: ActivityPart;
  minutes: number;
  intensity: Intensity;
  speed_kmh: number | null;
  incline_pct: number | null;
  level: number | null;
  distance_km: number | null;
  calories: number | null;
  items: string[];
  note: string;
};
export type Activity = Omit<ActivityIn, "note"> & {
  name: string;
  note: string;
  calories: number;
  calories_estimated: boolean;
  item_names: string[];
};
export type Suggestion = { activity: string; minutes: number; text: string; done: boolean };
export type Stretch = { id: string; name: string; seconds: number; each_side: boolean; how: string };
export type ActivityToday = {
  warmup: Suggestion | null;
  finisher: Suggestion | null;
  cooldown: Stretch[];
  cooldown_minutes: number;
  rest_day: string | null;
  activities: Activity[];
  week_target: number;
  week_done: number;
};
export type ActivityWeek = {
  level: CardioLevel;
  chosen: CardioLevel | null;
  target_minutes: number;
  done_minutes: number;
  days: { date: string; minutes: number }[];
  activities: Activity[];
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
  logged_sets?: number;
  place?: string | null; // e.g. "home (mat only)" when not at the usual gym
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

export type Target = {
  weight_kg: number | null;
  reps: number;
  reason: string;
  change: "first" | "increase" | "hold" | "more_reps" | "reduce" | "light" | "deload";
};

export type LoggedSet = {
  id: string;
  day: string;
  exercise_id: string;
  set_index: number;
  weight_kg: number;
  reps: number;
  rir: number | null;
  note: string;
  e1rm: number | null;
  pr: boolean;
};

export type Assessment = {
  verdict: "stop" | "rest" | "lighter" | "normal";
  score: number;
  messages: string[];
  avoid_areas: string[];
  sore_areas: string[];
};

export type TrainingToday = {
  day: PlanDay & { logged_sets: number };
  stop: boolean;
  suggest_rest: boolean;
  deload: boolean;
  readiness: Assessment | null;
  exercises: { exercise_id: string; target: Target; logged: LoggedSet[] }[];
};

export type WeightPoint = { day: string; weight_kg: number; trend_kg: number };
export type FatPoint = { day: string; pct: number; method: string };
export type Measurement = {
  day: string;
  neck_cm: number | null;
  waist_cm: number | null;
  hips_cm: number | null;
  chest_cm: number | null;
  arm_cm: number | null;
  thigh_cm: number | null;
  body_fat_pct: number | null;
  body_fat_source: string | null;
};
export type ProjectionInfo = {
  status: "reached" | "on_track" | "wrong_way" | "flat" | "not_enough_data";
  message: string;
  earliest: string | null;
  latest: string | null;
  target: number;
  unit: "kg" | "%";
};
export type BodySummary = {
  weights: WeightPoint[];
  latest_weight_kg: number | null;
  trend_kg: number | null;
  rate_kg_per_week: number | null;
  bmi: number | null;
  bmi_note: string;
  body_fat: FatPoint[];
  measurements: Measurement[];
  weight_projection: ProjectionInfo | null;
  body_fat_projection: ProjectionInfo | null;
  advice: string[];
};

export type VolumeStats = {
  weeks: string[];
  muscles: { muscle: string; weekly: number[]; target_low: number; target_high: number }[];
  push_sets: number;
  pull_sets: number;
};
export type CalendarDay = { day: string; status: "done" | "missed" | "skipped" | "rest" | "upcoming" };
export type RecoveryState = "fresh" | "recovering" | "fatigued";
export type MuscleRecovery = { muscle: string; state: RecoveryState; last_trained: string | null };
export type WeeklySummary = {
  week_start: string;
  sessions_done: number;
  sessions_planned: number;
  sets: number;
  sets_last_week: number;
  prs: string[];
  under_target: string[];
  weight_change_kg: number | null;
  lines: string[];
};
export type LoggedExercise = { exercise_id: string; name: string; sessions: number; best_e1rm: number | null; last_day: string };
export type HistoryPoint = { day: string; best_e1rm: number | null; top_weight_kg: number; total_reps: number; pr: boolean };

export type CoachAction = { index: number; type: string; label: string; applied: boolean };
export type CoachMessage = {
  id: string;
  role: "user" | "coach";
  text: string;
  actions: CoachAction[];
  source: "groq" | "gemini" | "engine" | "safety" | null;
  created_at: string;
};
