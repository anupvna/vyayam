// Pick the equipment your gym has. Start from a preset (the chosen one is marked),
// then tap the illustrated tiles to match what's really there.
import type { Catalog } from "../types";
import { EquipmentArt } from "./EquipmentArt";

type Props = {
  catalog: Catalog;
  selected: string[];
  onChange: (equipment: string[]) => void;
};

const sameSet = (a: string[], b: string[]) =>
  a.length === b.length && a.every((x) => b.includes(x));

export function EquipmentPicker({ catalog, selected, onChange }: Props) {
  const chosen = new Set(selected);
  // A preset counts as chosen while your selection matches it exactly.
  const activePreset = catalog.presets.find((p) => sameSet(p.equipment, selected));

  function toggle(id: string) {
    const next = new Set(chosen);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange([...next].sort());
  }

  function setCategory(categoryId: string, on: boolean) {
    const next = new Set(chosen);
    for (const e of catalog.equipment) {
      if (e.category !== categoryId) continue;
      if (on) next.add(e.id);
      else next.delete(e.id);
    }
    onChange([...next].sort());
  }

  return (
    <div className="fields">
      <div className="presets">
        {catalog.presets.map((p) => (
          <button
            key={p.id}
            type="button"
            className="preset"
            aria-pressed={activePreset?.id === p.id}
            onClick={() => onChange([...p.equipment].sort())}
          >
            <strong>{p.name}</strong>
            <small>{p.description}</small>
          </button>
        ))}
      </div>

      <p className="picker-status">
        <span>
          {activePreset ? `${activePreset.name}` : "Custom selection"}, {chosen.size} of{" "}
          {catalog.equipment.length} items
        </span>
      </p>

      {catalog.categories.map((cat) => {
        const items = catalog.equipment.filter((e) => e.category === cat.id);
        const allOn = items.every((e) => chosen.has(e.id));
        return (
          <section key={cat.id}>
            <div className="category-head">
              <h3>{cat.name}</h3>
              <button
                type="button"
                className="link small"
                onClick={() => setCategory(cat.id, !allOn)}
              >
                {allOn ? "Clear" : "Select all"}
              </button>
            </div>
            <div className="tiles">
              {items.map((e) => (
                <button
                  key={e.id}
                  type="button"
                  className="tile"
                  aria-pressed={chosen.has(e.id)}
                  onClick={() => toggle(e.id)}
                >
                  <i className="tick" aria-hidden="true" />
                  <EquipmentArt id={e.id} size={54} />
                  <span>{e.name}</span>
                </button>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
