// Pure helpers for the coach screen (unit-tested).

/** Starter questions, matched to what the coach can actually do. */
export function suggestions(isTrainingDay: boolean): string[] {
  return isTrainingDay
    ? ["Why this weight today?", "I only have 30 minutes", "Can I train at home today?", "I'm sore from last time", "What cardio should I do?", "How am I doing?"]
    : ["What's next this week?", "What cardio should I do today?", "How am I doing?", "When will I reach my goal?", "How much protein do I need?"];
}

/** A question about one exercise's target, used by the "Ask why" link on Today. */
export const askWhy = (exerciseName: string): string => `Why is my target for ${exerciseName} what it is today?`;

// "Shorten today" is a view setting: it's kept for the day so Today opens shortened.
const minutesKey = (day: string) => `vyayam:minutes:${day}`;

export function savedMinutes(day: string): number | null {
  try {
    const v = Number(sessionStorage.getItem(minutesKey(day)));
    return v >= 20 && v <= 180 ? v : null;
  } catch {
    return null;
  }
}

export function saveMinutes(day: string, minutes: number | null): void {
  try {
    if (minutes === null) sessionStorage.removeItem(minutesKey(day));
    else sessionStorage.setItem(minutesKey(day), String(minutes));
  } catch {
    // storage unavailable: it just won't be remembered
  }
}

/** Enter sends; Shift+Enter makes a new line (and phones' Enter key just adds a line). */
export function sendsOnEnter(e: { key: string; shiftKey: boolean; nativeEvent?: { isComposing?: boolean } }, touch: boolean): boolean {
  return e.key === "Enter" && !e.shiftKey && !touch && !e.nativeEvent?.isComposing;
}
