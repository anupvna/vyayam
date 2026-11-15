// The setup wizard: About you -> Goal -> Your week -> Your gym -> Injuries -> Review.
// Each step says in one line what you're choosing and why it matters.
// Also used to edit your setup later (then the gym step is skipped; gyms have their own tab).
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import { ApiError, api } from "../api";
import { AdviceList } from "../components/AdviceList";
import { EquipmentPicker } from "../components/EquipmentPicker";
import { DAY_NAMES, EXPERIENCE, GOALS, goalName } from "../labels";
import {
  emptyForm,
  fromProfile,
  heightCm,
  switchUnit,
  targetWeightKg,
  toProfileInput,
  validateStep,
  weightKg,
  type FormState,
  type StepId,
} from "../onboardingForm";
import type { Advice, Catalog, Gym, Profile } from "../types";

const THIS_YEAR = new Date().getFullYear();
const SESSION_OPTIONS = [30, 45, 60, 75, 90];

const STEPS: Record<StepId, { title: string; intro: string }> = {
  about: {
    title: "About you",
    intro: "Your starting point. It sets training volume and body calculations, and stays private.",
  },
  goal: {
    title: "Your goal",
    intro: "Pick what matters most right now. It decides how your training and targets are set.",
  },
  schedule: {
    title: "Your week",
    intro: "Tap the days you can usually train. Your weekly plan is built around them.",
  },
  gym: {
    title: "Your gym",
    intro: "Tap everything your gym has. Your plan will only use this equipment.",
  },
  injuries: {
    title: "Injuries",
    intro: "Tap any area that's injured or sore. Exercises that load it will be left out.",
  },
  review: {
    title: "Check and finish",
    intro: "Make sure this looks right. You can change any of it later.",
  },
};

