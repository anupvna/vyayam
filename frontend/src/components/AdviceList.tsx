import type { Advice } from "../types";

export function AdviceList({ advice }: { advice: Advice[] }) {
  if (advice.length === 0) return null;
  return (
    <ul className="advice">
      {advice.map((a) => (
        <li key={a.code} className={a.level}>
          {a.message}
        </li>
      ))}
    </ul>
  );
}
