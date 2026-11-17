import { describe, expect, it } from "vitest";

import { confirmHint, newPasswordProblem } from "./authForm";

describe("new password checks", () => {
  it("needs 10 characters and a matching confirmation", () => {
    expect(newPasswordProblem("short", "short")).toMatch(/at least 10/);
    expect(newPasswordProblem("correct horse", "correct hose")).toMatch(/don't match/);
    expect(newPasswordProblem("correct horse", "correct horse")).toBeNull();
  });

  it("hints while typing without nagging too early", () => {
    expect(confirmHint("correct horse", "")).toBeNull();
    expect(confirmHint("correct horse", "correct")).toBeNull(); // still typing
    expect(confirmHint("correct horse", "correcx")).toMatch(/don't match/);
    expect(confirmHint("correct horse", "correct horse")).toBe("Passwords match.");
  });
});
