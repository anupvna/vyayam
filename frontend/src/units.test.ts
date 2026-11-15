import { describe, expect, it } from "vitest";

import { cmToFtIn, ftInToCm, kgToLb, lbToKg, round1 } from "./units";

describe("units", () => {
  it("converts kg and lb both ways", () => {
    expect(round1(kgToLb(100))).toBe(220.5);
    expect(round1(lbToKg(220.5))).toBe(100);
  });

  it("converts height to feet and inches", () => {
    expect(cmToFtIn(178)).toEqual({ ft: 5, inches: 10 });
    expect(cmToFtIn(182.88)).toEqual({ ft: 6, inches: 0 }); // never "5 ft 12 in"
  });

  it("round-trips feet/inches through cm", () => {
    for (let ft = 4; ft <= 7; ft++) {
      for (let inches = 0; inches < 12; inches++) {
        expect(cmToFtIn(ftInToCm(ft, inches))).toEqual({ ft, inches });
      }
    }
  });
});
