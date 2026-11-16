// Body: log today's weight, see the trend (not the noisy daily number), your rate,
// BMI, body fat estimates, measurements, and when you'll reach your goal (a range).
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api";
import { cmToDisplay, displayToCm, displayToKg, kgToDisplay, lengthUnit, parseOptional, rateLabel } from "../body";
import { Chart } from "../charts/Chart";
import { ACCENT, ACCENT_WASH, INK, SERIES, baseOption } from "../charts/theme";
import type { BodySummary, Profile } from "../types";

type Props = { today: string; profile: Profile };

const MEASURE_LINES: { key: "waist_cm" | "chest_cm" | "arm_cm" | "thigh_cm" | "hips_cm"; label: string }[] = [
  { key: "waist_cm", label: "Waist" },
  { key: "chest_cm", label: "Chest" },
  { key: "arm_cm", label: "Arm" },
  { key: "thigh_cm", label: "Thigh" },
  { key: "hips_cm", label: "Hips" },
];

const FIELDS: { key: string; label: string }[] = [
  { key: "neck_cm", label: "Neck" },
  { key: "waist_cm", label: "Waist (at the navel)" },
  { key: "hips_cm", label: "Hips (widest point)" },
  { key: "chest_cm", label: "Chest" },
  { key: "arm_cm", label: "Upper arm" },
  { key: "thigh_cm", label: "Thigh" },
];