export function OnboardingPage() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [editing, setEditing] = useState(false);
  const [needsGym, setNeedsGym] = useState(true);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [advice, setAdvice] = useState<Advice[]>([]);
  const [saving, setSaving] = useState(false);

  // Load the catalog, plus the existing profile and gyms if we're editing.
  useEffect(() => {
    void (async () => {
      try {
        const [cat, gyms] = await Promise.all([api<Catalog>("/catalog"), api<Gym[]>("/gyms")]);
        setCatalog(cat);
        setNeedsGym(gyms.length === 0);
        const commercial = cat.presets.find((p) => p.id === "commercial");
        let start = { ...emptyForm(), equipment: commercial?.equipment ?? [] };
        try {
          start = { ...fromProfile(await api<Profile>("/profile")), equipment: start.equipment };
          setEditing(true);
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 404)) throw err;
        }
        setForm(start);
      } catch {
        setError("Couldn't load your setup. Check your connection and refresh.");
      }
    })();
  }, []);

  const steps = useMemo<StepId[]>(
    () =>
      needsGym
        ? ["about", "goal", "schedule", "gym", "injuries", "review"]
        : ["about", "goal", "schedule", "injuries", "review"],
    [needsGym],
  );
  const step = steps[stepIndex];

  // Live goal check on the goal and review steps (debounced: one call after typing stops).
  const goalKey = JSON.stringify([form.sex, heightCm(form), weightKg(form), form.goal,
    targetWeightKg(form), form.targetBodyFat, form.unit]);
  useEffect(() => {
    if ((step !== "goal" && step !== "review") || validateStep("about", form, THIS_YEAR) || !form.goal) {
      setAdvice([]);
      return;
    }
    const input = toProfileInput(form);
    const t = setTimeout(() => {
      api<Advice[]>("/profile/assess", {
        method: "POST",
        body: {
          sex: input.sex,
          height_cm: input.height_cm,
          weight_kg: input.weight_kg,
          goal: input.goal,
          target_weight_kg: input.target_weight_kg,
          target_body_fat_pct: input.target_body_fat_pct,
          unit_system: input.unit_system,
        },
      })
        .then(setAdvice)
        .catch(() => setAdvice([]));
    }, 400);
    return () => clearTimeout(t);
  }, [step, goalKey]); // goalKey captures every form field the check depends on

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  function next() {
    const problem = validateStep(step, form, THIS_YEAR);
    if (problem) return setError(problem);
    setError(null);
    setStepIndex((i) => Math.min(i + 1, steps.length - 1));
    window.scrollTo(0, 0);
  }

  function back() {
    setError(null);
    setStepIndex((i) => Math.max(i - 1, 0));
    window.scrollTo(0, 0);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api<Profile>("/profile", { method: "PUT", body: toProfileInput(form) });
      if (needsGym) {
        await api<Gym>("/gyms", {
          method: "POST",
          body: { name: form.gymName.trim(), equipment: form.equipment },
        });
      }
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save. Try again.");
    } finally {
      setSaving(false);
    }
  }

  if (!catalog) return <div className="splash">{error ?? "Loading…"}</div>;

  const weightUnit = form.unit === "metric" ? "kg" : "lb";
  const pressed = (on: boolean) => ({ "aria-pressed": on });

  return (
    <main className="wizard">
      <header className="wizard-head">
        <div className="wizard-top">
          <span>
            Step {stepIndex + 1} of {steps.length}
          </span>
          {editing && (
            <button type="button" className="link" onClick={() => navigate("/profile")}>
              Cancel
            </button>
          )}
        </div>
        <div className="progress" aria-hidden="true">
          {steps.map((s, i) => (
            <span key={s} className={i <= stepIndex ? "done" : ""} />
          ))}
        </div>
        <h1>{STEPS[step].title}</h1>
        <p>{STEPS[step].intro}</p>
      </header>

      <section className="fields">
        {step === "about" && (
          <>
            <div className="segmented" role="group" aria-label="Units">
              {(["metric", "imperial"] as const).map((u) => (
                <button
                  key={u}
                  type="button"
                  {...pressed(form.unit === u)}
                  onClick={() => setForm((f) => switchUnit(f, u))}
                >
                  {u === "metric" ? "Kilograms and cm" : "Pounds and feet"}
                </button>
              ))}
            </div>

            <label>
              Birth year
              <input
                inputMode="numeric"
                placeholder={`e.g. ${THIS_YEAR - 25}`}
                value={form.birthYear}
                onChange={(e) => set("birthYear", e.target.value)}
              />
            </label>

            <div className="label">
              Sex
              <span className="hint">Used only by the body-fat formulas.</span>
              <div className="segmented" role="group" aria-label="Sex">
                {(["male", "female"] as const).map((s) => (
                  <button key={s} type="button" {...pressed(form.sex === s)} onClick={() => set("sex", s)}>
                    {s === "male" ? "Male" : "Female"}
                  </button>
                ))}
              </div>
            </div>

            {form.unit === "metric" ? (
              <label>
                Height in cm
                <input
                  inputMode="decimal"
                  placeholder="e.g. 175"
                  value={form.heightCm}
                  onChange={(e) => set("heightCm", e.target.value)}
                />
              </label>
            ) : (
              <div className="two">
                <label>
                  Height, feet
                  <input
                    inputMode="numeric"
                    placeholder="5"
                    value={form.heightFt}
                    onChange={(e) => set("heightFt", e.target.value)}
                  />
                </label>
                <label>
                  and inches
                  <input
                    inputMode="numeric"
                    placeholder="10"
                    value={form.heightIn}
                    onChange={(e) => set("heightIn", e.target.value)}
                  />
                </label>
              </div>
            )}

            <label>
              Weight today in {weightUnit}
              <input
                inputMode="decimal"
                value={form.weight}
                onChange={(e) => set("weight", e.target.value)}
              />
            </label>

            <div className="label">
              Training experience
              <div className="choices">
                {EXPERIENCE.map((x) => (
                  <button
                    key={x.id}
                    type="button"
                    className="choice"
                    {...pressed(form.experience === x.id)}
                    onClick={() => set("experience", x.id)}
                  >
                    <strong>{x.name}</strong>
                    <i className="tick" aria-hidden="true" />
                    <small>{x.blurb}</small>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        {step === "goal" && (
          <>
            <div className="choices">
              {GOALS.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  className="choice"
                  {...pressed(form.goal === g.id)}
                  onClick={() => set("goal", g.id)}
                >
                  <strong>{g.name}</strong>
                  <i className="tick" aria-hidden="true" />
                  <small>{g.blurb}</small>
                </button>
              ))}
            </div>

            <div className="label">
              Targets
              <span className="hint">Optional. Add them now or later.</span>
              <div className="two">
                <label>
                  <span className="hint">Weight in {weightUnit}</span>
                  <input
                    inputMode="decimal"
                    value={form.targetWeight}
                    onChange={(e) => set("targetWeight", e.target.value)}
                  />
                </label>
                <label>
                  <span className="hint">Body fat %</span>
                  <input
                    inputMode="decimal"
                    value={form.targetBodyFat}
                    onChange={(e) => set("targetBodyFat", e.target.value)}
                  />
                </label>
              </div>
            </div>
            <AdviceList advice={advice} />
          </>
        )}

        {step === "schedule" && (
          <>
            <div className="label">
              Training days
              <span className="hint">
                {form.days.length} {form.days.length === 1 ? "day" : "days"} a week. At least one
                full rest day is kept for recovery.
              </span>
              <div className="pills week-pills">
                {DAY_NAMES.map((name, i) => {
                  const on = form.days.includes(i);
                  return (
                    <button
                      key={name}
                      type="button"
                      className="pill"
                      {...pressed(on)}
                      onClick={() => set("days", on ? form.days.filter((d) => d !== i) : [...form.days, i])}
                    >
                      {name}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="label">
              Time per session
              <div className="segmented" role="group" aria-label="Minutes per session">
                {SESSION_OPTIONS.map((m) => (
                  <button key={m} type="button" {...pressed(form.minutes === m)} onClick={() => set("minutes", m)}>
                    {m} min
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        {step === "gym" && (
          <>
            <label>
              Name this gym
              <input
                value={form.gymName}
                maxLength={60}
                placeholder="e.g. NYU Palladium"
                onChange={(e) => set("gymName", e.target.value)}
              />
            </label>
            <EquipmentPicker catalog={catalog} selected={form.equipment} onChange={(eq) => set("equipment", eq)} />
          </>
        )}

        {step === "injuries" && (
          <>
            <div className="pills">
              {catalog.body_parts.map((b) => {
                const on = form.injuries.includes(b.id);
                return (
                  <button
                    key={b.id}
                    type="button"
                    className="pill"
                    {...pressed(on)}
                    onClick={() =>
                      set("injuries", on ? form.injuries.filter((x) => x !== b.id) : [...form.injuries, b.id])
                    }
                  >
                    {b.name}
                  </button>
                );
              })}
            </div>
            <label>
              Anything else to know
              <textarea
                rows={3}
                maxLength={500}
                placeholder="Optional, e.g. old ACL repair on the left knee"
                value={form.injuryNotes}
                onChange={(e) => set("injuryNotes", e.target.value)}
              />
            </label>
            <p className="hint">
              This isn't a diagnosis. For pain that lasts, see a qualified professional.
            </p>
          </>
        )}

        {step === "review" && (
          <>
            <dl className="summary">
              <dt>Goal</dt>
              <dd>{form.goal ? goalName(form.goal) : ""}</dd>
              <dt>Training days</dt>
              <dd>
                {[...form.days].sort((a, b) => a - b).map((d) => DAY_NAMES[d]).join(", ")}, {form.minutes} min each
              </dd>
              {needsGym && (
                <>
                  <dt>Gym</dt>
                  <dd>
                    {form.gymName}, {form.equipment.length} items
                  </dd>
                </>
              )}
              <dt>Injuries</dt>
              <dd>
                {form.injuries.length
                  ? form.injuries.map((id) => catalog.body_parts.find((b) => b.id === id)?.name ?? id).join(", ")
                  : "None"}
              </dd>
            </dl>
            <AdviceList advice={advice} />
          </>
        )}

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </section>

      <nav className="wizard-nav">
        {stepIndex > 0 && (
          <button type="button" className="secondary" onClick={back}>
            Back
          </button>
        )}
        {step === "review" ? (
          <button type="button" className="primary" onClick={save} disabled={saving}>
            {saving ? "Saving…" : editing ? "Save changes" : "Finish setup"}
          </button>
        ) : (
          <button type="button" className="primary" onClick={next}>
            Continue
          </button>
        )}
      </nav>
    </main>
  );
}
