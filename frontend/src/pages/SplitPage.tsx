// Choose how your week is split. The engine recommends one and says why; you can
// pick any built-in split or design your own sessions.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { ApiError, api } from "../api";
import { localISO } from "../plan";
import type { Catalog, Split, Splits } from "../types";

type CustomSession = { name: string; muscles: string[] };

export function SplitPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<Splits | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [custom, setCustom] = useState<CustomSession[]>([
    { name: "Day 1", muscles: [] },
    { name: "Day 2", muscles: [] },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([api<Splits>("/plan/splits"), api<Catalog>("/catalog")])
      .then(([s, c]) => {
        setData(s);
        setCatalog(c);
        setSelected(s.current ?? s.recommended);
      })
      .catch((err) =>
        err instanceof ApiError && err.status === 404
          ? navigate("/onboarding", { replace: true })
          : setError("Couldn't load splits. Check your connection and refresh."),
      );
  }, [navigate]);

  if (!data || !catalog) return <div className="splash">{error ?? "Loading…"}</div>;

  const muscleName = (id: string) => catalog.muscles.find((m) => m.id === id)?.name ?? id;
  const ordered: Split[] = [
    ...data.splits.filter((s) => s.id === data.recommended),
    ...data.splits.filter((s) => s.id !== data.recommended),
  ];

  function updateCustom(i: number, next: Partial<CustomSession>) {
    setCustom(custom.map((s, j) => (j === i ? { ...s, ...next } : s)));
  }

  async function save() {
    if (!selected) return;
    setError(null);
    if (selected === "custom") {
      if (custom.some((s) => s.muscles.length === 0 || !s.name.trim())) {
        setError("Give every session a name and at least one muscle.");
        return;
      }
    }
    setSaving(true);
    try {
      await api("/plan/split", {
        method: "PUT",
        body: {
          split_id: selected,
          custom_sessions: selected === "custom" ? custom : null,
          today: localISO(),
        },
      });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save. Try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="wizard">
      <header className="wizard-head">
        <div className="wizard-top">
          <span>Your training split</span>
          {data.current && (
            <button type="button" className="link" onClick={() => navigate(-1)}>
              Cancel
            </button>
          )}
        </div>
        <h1>How to split your week</h1>
        <p>A split decides which muscles you train on which day. Pick one, or build your own.</p>
      </header>

      <section className="choices">
        {ordered.map((s) => (
          <button
            key={s.id}
            type="button"
            className="choice split-choice"
            aria-pressed={selected === s.id}
            onClick={() => setSelected(s.id)}
          >
            <strong>
              {s.name}
              {s.id === data.recommended && <span className="badge">Recommended</span>}
            </strong>
            <i className="tick" aria-hidden="true" />
            <small>{s.id === data.recommended ? data.reason : s.blurb}</small>
            <small className="sessions">{s.sessions.map((x) => x.name).join("  ·  ")}</small>
            {s.fit_note && <small className="fit">{s.fit_note}</small>}
          </button>
        ))}

        <button
          type="button"
          className="choice split-choice"
          aria-pressed={selected === "custom"}
          onClick={() => setSelected("custom")}
        >
          <strong>Build my own</strong>
          <i className="tick" aria-hidden="true" />
          <small>Choose the muscles for each session, like chest and biceps on day one.</small>
        </button>
      </section>

      {selected === "custom" && (
        <section className="fields">
          {custom.map((s, i) => (
            <div key={i} className="card custom-session">
              <div className="card-head">
                <input
                  aria-label={`Session ${i + 1} name`}
                  value={s.name}
                  maxLength={30}
                  onChange={(e) => updateCustom(i, { name: e.target.value })}
                />
                {custom.length > 1 && (
                  <button type="button" className="link danger" onClick={() => setCustom(custom.filter((_, j) => j !== i))}>
                    Remove
                  </button>
                )}
              </div>
              <div className="pills">
                {catalog.muscles.map((m) => {
                  const on = s.muscles.includes(m.id);
                  return (
                    <button
                      key={m.id}
                      type="button"
                      className="pill"
                      aria-pressed={on}
                      onClick={() =>
                        updateCustom(i, {
                          muscles: on ? s.muscles.filter((x) => x !== m.id) : [...s.muscles, m.id].slice(0, 6),
                        })
                      }
                    >
                      {m.name}
                    </button>
                  );
                })}
              </div>
              {s.muscles.length > 0 && (
                <p className="muted small">{s.muscles.map(muscleName).join(", ")}</p>
              )}
            </div>
          ))}
          {custom.length < 7 && (
            <button
              type="button"
              className="secondary"
              onClick={() => setCustom([...custom, { name: `Day ${custom.length + 1}`, muscles: [] }])}
            >
              Add a session
            </button>
          )}
          <p className="hint">
            Recovery rules still apply: if two back-to-back days hit the same muscle, the second
            day keeps it light.
          </p>
        </section>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <nav className="wizard-nav">
        <button type="button" className="primary" disabled={saving || !selected} onClick={save}>
          {saving ? "Saving…" : "Use this split"}
        </button>
      </nav>
    </main>
  );
}
