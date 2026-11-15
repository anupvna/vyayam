import { describe, expect, it } from "vitest";

import { effortLabel, formatRest, formatSets, localISO, parseISO } from "./plan";

describe("plan helpers", () => {
  it("uses the local date, not UTC", () => {
    expect(localISO(new Date(2026, 10, 16, 23, 30))).toBe("2026-11-16");
    expect(parseISO("2026-11-16").getDate()).toBe(16);
    expect(localISO(parseISO("2026-01-05"))).toBe("2026-01-05");
  });

  it("formats rest, sets and effort", () => {
    expect(formatRest(90)).toBe("1:30");
    expect(formatRest(180)).toBe("3 min");
    expect(formatSets({ sets: 3, reps: [6, 10] })).toBe("3 × 6–10");
    expect(formatSets({ sets: 2, reps: [5, 5] })).toBe("2 × 5");
    expect(effortLabel(2)).toBe("Stop 2 reps before failure");
    expect(effortLabel(4)).toMatch(/Easy/);
  });
});
