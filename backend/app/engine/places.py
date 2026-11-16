"""Training somewhere else for a day: at home on a mat, or at another of your gyms.

The day keeps its session (same muscles, same sets and effort); each exercise that
can't be done there is swapped for the closest one that can, using the same ranking
as the library's alternatives. If nothing fits (e.g. pulling with only a mat), the
exercise is dropped with a note. Pure functions.
"""

from dataclasses import replace

from app.engine.alternatives import find_alternatives, is_available, is_bodyweight_only
from app.engine.planner import DayPlan
from app.library import Exercise

MAT = frozenset({"mat"})
# A barbell squat for 6-10 reps becomes bodyweight squats for 12-20: the same effort
# needs more reps without the load.
BODYWEIGHT_REPS = (12, 20)


def substitute_day(
    day: DayPlan,
    library: dict[str, Exercise],
    *,
    equipment: frozenset[str],
    place_name: str,
    injured: frozenset[str] = frozenset(),
    hidden: frozenset[str] = frozenset(),
    favorites: frozenset[str] = frozenset(),
) -> DayPlan:
    if day.status != "planned":
        return day
    out, used, dropped = [], set(), []
    for pe in day.exercises:
        ex = library[pe.exercise_id]
        if is_available(ex, equipment):
            out.append(pe)
            used.add(ex.id)
            continue
        options = find_alternatives(
            ex,
            library.values(),
            equipment=equipment,
            injured=injured,
            hidden=hidden | used,  # don't do the same replacement twice in one session
            favorites=favorites,
            limit=1,
        )
        if not options:
            dropped.append(ex.name)
            continue
        alt = options[0]
        used.add(alt.id)
        reps = (
            BODYWEIGHT_REPS if is_bodyweight_only(alt) and not is_bodyweight_only(ex) else pe.reps
        )
        out.append(
            replace(
                pe,
                exercise_id=alt.id,
                name=alt.name,
                kind=alt.kind,
                primary=alt.primary,
                secondary=alt.secondary,
                reps=reps,
            )
        )
    notes = [f"Training at {place_name} today: exercises are swapped for ones that work there."]
    if dropped:
        notes.append(
            f"Nothing at {place_name} can replace {', '.join(dropped)}, so "
            f"{'it is' if len(dropped) == 1 else 'they are'} left out today."
        )
    return replace(day, exercises=out, notes=notes + day.notes)
