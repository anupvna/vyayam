// Rest timer that appears after each logged set. Counts down using the clock (not by
// counting ticks), so it stays correct if the phone locks or the tab sleeps.
import { useEffect, useState } from "react";

import { formatClock } from "../logging";

type Props = { endsAt: number; total: number; onDone: () => void };

export function RestTimer({ endsAt, total, onDone }: Props) {
  const [now, setNow] = useState(() => Date.now());
  const left = (endsAt - now) / 1000;

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (left <= 0) {
      navigator.vibrate?.([200, 100, 200]);
      onDone();
    }
  }, [left, onDone]);

  return (
    <div className="rest-timer" role="timer" aria-live="polite">
      <div className="rest-bar" style={{ width: `${Math.max(0, Math.min(100, (left / total) * 100))}%` }} />
      <span>Rest</span>
      <b>{formatClock(left)}</b>
      <button type="button" className="link" onClick={onDone}>
        Skip rest
      </button>
    </div>
  );
}
