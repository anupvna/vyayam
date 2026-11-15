// Unit conversion. The server always stores metric; the screen shows whatever the
// user picked. Pure functions, so they're easy to unit-test.

const KG_PER_LB = 0.45359237;
const CM_PER_IN = 2.54;

export const kgToLb = (kg: number): number => kg / KG_PER_LB;
export const lbToKg = (lb: number): number => lb * KG_PER_LB;

export function cmToFtIn(cm: number): { ft: number; inches: number } {
  const totalInches = Math.round(cm / CM_PER_IN);
  return { ft: Math.floor(totalInches / 12), inches: totalInches % 12 };
}

export const ftInToCm = (ft: number, inches: number): number => (ft * 12 + inches) * CM_PER_IN;

/** Round to one decimal place (what we show). */
export const round1 = (n: number): number => Math.round(n * 10) / 10;

/** Round to two decimals (what we store), so 176 lb -> kg -> lb shows 176 again. */
export const round2 = (n: number): number => Math.round(n * 100) / 100;
