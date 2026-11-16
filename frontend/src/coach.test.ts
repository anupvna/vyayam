import { afterEach, describe, expect, it, vi } from "vitest";

import { askWhy, savedMinutes, saveMinutes, sendsOnEnter, suggestions } from "./coach";

describe("coach helpers", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("suggests questions that fit the day", () => {
    expect(suggestions(true)).toContain("I only have 30 minutes");
    expect(suggestions(false)).not.toContain("I only have 30 minutes");
  });

  it("asks about one exercise", () => {
    expect(askWhy("Barbell row")).toBe("Why is my target for Barbell row what it is today?");
  });

  it("remembers a shortened day, and ignores junk", () => {
    const store = new Map<string, string>();
    vi.stubGlobal("sessionStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => store.set(k, v),
      removeItem: (k: string) => store.delete(k),
    });
    expect(savedMinutes("2026-11-16")).toBeNull();
    saveMinutes("2026-11-16", 30);
    expect(savedMinutes("2026-11-16")).toBe(30);
    expect(savedMinutes("2026-11-17")).toBeNull();
    saveMinutes("2026-11-16", null);
    expect(savedMinutes("2026-11-16")).toBeNull();
    store.set("vyayam:minutes:2026-11-18", "abc");
    expect(savedMinutes("2026-11-18")).toBeNull();
  });

  it("sends on Enter only on a keyboard, never mid-composition", () => {
    expect(sendsOnEnter({ key: "Enter", shiftKey: false }, false)).toBe(true);
    expect(sendsOnEnter({ key: "Enter", shiftKey: true }, false)).toBe(false);
    expect(sendsOnEnter({ key: "Enter", shiftKey: false }, true)).toBe(false);
    expect(sendsOnEnter({ key: "Enter", shiftKey: false, nativeEvent: { isComposing: true } }, false)).toBe(false);
  });
});
