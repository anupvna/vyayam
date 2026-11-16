// The 10-second daily check-in: sleep, energy, stress, soreness, pain, and red flags.
import { useState } from "react";

import { ApiError, api } from "../api";
import { offlineAssessment } from "../offline/queue";
import type { Assessment, Catalog } from "../types";

const SCALES = [
  { key: "sleep", label: "Sleep", low: "Terrible", high: "Great" },
  { key: "energy", label: "Energy", low: "Drained", high: "Full" },
  { key: "stress", label: "Stress", low: "Calm", high: "Very stressed" },
] as const;

const SORE = ["chest", "back", "shoulders", "arms", "core", "glutes", "legs"];

const RED_FLAGS: [string, string][] = [
  ["chest_pain", "Chest pain or pressure"],
  ["dizziness", "Dizziness or fainting"],
  ["shortness_of_breath", "Unusual shortness of breath"],
  ["sharp_joint_pain", "Sharp pain in a joint"],
  ["numbness", "Numbness or tingling"],
];

type Props = { today: string; catalog: Catalog; onDone: (a: Assessment) => void; onSkip: () => void };

export function CheckInCard({ today, catalog, onDone, onSkip }: Props) {
  const [values, setValues] = useState({ sleep: 0, energy: 0, stress: 0 });
  const [sore, setSore] = useState<string[]>([]);
  const [hurts, setHurts] = useState<boolean | null>(null);
  const [pain, setPain] = useState<string[]>([]);
  const [flags, setFlags] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const toggle = (list: string[], set: (v: string[]) => void, id: string) =>
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

  async function submit() {
    if (!values.sleep || !values.energy || !values.stress) return setError("Tap a number for sleep, energy and stress.");
    setBusy(true);
    setError(null);
    try {
      const body = { today, ...values, sore_areas: sore, pain_areas: hurts ? pain : [], red_flags: flags };
      // Offline, red flags still stop training; the rest of the advice waits for the sync.
      onDone(await api<Assessment>("/readiness", { method: "POST", body, offline: () => offlineAssessment(body) }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card checkin" aria-label="Daily check-in">
      <div className="card-head">
        <h2>How are you today?</h2>
        <button type="button" className="link small" onClick={onSkip}>
          Skip
        </button>
      </div>
      <p className="muted small">Ten seconds. Your workout adapts to it.</p>

      {SCALES.map((s) => (
        <div key={s.key} className="scale">
          <span className="label">{s.label}</span>
          <div className="segmented" role="group" aria-label={s.label}>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                aria-pressed={values[s.key] === n}
                aria-label={`${s.label} ${n}`}
                onClick={() => setValues({ ...values, [s.key]: n })}
              >
                {n}
              </button>
            ))}
          </div>
          <span className="scale-ends">
            <small>{s.low}</small>
            <small>{s.high}</small>
          </span>
        </div>
      ))}

      <div className="label">
        Anything sore?
        <div className="pills">
          {SORE.map((a) => (
            <button key={a} type="button" className="pill" aria-pressed={sore.includes(a)} onClick={() => toggle(sore, setSore, a)}>
              {a[0].toUpperCase() + a.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="label">
        Any pain (not just soreness)?
        <div className="segmented" role="group" aria-label="Any pain">
          <button type="button" aria-pressed={hurts === false} onClick={() => setHurts(false)}>
            No
          </button>
          <button type="button" aria-pressed={hurts === true} onClick={() => setHurts(true)}>
            Yes
          </button>
        </div>
        {hurts && (
          <div className="pills">
            {catalog.body_parts.map((b) => (
              <button key={b.id} type="button" className="pill" aria-pressed={pain.includes(b.id)} onClick={() => toggle(pain, setPain, b.id)}>
                {b.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="label red-flags">
        Right now, do you have any of these?
        {RED_FLAGS.map(([id, label]) => (
          <label key={id} className="check">
            <input type="checkbox" checked={flags.includes(id)} onChange={() => toggle(flags, setFlags, id)} />
            {label}
          </label>
        ))}
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button type="button" className="primary" disabled={busy} onClick={submit}>
        {busy ? "Saving…" : "Done"}
      </button>
    </section>
  );
}
