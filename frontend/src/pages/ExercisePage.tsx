// One exercise: muscle map, what you need, how to do it, mistakes, safety, and the
// best alternatives for your gym and injuries. Favorite or hide it from here.
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { ApiError, api } from "../api";
import { EquipmentArt } from "../components/EquipmentArt";
import { MuscleMap } from "../components/MuscleMap";
import { artFor } from "../library";
import type { Catalog, ExerciseDetail, Preference } from "../types";

export function ExercisePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [ex, setEx] = useState<ExerciseDetail | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setEx(null);
    window.scrollTo(0, 0);
    Promise.all([api<ExerciseDetail>(`/exercises/${id}`), api<Catalog>("/catalog")])
      .then(([e, c]) => {
        setEx(e);
        setCatalog(c);
      })
      .catch((err) =>
        setError(err instanceof ApiError && err.status === 404 ? "We couldn't find that exercise." : "Couldn't load. Check your connection and refresh."),
      );
  }, [id]);

  if (error) return <div className="splash">{error}</div>;
  if (!ex || !catalog) return <div className="splash">Loading…</div>;

  const name = (list: { id: string; name: string }[], key: string) => list.find((x) => x.id === key)?.name ?? key;
  const muscle = (m: string) => name(catalog.muscles, m);
  const gear = (option: string[]) =>
    option.length === 0 ? "No equipment" : option.map((e) => name(catalog.equipment, e)).join(" + ");

  async function setPreference(next: Preference) {
    if (!ex) return;
    setSaving(true);
    try {
      await api(`/exercises/${ex.id}/preference`, { method: "PUT", body: { preference: next } });
      setEx({ ...ex, preference: next });
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="page detail">
      <header className="wizard-top">
        <button type="button" className="link" onClick={() => navigate(-1)}>
          Back
        </button>
        <span>{name(catalog.patterns, ex.pattern)}</span>
      </header>

      <div className="detail-head">
        <h1>{ex.name}</h1>
        <p className="muted">
          {ex.kind === "main" ? "Main lift" : "Accessory"}, {["", "beginner friendly", "some experience", "advanced"][ex.difficulty]}
          {ex.unilateral && ", one side at a time"}
        </p>
      </div>

      <div className="actions">
        <button
          type="button"
          className={ex.preference === "favorite" ? "primary" : "secondary"}
          disabled={saving}
          aria-pressed={ex.preference === "favorite"}
          onClick={() => setPreference(ex.preference === "favorite" ? "none" : "favorite")}
        >
          {ex.preference === "favorite" ? "★ Favorite" : "☆ Favorite"}
        </button>
        <button
          type="button"
          className="secondary"
          disabled={saving}
          aria-pressed={ex.preference === "hidden"}
          onClick={() => setPreference(ex.preference === "hidden" ? "none" : "hidden")}
        >
          {ex.preference === "hidden" ? "Show in plans again" : "Never suggest this"}
        </button>
      </div>

      {(!ex.safe || !ex.available) && (
        <ul className="advice">
          {!ex.safe && (
            <li className="warning">
              This works your {ex.injury_conflicts.map((b) => name(catalog.body_parts, b).toLowerCase()).join(" and ")},
              which you marked as injured. It won't be planned for you; try an alternative below.
            </li>
          )}
          {!ex.available && <li>Your current gym doesn't have the equipment for this one.</li>}
        </ul>
      )}

      <section className="card mm-card">
        <MuscleMap primary={ex.primary} secondary={ex.secondary} size={300} />
        <div className="mm-legend">
          <p>
            <i className="dot primary" />
            {ex.primary.map(muscle).join(", ")}
          </p>
          {ex.secondary.length > 0 && (
            <p className="muted">
              <i className="dot secondary" />
              {ex.secondary.map(muscle).join(", ")}
            </p>
          )}
        </div>
      </section>

      <section className="card">
        <h2>You'll need</h2>
        <ul className="need">
          {ex.equipment.map((option, i) => (
            <li key={i}>
              <span className="ex-art">
                <EquipmentArt id={option[0] ?? "bodyweight"} size={30} />
              </span>
              {gear(option)}
              {i < ex.equipment.length - 1 && <span className="muted"> or</span>}
            </li>
          ))}
        </ul>
      </section>

      <section className="card how">
        <h2>How to do it</h2>
        <h3>Set up</h3>
        <ul>
          {ex.setup.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
        <h3>Each rep</h3>
        <ol>
          {ex.execution.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ol>
        <h3>Breathing</h3>
        <p>{ex.breathing}</p>
      </section>

      <section className="card how">
        <h2>Common mistakes</h2>
        <ul>
          {ex.mistakes.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
        <p className="safety">{ex.safety}</p>
      </section>

      <section className="stack-tight">
        <h2>Alternatives</h2>
        <p className="muted small">Same movement and muscles, using what your gym has.</p>
        {ex.alternatives.length === 0 ? (
          <p className="muted">No alternatives at your current gym. Add equipment in the Gym tab.</p>
        ) : (
          <ul className="ex-list">
            {ex.alternatives.map((a) => (
              <li key={a.id}>
                <Link to={`/exercises/${a.id}`} className="ex-row">
                  <span className="ex-art">
                    <EquipmentArt id={artFor(a)} size={36} />
                  </span>
                  <span className="ex-text">
                    <strong>
                      {a.name}
                      {a.preference === "favorite" && <span className="star"> ★</span>}
                    </strong>
                    <small>{a.primary.map(muscle).join(", ")}</small>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="footnote">
        A training aid, not medical advice. Stop if something hurts. <Link to="/library" className="link">Library</Link>
      </p>
    </main>
  );
}
