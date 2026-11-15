import type { Experience, Goal } from "./types";

export const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

/** Today as 0 = Monday ... 6 = Sunday (JavaScript counts from Sunday). */
export const todayIndex = (d = new Date()): number => (d.getDay() + 6) % 7;

export const GOALS: { id: Goal; name: string; blurb: string }[] = [
  { id: "fat_loss", name: "Lose fat", blurb: "Get leaner while keeping your muscle." },
  { id: "muscle_gain", name: "Build muscle", blurb: "Add size, eating a little above maintenance." },
  {
    id: "recomposition",
    name: "Lose fat and build muscle",
    blurb: "Both at once. Slower, and best if you're newer to lifting.",
  },
  { id: "strength", name: "Get stronger", blurb: "Lift heavier on squat, bench, deadlift and press." },
];

export const EXPERIENCE: { id: Experience; name: string; blurb: string }[] = [
  { id: "beginner", name: "Beginner", blurb: "Under a year of regular training." },
  { id: "intermediate", name: "Intermediate", blurb: "One to three years. Comfortable with the main lifts." },
  { id: "advanced", name: "Advanced", blurb: "Three years or more. Progress comes slowly." },
];

export const goalName = (g: Goal): string => GOALS.find((x) => x.id === g)?.name ?? g;
