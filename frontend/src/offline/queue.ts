// Pure rules for offline changes (unit-tested):
// - which changes may wait in the outbox (only ones that are safe to send late and twice)
// - how a new change merges with ones already waiting
// - how waiting changes show on screens loaded from the saved copy
// - the stand-in answers shown until the server replies
import type { Method, OutboxItem } from "./store";
import type { Activity, ActivityToday, ActivityWeek, Assessment, LoggedSet, TrainingToday } from "../types";

const DAY = String.raw`\d{4}-\d{2}-\d{2}`;
const QUEUEABLE: [Method, RegExp][] = [
  ["POST", /^\/logs$/], // each set carries its own id, so a resend is ignored
  ["DELETE", /^\/logs\/[\w-]+$/],
  ["POST", /^\/readiness$/], // one check-in per day, a resend overwrites it
  ["PUT", new RegExp(`^/body/(weights|measurements)/${DAY}$`)],
  ["DELETE", new RegExp(`^/body/(weights|measurements)/${DAY}$`)],
  ["PUT", /^\/exercises\/[\w-]+\/preference$/],
  ["POST", /^\/activities$/], // cardio and floor work: also carry their own id
  ["DELETE", /^\/activities\/[\w-]+$/],
];

export function isQueueable(method: string, path: string): method is Method {
  return QUEUEABLE.some(([m, re]) => m === method && re.test(path));
}

const bodyOf = (i: OutboxItem) => (i.body ?? {}) as Record<string, unknown>;

/** Merge a new change into the waiting list: which waiting items to drop, and whether to add the new one. */
export function merge(pending: OutboxItem[], next: OutboxItem): { remove: number[]; add: OutboxItem | null } {
  const seqs = (pred: (i: OutboxItem) => boolean) => pending.filter(pred).map((i) => i.seq as number);

  const logDelete = /^\/(logs|activities)\/([\w-]+)$/.exec(next.path);
  if (next.method === "DELETE" && logDelete) {
    // Undoing a set (or activity) that never reached the server: just forget both.
    const created = `/${logDelete[1]}`;
    const unsent = seqs((i) => i.method === "POST" && i.path === created && bodyOf(i).id === logDelete[2]);
    if (unsent.length) return { remove: unsent, add: null };
    return { remove: [], add: next };
  }
  if (next.path === "/readiness") {
    const day = bodyOf(next).today;
    return { remove: seqs((i) => i.path === "/readiness" && bodyOf(i).today === day), add: next };
  }
  if (next.method === "PUT" || next.method === "DELETE") {
    // Only the latest value for the same thing matters.
    return { remove: seqs((i) => i.path === next.path), add: next };
  }
  return { remove: [], add: next };
}

/** Estimated 1-rep max (Epley), the same rule as the server: sets of 12 reps or fewer. */
function e1rm(weight: number, reps: number): number | null {
  if (weight <= 0 || reps < 1 || reps > 12) return null;
  return Math.round(weight * (1 + reps / 30) * 10) / 10;
}

type NewSet = { id: string; day: string; exercise_id: string; set_index: number; weight_kg: number; reps: number; rir?: number | null; note?: string };

/** What a set looks like before the server has seen it (records are worked out after it syncs). */
export function offlineSet(b: NewSet): LoggedSet {
  return { ...b, rir: b.rir ?? null, note: b.note ?? "", e1rm: e1rm(b.weight_kg, b.reps), pr: false };
}

// Same wording as the server's safety layer (backend/app/engine/readiness.py STOP_MESSAGE).
// Red flags must stop training even with no connection.
const STOP_MESSAGE =
  "These symptoms can be a sign of a medical problem. " +
  "If you have chest pain, fainted, or are struggling to breathe, call emergency " +
  "services (911 in the US) now. Otherwise, see a doctor before you train again.";

export const OFFLINE_CHECKIN_NOTE =
  "You're offline, so your check-in is saved on this phone. Your workout adjusts to it once it syncs.";

type CheckInBody = { sore_areas?: string[]; pain_areas?: string[]; red_flags?: string[] };

export function offlineAssessment(b: CheckInBody): Assessment {
  const sore = b.sore_areas ?? [];
  if (b.red_flags?.length) {
    return { verdict: "stop", score: 0, messages: [STOP_MESSAGE], avoid_areas: b.pain_areas ?? [], sore_areas: sore };
  }
  return { verdict: "normal", score: 0, messages: [OFFLINE_CHECKIN_NOTE], avoid_areas: b.pain_areas ?? [], sore_areas: sore };
}

