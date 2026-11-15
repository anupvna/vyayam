// A session's exercises: what to do, how many sets and reps, how hard, how long to rest.
import { Link } from "react-router";

import { effortLabel, formatRest, formatSets } from "../plan";
import type { PlannedExercise } from "../types";

export function WorkoutList({ exercises }: { exercises: PlannedExercise[] }) {
  return (
    <ol className="workout">
      {exercises.map((e) => (
        <li key={e.exercise_id}>
          <Link to={`/exercises/${e.exercise_id}`} className="workout-row">
            <span className="workout-name">
              {e.name}
              {e.kind === "main" && <span className="badge">Main lift</span>}
              {e.light && <span className="badge quiet">Light today</span>}
            </span>
            <span className="workout-sets">{formatSets(e)}</span>
            <span className="workout-meta">
              {effortLabel(e.rir)}. Rest {formatRest(e.rest_seconds)}.
            </span>
          </Link>
        </li>
      ))}
    </ol>
  );
}
