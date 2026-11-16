import { describe, expect, it } from "vitest";

import { OFFLINE_CHECKIN_NOTE, applyPending, isQueueable, merge, offlineAssessment, offlineSet } from "./queue";
import type { OutboxItem } from "./store";
import type { Activity, TrainingToday } from "../types";

const item = (seq: number, method: OutboxItem["method"], path: string, body?: unknown): OutboxItem => ({
  seq,
  userId: "u",
  method,
  path,
  body,
  createdAt: 0,
});

const set = (id: string, exercise_id = "bench_press", set_index = 1, day = "2026-11-16") => ({
  id,
  day,
  exercise_id,
  set_index,
  weight_kg: 60,
  reps: 8,
  rir: 2,
});

describe("isQueueable", () => {
  it("allows changes that are safe to send late or twice", () => {
    expect(isQueueable("POST", "/logs")).toBe(true);
    expect(isQueueable("DELETE", "/logs/3f1c-aa")).toBe(true);
    expect(isQueueable("POST", "/readiness")).toBe(true);
    expect(isQueueable("PUT", "/body/weights/2026-11-16")).toBe(true);
    expect(isQueueable("PUT", "/body/measurements/2026-11-16")).toBe(true);
    expect(isQueueable("PUT", "/exercises/bench_press/preference")).toBe(true);
  });

  it("refuses changes that need the server to decide", () => {
    expect(isQueueable("POST", "/plan/days/2026-11-16/skip")).toBe(false);
    expect(isQueueable("PUT", "/profile")).toBe(false);
    expect(isQueueable("POST", "/gyms")).toBe(false);
    expect(isQueueable("POST", "/auth/logout")).toBe(false);
    expect(isQueueable("GET", "/logs")).toBe(false);
  });
});

describe("merge", () => {
  it("forgets a set and its undo when the set never reached the server", () => {
    const pending = [item(1, "POST", "/logs", set("a")), item(2, "POST", "/logs", set("b"))];
    expect(merge(pending, item(0, "DELETE", "/logs/a"))).toEqual({ remove: [1], add: null });
  });

  it("queues an undo for a set the server already has", () => {
    const next = item(0, "DELETE", "/logs/old");
    expect(merge([item(1, "POST", "/logs", set("a"))], next)).toEqual({ remove: [], add: next });
  });

  it("keeps only the latest weigh-in for a day", () => {
    const pending = [item(1, "PUT", "/body/weights/2026-11-16", { weight_kg: 80 }), item(2, "PUT", "/body/weights/2026-11-15", {})];
    const next = item(0, "PUT", "/body/weights/2026-11-16", { weight_kg: 79.5 });
    expect(merge(pending, next)).toEqual({ remove: [1], add: next });
  });

  it("keeps only the latest check-in for a day", () => {
    const pending = [item(1, "POST", "/readiness", { today: "2026-11-16" }), item(2, "POST", "/readiness", { today: "2026-11-15" })];
    const next = item(0, "POST", "/readiness", { today: "2026-11-16" });
    expect(merge(pending, next).remove).toEqual([1]);
  });

  it("never merges new sets", () => {
    const next = item(0, "POST", "/logs", set("b"));
    expect(merge([item(1, "POST", "/logs", set("a"))], next)).toEqual({ remove: [], add: next });
  });
});

describe("offline answers", () => {
  it("shows a set as typed, with its estimated max but no record yet", () => {
    expect(offlineSet(set("a"))).toMatchObject({ id: "a", e1rm: 76, pr: false, note: "" });
    expect(offlineSet({ ...set("a"), reps: 15 }).e1rm).toBeNull();
    expect(offlineSet({ ...set("a"), weight_kg: 0 }).e1rm).toBeNull();
  });

  it("still stops training on red flags with no connection", () => {
    const a = offlineAssessment({ red_flags: ["chest_pain"] });
    expect(a.verdict).toBe("stop");
    expect(a.messages[0]).toMatch(/emergency/);
  });

  it("otherwise says the advice comes after syncing", () => {
    expect(offlineAssessment({ sore_areas: ["legs"] })).toMatchObject({
      verdict: "normal",
      messages: [OFFLINE_CHECKIN_NOTE],
      sore_areas: ["legs"],
    });
  });
});