/** Show waiting changes on top of a screen's data (saved copy or fresh), so nothing seems lost. */
export function applyPending<T>(path: string, data: T, pending: OutboxItem[]): T {
  if (!pending.length) return data;
  if (path.startsWith("/activities/today") || path.startsWith("/activities/week")) return applyActivities(path, data, pending);
  if (!path.startsWith("/training/today")) return data;
  const day = new URLSearchParams(path.split("?")[1] ?? "").get("today");
  const t = data as unknown as TrainingToday;
  const added = pending.filter((i) => i.method === "POST" && i.path === "/logs" && bodyOf(i).day === day);
  const deleted = new Set(
    pending.filter((i) => i.method === "DELETE" && i.path.startsWith("/logs/")).map((i) => i.path.slice("/logs/".length)),
  );
  const checkIn = pending.filter((i) => i.path === "/readiness" && bodyOf(i).today === day).pop();

  const exercises = t.exercises.map((x) => {
    const mine = added.map((i) => bodyOf(i) as NewSet).filter((b) => b.exercise_id === x.exercise_id);
    const known = new Set(x.logged.map((s) => s.id));
    const logged = [...x.logged, ...mine.filter((b) => !known.has(b.id)).map(offlineSet)]
      .filter((s) => !deleted.has(s.id))
      .sort((a, b) => a.set_index - b.set_index);
    return { ...x, logged };
  });
  const count = exercises.reduce((n, x) => n + x.logged.length, 0);
  const readiness = checkIn ? offlineAssessment(bodyOf(checkIn) as CheckInBody) : t.readiness;
  return {
    ...t,
    exercises,
    day: { ...t.day, logged_sets: count },
    readiness,
    stop: t.stop || readiness?.verdict === "stop",
  } as unknown as T;
}

// Cardio and floor work waiting to sync. Each queued body carries a `preview` (how it
// shows on screen); the server ignores that field.
type Preview = Activity & { preview?: Activity };
// Same rule as the server: stretching and mat (floor strength) work are logged, not cardio.
const cardioMinutes = (a: Activity) =>
  a.activity !== "stretching" && a.activity !== "mat_workout" && a.part !== "cooldown" ? a.minutes : 0;

function applyActivities<T>(path: string, data: T, pending: OutboxItem[]): T {
  const day = new URLSearchParams(path.split("?")[1] ?? "").get("today") ?? "";
  const weekly = path.startsWith("/activities/week");
  const inRange = (d: string) => (weekly ? d >= mondayOf(day) && d <= addDays(mondayOf(day), 6) : d === day);
  const added = pending
    .filter((i) => i.method === "POST" && i.path === "/activities")
    .map((i) => (bodyOf(i) as Preview).preview)
    .filter((a): a is Activity => !!a && inRange(a.day));
  const deleted = new Set(
    pending.filter((i) => i.method === "DELETE" && i.path.startsWith("/activities/")).map((i) => i.path.slice("/activities/".length)),
  );
  if (weekly) {
    const w = data as unknown as ActivityWeek;
    const known = new Set(w.activities.map((a) => a.id));
    const activities = [...w.activities, ...added.filter((a) => !known.has(a.id))].filter((a) => !deleted.has(a.id));
    const days = w.days.map((d) => ({
      ...d,
      minutes: Math.round(activities.filter((a) => a.day === d.date).reduce((n, a) => n + cardioMinutes(a), 0)),
    }));
    return { ...w, activities, days, done_minutes: days.reduce((n, d) => n + d.minutes, 0) } as unknown as T;
  }
  const t = data as unknown as ActivityToday;
  const known = new Set(t.activities.map((a) => a.id));
  const fresh = added.filter((a) => !known.has(a.id));
  const activities = [...t.activities, ...fresh].filter((a) => !deleted.has(a.id));
  const parts = new Set(activities.map((a) => a.part));
  return {
    ...t,
    activities,
    warmup: t.warmup && { ...t.warmup, done: parts.has("warmup") },
    finisher: t.finisher && { ...t.finisher, done: parts.has("finisher") },
    week_done: t.week_done + fresh.reduce((n, a) => n + cardioMinutes(a), 0),
  } as unknown as T;
}

function mondayOf(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return d.toISOString().slice(0, 10);
}

function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}