export function BodySection({ today, profile }: Props) {
  const u = profile.unit_system;
  const wUnit = u === "metric" ? "kg" : "lb";
  const [data, setData] = useState<BodySummary | null>(null);
  const [weight, setWeight] = useState("");
  const [showMeasure, setShowMeasure] = useState(false);
  const [measure, setMeasure] = useState<Record<string, string>>({});
  const [fat, setFat] = useState("");
  const [fatSource, setFatSource] = useState("scale");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () =>
      api<BodySummary>(`/body/summary?today=${today}`)
        .then(setData)
        .catch(() => setError("Couldn't load body data. Check your connection and refresh.")),
    [today],
  );
  useEffect(() => {
    void load();
  }, [load]);

  async function saveWeight() {
    const v = Number(weight);
    if (!weight.trim() || !Number.isFinite(v)) return setError(`Enter your weight in ${wUnit}.`);
    setBusy(true);
    setError(null);
    try {
      await api(`/body/weights/${today}`, { method: "PUT", body: { weight_kg: displayToKg(v, u) } });
      setWeight("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function saveMeasurements() {
    const body: Record<string, number | string | null> = {};
    for (const f of FIELDS) {
      const v = parseOptional(measure[f.key] ?? "");
      if (v === undefined) return setError(`Check the ${f.label.toLowerCase()} value.`);
      body[f.key] = v === null ? null : displayToCm(v, u);
    }
    const bf = parseOptional(fat);
    if (bf === undefined) return setError("Check the body fat value.");
    body.body_fat_pct = bf;
    body.body_fat_source = bf === null ? null : fatSource;
    setBusy(true);
    setError(null);
    try {
      await api(`/body/measurements/${today}`, { method: "PUT", body });
      setMeasure({});
      setFat("");
      setShowMeasure(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Enter at least one measurement.");
    } finally {
      setBusy(false);
    }
  }

  const weightOption = useMemo(() => {
    if (!data || data.weights.length === 0) return null;
    const pts = data.weights;
    const proj = data.weight_projection;
    const target = proj ? kgToDisplay(proj.target, u) : null;
    const end = proj?.status === "on_track" && proj.latest ? proj.latest : pts[pts.length - 1].day;
    const o = baseOption();
    return {
      ...o,
      legend: { top: 0, left: 0, textStyle: { color: INK.secondary }, itemWidth: 14, itemHeight: 8 },
      grid: { ...o.grid, top: 34 },
      xAxis: { ...o.xAxis, max: end },
      yAxis: { ...o.yAxis, name: wUnit, nameTextStyle: { color: INK.muted } },
      series: [
        {
          name: "Trend",
          type: "line",
          showSymbol: false,
          lineStyle: { width: 2, color: ACCENT },
          itemStyle: { color: ACCENT },
          data: pts.map((p) => [p.day, kgToDisplay(p.trend_kg, u)]),
          ...(proj?.status === "on_track" && proj.earliest && proj.latest
            ? {
                markArea: {
                  silent: true,
                  itemStyle: { color: ACCENT_WASH },
                  label: { show: true, position: "insideTop", color: INK.secondary, formatter: "Likely goal date" },
                  data: [[{ xAxis: proj.earliest }, { xAxis: proj.latest }]],
                },
              }
            : {}),
        },
        {
          name: "Daily weigh-ins",
          type: "scatter",
          symbolSize: 8,
          itemStyle: { color: INK.secondary, borderColor: INK.surface, borderWidth: 2 },
          data: pts.map((p) => [p.day, kgToDisplay(p.weight_kg, u)]),
        },
        ...(target !== null
          ? [
              {
                name: "Goal",
                type: "line",
                showSymbol: false,
                lineStyle: { width: 1.5, type: "dashed", color: INK.primary },
                itemStyle: { color: INK.primary },
                data: [
                  [pts[0].day, target],
                  [end, target],
                ],
              },
            ]
          : []),
      ],
    };
  }, [data, u, wUnit]);

  const fatOption = useMemo(() => {
    if (!data || data.body_fat.length === 0) return null;
    const o = baseOption();
    const target = data.body_fat_projection?.target ?? null;
    return {
      ...o,
      yAxis: { ...o.yAxis, name: "%", nameTextStyle: { color: INK.muted } },
      tooltip: {
        ...o.tooltip,
        trigger: "item" as const,
        formatter: (p: { data: [string, number, string] }) => `${p.data[0]}<br/>${p.data[1]}% (${p.data[2]})`,
      },
      series: [
        {
          name: "Body fat",
          type: "line",
          symbolSize: 8,
          lineStyle: { width: 2, color: ACCENT },
          itemStyle: { color: ACCENT, borderColor: INK.surface, borderWidth: 2 },
          data: data.body_fat.map((f) => [f.day, f.pct, f.method]),
          ...(target !== null
            ? {
                markLine: {
                  silent: true,
                  symbol: "none",
                  lineStyle: { type: "dashed", color: INK.primary },
                  label: { color: INK.secondary, formatter: `Goal ${target}%` },
                  data: [{ yAxis: target }],
                },
              }
            : {}),
        },
      ],
    };
  }, [data]);

  const measureOption = useMemo(() => {
    if (!data || data.measurements.length < 2) return null;
    const lines = MEASURE_LINES.filter((m) => data.measurements.some((x) => x[m.key] !== null));
    if (lines.length === 0) return null;
    const o = baseOption();
    return {
      ...o,
      legend: { top: 0, left: 0, textStyle: { color: INK.secondary }, itemWidth: 14, itemHeight: 8 },
      grid: { ...o.grid, top: 34, right: 52 },
      yAxis: { ...o.yAxis, name: lengthUnit(u), nameTextStyle: { color: INK.muted } },
      series: lines.map((m, i) => ({
        name: m.label,
        type: "line",
        connectNulls: true,
        symbolSize: 7,
        lineStyle: { width: 2, color: SERIES[i] },
        itemStyle: { color: SERIES[i], borderColor: INK.surface, borderWidth: 2 },
        endLabel: { show: true, color: INK.secondary, formatter: m.label, fontSize: 11 },
        data: data.measurements
          .filter((x) => x[m.key] !== null)
          .map((x) => [x.day, cmToDisplay(x[m.key] as number, u)]),
      })),
    };
  }, [data, u]);

  if (!data) return <p className="muted">{error ?? "Loading…"}</p>;

  const latestFat = data.body_fat[data.body_fat.length - 1];

  return (
    <div className="stack-tight progress-section">
      <section className="card">
        <h2>Today's weight</h2>
        <div className="set-entry two-col">
          <label>
            <span className="hint">{wUnit}</span>
            <input inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="Weigh in" />
          </label>
          <button type="button" className="primary" disabled={busy} onClick={saveWeight}>
            Save weight
          </button>
        </div>
        <p className="hint">Weigh in the morning, after the bathroom, before eating. Daily swings are normal; the trend is what counts.</p>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </section>

      <section className="tiles-row">
        <div className="tile-stat">
          <span className="muted small">Trend weight</span>
          <b>{data.trend_kg !== null ? `${kgToDisplay(data.trend_kg, u)} ${wUnit}` : "No data"}</b>
        </div>
        <div className="tile-stat">
          <span className="muted small">Rate</span>
          <b className="smaller">{rateLabel(data.rate_kg_per_week, u)}</b>
        </div>
        <div className="tile-stat">
          <span className="muted small">BMI</span>
          <b>{data.bmi ?? "-"}</b>
        </div>
      </section>
      <p className="hint">{data.bmi_note}</p>

      {data.advice.length > 0 && (
        <ul className="advice">
          {data.advice.map((a) => (
            <li key={a} className="warning">
              {a}
            </li>
          ))}
        </ul>
      )}

      <section className="card">
        <div className="card-head">
          <h2>Weight</h2>
          {data.weight_projection && <span className="muted small">Goal {kgToDisplay(data.weight_projection.target, u)} {wUnit}</span>}
        </div>
        {weightOption ? (
          <Chart option={weightOption} height={240} label="Weight trend, daily weigh-ins and goal" />
        ) : (
          <p className="muted">Log your weight a few mornings a week. The trend line appears after the first weigh-in.</p>
        )}
        {data.weight_projection && <p className="projection">{data.weight_projection.message}</p>}
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Body fat</h2>
          {latestFat && (
            <span className="muted small">
              {latestFat.pct}% ({latestFat.method})
            </span>
          )}
        </div>
        {fatOption ? (
          <Chart option={fatOption} height={200} label="Body fat percentage over time" />
        ) : (
          <p className="muted">Add neck and waist measurements{profile.sex === "female" ? " and hips" : ""} for a US Navy estimate, or a reading from a scale.</p>
        )}
        <p className="hint">
          Every body fat number here is an estimate. Tape methods are typically within about 3 to 4 points of a DEXA
          scan; what matters is the direction over time, measured the same way.
        </p>
        {data.body_fat_projection && <p className="projection">{data.body_fat_projection.message}</p>}
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Measurements</h2>
          <button type="button" className="link small" onClick={() => setShowMeasure(!showMeasure)}>
            {showMeasure ? "Close" : "Add today's"}
          </button>
        </div>
        {measureOption && <Chart option={measureOption} height={220} label="Body measurements over time" />}
        {!measureOption && !showMeasure && (
          <p className="muted">Measure every 2 to 4 weeks, same time of day, tape snug but not tight.</p>
        )}
        {showMeasure && (
          <div className="fields">
            <div className="two">
              {FIELDS.map((f) => (
                <label key={f.key}>
                  <span className="hint">
                    {f.label}, {lengthUnit(u)}
                  </span>
                  <input
                    inputMode="decimal"
                    value={measure[f.key] ?? ""}
                    onChange={(e) => setMeasure({ ...measure, [f.key]: e.target.value })}
                  />
                </label>
              ))}
            </div>
            <div className="two">
              <label>
                <span className="hint">Body fat % (optional)</span>
                <input inputMode="decimal" value={fat} onChange={(e) => setFat(e.target.value)} />
              </label>
              <label>
                <span className="hint">Measured with</span>
                <div className="segmented">
                  {["scale", "dexa", "other"].map((s) => (
                    <button key={s} type="button" aria-pressed={fatSource === s} onClick={() => setFatSource(s)}>
                      {s === "dexa" ? "DEXA" : s[0].toUpperCase() + s.slice(1)}
                    </button>
                  ))}
                </div>
              </label>
            </div>
            <button type="button" className="primary" disabled={busy} onClick={saveMeasurements}>
              Save measurements
            </button>
          </div>
        )}
        {data.measurements.length > 0 && (
          <details className="table-view">
            <summary>Show as a table</summary>
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  {MEASURE_LINES.map((m) => (
                    <th key={m.key}>{m.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.measurements.map((x) => (
                  <tr key={x.day}>
                    <td>{x.day}</td>
                    {MEASURE_LINES.map((m) => (
                      <td key={m.key}>{x[m.key] !== null ? cmToDisplay(x[m.key] as number, u) : ""}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        )}
      </section>
    </div>
  );
}