describe("applyPending", () => {
  const today: TrainingToday = {
    day: { logged_sets: 1 } as TrainingToday["day"],
    stop: false,
    suggest_rest: false,
    deload: false,
    readiness: null,
    exercises: [
      { exercise_id: "bench_press", target: {} as never, logged: [offlineSet({ ...set("s1"), set_index: 1 })] },
      { exercise_id: "back_squat", target: {} as never, logged: [] },
    ],
  };
  const path = "/training/today?today=2026-11-16";

  it("adds waiting sets to the right exercise, in order", () => {
    const pending = [item(1, "POST", "/logs", set("s3", "bench_press", 3)), item(2, "POST", "/logs", set("s2", "bench_press", 2)), item(3, "POST", "/logs", set("q1", "back_squat"))];
    const out = applyPending(path, today, pending);
    expect(out.exercises[0].logged.map((s) => s.id)).toEqual(["s1", "s2", "s3"]);
    expect(out.exercises[1].logged.map((s) => s.id)).toEqual(["q1"]);
    expect(out.day.logged_sets).toBe(4);
  });

  it("ignores sets for another day and sets the server already has", () => {
    const pending = [item(1, "POST", "/logs", set("x", "bench_press", 2, "2026-11-15")), item(2, "POST", "/logs", set("s1"))];
    expect(applyPending(path, today, pending).exercises[0].logged).toHaveLength(1);
  });

  it("hides sets whose undo is waiting", () => {
    expect(applyPending(path, today, [item(1, "DELETE", "/logs/s1")]).exercises[0].logged).toEqual([]);
  });

  it("shows a waiting check-in, and red flags stop the workout", () => {
    const out = applyPending(path, today, [item(1, "POST", "/readiness", { today: "2026-11-16", red_flags: ["dizziness"] })]);
    expect(out.readiness?.verdict).toBe("stop");
    expect(out.stop).toBe(true);
  });

  it("leaves other screens alone", () => {
    const data = { weights: [] };
    expect(applyPending("/body/summary?today=2026-11-16", data, [item(1, "POST", "/logs", set("a"))])).toBe(data);
  });
});

describe("activities offline", () => {
  const preview = (id: string, day = "2026-11-16", part = "main", minutes = 20, activity = "treadmill") => ({
    id, day, part, minutes, activity, name: "Treadmill", intensity: "moderate", speed_kmh: null, incline_pct: null,
    level: null, distance_km: null, calories: 100, calories_estimated: true, items: [], item_names: [], note: "",
  });
  const post = (seq: number, p: ReturnType<typeof preview>) => item(seq, "POST", "/activities", { id: p.id, day: p.day, preview: p });

  it("queues activity logs and undo", () => {
    expect(isQueueable("POST", "/activities")).toBe(true);
    expect(isQueueable("DELETE", "/activities/abc-1")).toBe(true);
    expect(merge([post(1, preview("x"))], item(0, "DELETE", "/activities/x"))).toEqual({ remove: [1], add: null });
  });

  it("shows waiting activities on today's card and ticks the warm-up", () => {
    const today = {
      warmup: { activity: "treadmill", minutes: 5, text: "", done: false },
      finisher: null, cooldown: [], cooldown_minutes: 0, rest_day: null, activities: [] as Activity[], week_target: 150, week_done: 10,
    };
    const out = applyPending("/activities/today?today=2026-11-16", today, [
      post(1, preview("w", "2026-11-16", "warmup", 5)),
      post(2, preview("other-day", "2026-11-15")),
    ]);
    expect(out.activities.map((a) => a.id)).toEqual(["w"]);
    expect(out.warmup?.done).toBe(true);
    expect(out.week_done).toBe(15);
  });

  it("adds waiting minutes to the week, not stretching", () => {
    const week = {
      level: "regular", chosen: null, target_minutes: 150, done_minutes: 0, activities: [] as Activity[],
      days: ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22"].map((date) => ({ date, minutes: 0 })),
    };
    const out = applyPending("/activities/week?today=2026-11-18", week, [
      post(1, preview("a", "2026-11-16", "main", 30)),
      post(2, preview("s", "2026-11-17", "main", 10, "stretching")),
      post(3, preview("next-week", "2026-11-23")),
    ]);
    expect(out.done_minutes).toBe(30);
    expect(out.days[0].minutes).toBe(30);
    expect(out.activities).toHaveLength(2);
  });
});
