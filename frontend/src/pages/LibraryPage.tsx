// Library tab: browse and search every exercise. Favorites float to the top; exercises
// you can't do at your gym are shown dimmed.
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";

import { api } from "../api";
import { EquipmentArt } from "../components/EquipmentArt";
import { TabBar } from "../components/TabBar";
import { artFor, filterExercises, sortExercises, type LibraryFilter } from "../library";
import type { Catalog, ExerciseSummary } from "../types";

const SCOPES: { id: LibraryFilter["scope"]; label: string }[] = [
  { id: "gym", label: "At my gym" },
  { id: "favorites", label: "Favorites" },
  { id: "all", label: "Everything" },
];

export function LibraryPage() {
  const [items, setItems] = useState<ExerciseSummary[] | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState<LibraryFilter>({ query: "", muscle: null, scope: "gym" });

  useEffect(() => {
    Promise.all([api<ExerciseSummary[]>("/exercises"), api<Catalog>("/catalog")])
      .then(([e, c]) => {
        setItems(e);
        setCatalog(c);
      })
      .catch(() => setError(true));
  }, []);

  const shown = useMemo(() => (items ? sortExercises(filterExercises(items, filter)) : []), [items, filter]);
  const muscleName = (id: string) => catalog?.muscles.find((m) => m.id === id)?.name ?? id;

  if (error) return <div className="splash">Couldn't load the library. Check your connection and refresh.</div>;
  if (!items || !catalog) return <div className="splash">Loading…</div>;

  return (
    <>
      <main className="page">
        <header className="page-head">
          <div>
            <p className="greeting">{items.length} exercises</p>
            <h1>Library</h1>
          </div>
        </header>

        <input
          type="search"
          placeholder="Search exercises"
          aria-label="Search exercises"
          value={filter.query}
          onChange={(e) => setFilter({ ...filter, query: e.target.value })}
        />

        <div className="segmented" role="group" aria-label="Show">
          {SCOPES.map((s) => (
            <button
              key={s.id}
              type="button"
              aria-pressed={filter.scope === s.id}
              onClick={() => setFilter({ ...filter, scope: s.id })}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="pills scroll-row" role="group" aria-label="Muscle">
          {catalog.muscles.map((m) => (
            <button
              key={m.id}
              type="button"
              className="pill"
              aria-pressed={filter.muscle === m.id}
              onClick={() => setFilter({ ...filter, muscle: filter.muscle === m.id ? null : m.id })}
            >
              {m.name}
            </button>
          ))}
        </div>

        {shown.length === 0 ? (
          <p className="muted empty">
            {filter.scope === "favorites"
              ? "No favorites yet. Open an exercise and tap Favorite to keep it near the top."
              : "Nothing matches. Try another search or muscle."}
          </p>
        ) : (
          <ul className="ex-list">
            {shown.map((e) => (
              <li key={e.id}>
                <Link to={`/exercises/${e.id}`} className={`ex-row ${e.available ? "" : "dim"}`}>
                  <span className="ex-art">
                    <EquipmentArt id={artFor(e)} size={36} />
                  </span>
                  <span className="ex-text">
                    <strong>
                      {e.name}
                      {e.preference === "favorite" && <span className="star" aria-label="Favorite"> ★</span>}
                    </strong>
                    <small>
                      {e.primary.map(muscleName).join(", ")}
                      {!e.available && ", not at your gym"}
                      {e.available && !e.safe && ", avoid with your injury"}
                      {e.preference === "hidden" && ", hidden"}
                    </small>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
      <TabBar />
    </>
  );
}
