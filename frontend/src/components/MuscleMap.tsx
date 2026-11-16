// Front and back body diagram with the worked muscles filled in brass:
// solid for primary muscles, faint for secondary. Drawn for Vyayam, so no licensing
// questions. Reused later for the recovery body map.

type Shape =
  | { e: [number, number, number, number] } // ellipse cx cy rx ry
  | { p: string }; // path

// Each muscle's shapes, on a 100 x 190 figure. Back-view shapes are shifted +100 x.
const FRONT: Record<string, Shape[]> = {
  traps: [{ p: "M42 31 L50 28 L58 31 L55 34 L45 34 Z" }],
  front_delts: [{ e: [33, 38, 6, 6] }, { e: [67, 38, 6, 6] }],
  side_delts: [{ e: [28.5, 40, 3, 6] }, { e: [71.5, 40, 3, 6] }],
  chest: [{ p: "M49 35 L39 35 Q35 42 39 50 L49 50 Z" }, { p: "M51 35 L61 35 Q65 42 61 50 L51 50 Z" }],
  biceps: [{ e: [29, 53, 4, 8.5] }, { e: [71, 53, 4, 8.5] }],
  forearms: [{ e: [25.5, 74, 3.6, 10] }, { e: [74.5, 74, 3.6, 10] }],
  abs: [{ p: "M44 52 H56 V80 Q50 84 44 80 Z" }],
  obliques: [{ p: "M42 53 L38 53 Q36 66 39 80 L42 80 Z" }, { p: "M58 53 L62 53 Q64 66 61 80 L58 80 Z" }],
  quads: [{ e: [42, 110, 6.5, 18] }, { e: [58, 110, 6.5, 18] }],
  adductors: [{ e: [47.6, 102, 2, 10] }, { e: [52.4, 102, 2, 10] }],
  calves: [{ e: [42, 150, 4.5, 13] }, { e: [58, 150, 4.5, 13] }],
};

const BACK: Record<string, Shape[]> = {
  traps: [{ p: "M150 28 L160 34 L150 50 L140 34 Z" }],
  rear_delts: [{ e: [133, 38, 6, 6] }, { e: [167, 38, 6, 6] }],
  side_delts: [{ e: [128.5, 40, 3, 6] }, { e: [171.5, 40, 3, 6] }],
  upper_back: [{ p: "M142 39 L147 47 L147 52 L140 50 Z" }, { p: "M158 39 L153 47 L153 52 L160 50 Z" }],
  lats: [{ p: "M139 51 L147 54 L147 70 L141 66 Z" }, { p: "M161 51 L153 54 L153 70 L159 66 Z" }],
  triceps: [{ e: [129, 52, 4, 9] }, { e: [171, 52, 4, 9] }],
  forearms: [{ e: [125.5, 74, 3.6, 10] }, { e: [174.5, 74, 3.6, 10] }],
  lower_back: [{ p: "M144 70 H156 V82 H144 Z" }],
  glutes: [{ e: [144, 92, 6.5, 7.5] }, { e: [156, 92, 6.5, 7.5] }],
  hamstrings: [{ e: [142, 114, 6, 15] }, { e: [158, 114, 6, 15] }],
  calves: [{ e: [142, 148, 5, 13] }, { e: [158, 148, 5, 13] }],
};

// The body outline, drawn twice (front at x=0, back at x=100).
function Silhouette({ dx }: { dx: number }) {
  return (
    <g transform={`translate(${dx} 0)`} className="mm-body">
      <circle cx="50" cy="16" r="9" />
      <rect x="46" y="23" width="8" height="8" rx="2" />
      <rect x="36" y="30" width="28" height="56" rx="10" />
      <rect x="37" y="80" width="26" height="18" rx="8" />
      <rect x="24" y="33" width="10" height="31" rx="5" />
      <rect x="66" y="33" width="10" height="31" rx="5" />
      <rect x="21" y="62" width="9" height="27" rx="4.5" />
      <rect x="70" y="62" width="9" height="27" rx="4.5" />
      <rect x="36" y="92" width="13" height="41" rx="6" />
      <rect x="51" y="92" width="13" height="41" rx="6" />
      <rect x="37" y="132" width="11" height="40" rx="5" />
      <rect x="52" y="132" width="11" height="40" rx="5" />
    </g>
  );
}

function Region({ shapes, level, color }: { shapes: Shape[]; level: "primary" | "secondary"; color?: string }) {
  return (
    <g className={color ? undefined : `mm-${level}`} fill={color}>
      {shapes.map((s, i) =>
        "e" in s ? (
          <ellipse key={i} cx={s.e[0]} cy={s.e[1]} rx={s.e[2]} ry={s.e[3]} />
        ) : (
          <path key={i} d={s.p} />
        ),
      )}
    </g>
  );
}

type Props = {
  primary: string[];
  secondary: string[];
  size?: number;
  colors?: Record<string, string>; // per-muscle fill, e.g. for the recovery map
};

export function MuscleMap({ primary, secondary, size = 220, colors }: Props) {
  const layer = (ids: string[], level: "primary" | "secondary") =>
    ids.flatMap((id) => [
      FRONT[id] && <Region key={`f-${id}`} shapes={FRONT[id]} level={level} />,
      BACK[id] && <Region key={`b-${id}`} shapes={BACK[id]} level={level} />,
    ]);

  return (
    <svg
      className="muscle-map"
      viewBox="0 0 200 190"
      width={size}
      height={(size * 190) / 200}
      role="img"
      aria-label={
        colors
          ? "Recovery state of each muscle"
          : `Works ${primary.join(", ")}${secondary.length ? `; also ${secondary.join(", ")}` : ""}`
      }
    >
      <Silhouette dx={0} />
      <Silhouette dx={100} />
      {layer(secondary, "secondary")}
      {layer(primary, "primary")}
      {colors &&
        Object.entries(colors).flatMap(([id, color]) => [
          FRONT[id] && <Region key={`cf-${id}`} shapes={FRONT[id]} level="primary" color={color} />,
          BACK[id] && <Region key={`cb-${id}`} shapes={BACK[id]} level="primary" color={color} />,
        ])}
      <text x="50" y="186" textAnchor="middle">
        Front
      </text>
      <text x="150" y="186" textAnchor="middle">
        Back
      </text>
    </svg>
  );
}
