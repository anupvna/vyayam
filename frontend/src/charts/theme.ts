// Chart colours and shared styling. The categorical palette was checked with a
// colour-vision validator against the card surface (#1c2140): lightness band,
// chroma, colour-blind separation of neighbours, and contrast all pass. Keep this
// order: it's what makes neighbouring colours distinguishable.
export const SERIES = ["#b88a45", "#3987e5", "#199e70", "#9085e9", "#d55181"];

export const INK = {
  primary: "#f1ebdf",
  secondary: "#9ca1bf",
  muted: "#6a7099",
  grid: "rgba(156, 161, 191, 0.14)",
  surface: "#1c2140",
};

export const ACCENT = "#cda35e"; // single-series lines (brass)
export const ACCENT_WASH = "rgba(205, 163, 94, 0.16)";

// Recovery states: status colours, always shown with a text legend too.
export const STATUS = {
  fresh: "#2f8f5b",
  recovering: "#c98500",
  fatigued: "#e2664c",
};

const FONT = '"Instrument Sans Variable", system-ui, sans-serif';

/** Shared base for every line chart: recessive grid and axes, readable ink, a
 * crosshair tooltip. */
export function baseOption() {
  return {
    animation: false,
    textStyle: { fontFamily: FONT, color: INK.secondary },
    grid: { left: 8, right: 16, top: 44, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "axis" as const,
      axisPointer: { type: "line" as const, lineStyle: { color: INK.muted } },
      backgroundColor: "#252b52",
      borderColor: "#323a66",
      textStyle: { color: INK.primary, fontFamily: FONT, fontSize: 13 },
    },
    xAxis: {
      type: "time" as const,
      axisLine: { lineStyle: { color: INK.grid } },
      axisTick: { show: false },
      axisLabel: { color: INK.muted, fontSize: 11, hideOverlap: true },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value" as const,
      scale: true,
      axisLabel: { color: INK.muted, fontSize: 11 },
      splitLine: { lineStyle: { color: INK.grid } },
    },
  };
}
