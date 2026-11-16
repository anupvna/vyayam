import { describe, expect, it } from "vitest";

import { cmToDisplay, displayToCm, displayToKg, kgToDisplay, parseOptional, rateLabel } from "./body";

describe("body helpers", () => {
  it("converts lengths and weights both ways", () => {
    expect(cmToDisplay(90, "imperial")).toBe(35.4);
    expect(displayToCm(35.4, "imperial")).toBe(89.92);
    expect(kgToDisplay(80, "imperial")).toBe(176.4);
    expect(kgToDisplay(displayToKg(176.4, "imperial"), "imperial")).toBe(176.4);
  });

  it("labels rates", () => {
    expect(rateLabel(-0.4, "metric")).toBe("−0.4 kg a week");
    expect(rateLabel(0.25, "imperial")).toBe("+0.6 lb a week");
    expect(rateLabel(null, "metric")).toBe("Not enough data");
  });

  it("parses optional fields", () => {
    expect(parseOptional("")).toBeNull();
    expect(parseOptional("38.5")).toBe(38.5);
    expect(parseOptional("abc")).toBeUndefined();
    expect(parseOptional("-3")).toBeUndefined();
  });
});
