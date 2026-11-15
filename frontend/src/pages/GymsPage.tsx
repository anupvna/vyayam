// Gym tab: switch the gym you're training at, edit its equipment, add or delete gyms.
import { useEffect, useState } from "react";

import { ApiError, api } from "../api";
import { EquipmentArt } from "../components/EquipmentArt";
import { EquipmentPicker } from "../components/EquipmentPicker";
import { TabBar } from "../components/TabBar";
import type { Catalog, Gym } from "../types";

type Draft = { id: string | null; name: string; equipment: string[] };

export function GymsPage() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [gyms, setGyms] = useState<Gym[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api<Catalog>("/catalog"), api<Gym[]>("/gyms")])
      .then(([c, g]) => {
        setCatalog(c);
        setGyms(g);
      })
      .catch(() => setError("Couldn't load your gyms. Check your connection and refresh."));
  }, []);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setGyms(await api<Gym[]>("/gyms"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const saveDraft = () =>
    run(async () => {
      if (!draft) return;
      await api(draft.id ? `/gyms/${draft.id}` : "/gyms", {
        method: draft.id ? "PUT" : "POST",
        body: { name: draft.name, equipment: draft.equipment },
      });
      setDraft(null);
    });

  if (!catalog) return <div className="splash">{error ?? "Loading…"}</div>;

  if (draft) {
    return (
      <main className="wizard">
        <header className="wizard-head">
          <div className="wizard-top">
            <span>{draft.id ? "Edit gym" : "New gym"}</span>
            <button className="link" onClick={() => setDraft(null)}>
              Cancel
            </button>
          </div>
          <h1>{draft.name.trim() || "Your gym"}</h1>
          <p>Tap everything this gym has. Your plan will only use this equipment.</p>
        </header>
        <section className="fields">
          <label>
            Name this gym
            <input
              value={draft.name}
              maxLength={60}
              placeholder="e.g. Home"
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          </label>
          <EquipmentPicker
            catalog={catalog}
            selected={draft.equipment}
            onChange={(equipment) => setDraft({ ...draft, equipment })}
          />
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
        </section>
        <nav className="wizard-nav">
          <button className="primary" disabled={busy || !draft.name.trim()} onClick={saveDraft}>
            {busy ? "Saving…" : "Save gym"}
          </button>
        </nav>
      </main>
    );
  }

  return (
    <>
      <main className="page">
        <header className="page-head">
          <div>
            <p className="greeting">Where you train</p>
            <h1>Your gyms</h1>
          </div>
        </header>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {gyms.map((g) => (
          <section key={g.id} className="card gym-card" data-active={g.is_active}>
            <div className="card-head">
              <div>
                <h2>{g.name}</h2>
                <span className="muted small">{g.equipment.length} pieces of equipment</span>
              </div>
              {g.is_active ? (
                <span className="badge">Training here</span>
              ) : (
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => run(() => api(`/gyms/${g.id}/activate`, { method: "POST" }))}
                >
                  Train here
                </button>
              )}
            </div>
            {g.equipment.length > 0 && (
              <div className="gear">
                {g.equipment.slice(0, 5).map((id) => (
                  <span key={id}>
                    <EquipmentArt id={id} size={34} />
                  </span>
                ))}
                {g.equipment.length > 5 && <span className="more">+{g.equipment.length - 5}</span>}
              </div>
            )}
            <div className="actions">
              <button className="link" onClick={() => setDraft({ id: g.id, name: g.name, equipment: g.equipment })}>
                Edit equipment
              </button>
              <button
                className="link danger"
                disabled={busy}
                onClick={() => {
                  if (window.confirm(`Delete "${g.name}"? This can't be undone.`)) {
                    void run(() => api(`/gyms/${g.id}`, { method: "DELETE" }));
                  }
                }}
              >
                Delete
              </button>
            </div>
          </section>
        ))}

        <button
          className="primary"
          onClick={() => setDraft({ id: null, name: "", equipment: [] })}
          disabled={gyms.length >= 10}
        >
          Add a gym
        </button>
      </main>
      <TabBar />
    </>
  );
}
