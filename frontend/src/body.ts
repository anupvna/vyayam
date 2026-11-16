// Helpers for the body tracking screens (unit-tested).
import type { UnitSystem } from "./types";
import { kgToLb, lbToKg, round1 } from "./units";

const CM_PER_IN = 2.54;

export const lengthUnit = (u: UnitSystem) => (u === "metric" ? "cm" : "in");
export const cmToDisplay = (cm: number, u: UnitSystem) => round1(u === "metric" ? cm : cm / CM_PER_IN);
export const displayToCm = (v: number, u: UnitSystem) => (u === "metric" ? v : Math.round(v * CM_PER_IN * 100) / 100);
export const kgToDisplay = (kg: number, u: UnitSystem) => round1(u === "metric" ? kg : kgToLb(kg));
export const displayToKg = (v: number, u: UnitSystem) => (u === "metric" ? v : Math.round(lbToKg(v) * 1e4) / 1e4);

/** "-0.4 kg / week" style label for a rate. */
export function rateLabel(kgPerWeek: number | null, u: UnitSystem): string {
  if (kgPerWeek === null) return "Not enough data";
  const v = kgToDisplay(kgPerWeek, u);
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${sign}${Math.abs(v)} ${u === "metric" ? "kg" : "lb"} a week`;
}

/** Parse an optional measurement field; "" -> null, invalid -> undefined. */
export function parseOptional(value: string): number | null | undefined {
  if (value.trim() === "") return null;
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : undefined;
}
