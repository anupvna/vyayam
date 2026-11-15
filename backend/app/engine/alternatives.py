"""Exercise alternatives: "the machine's taken, what else can I do?"

Hard filters (never broken):
  - the user has the equipment for it (at least one equipment option is fully owned)
  - it doesn't load an injured area
  - the user hasn't hidden it
  - it isn't the same exercise
  - it's relevant: same movement pattern, or shares a primary muscle

Ranking, in priority order:
  1. same movement pattern
  2. same kind: a main lift is swapped for a main lift, an accessory for an accessory
  3. overlap of primary muscles (Jaccard similarity: shared / combined)
  4. same loading style: weighted for weighted, bodyweight for bodyweight
  5. user favorites first
  6. closest difficulty
  7. name, so results are fully deterministic

The spec's order is pattern -> muscles -> equipment -> difficulty. "Kind" and
"loading style" were added after checking real results: without them a heavy
deadlift's top swap was a kettlebell swing instead of a trap bar deadlift.
"""

from collections.abc import Iterable

from app.library import Exercise


def is_available(exercise: Exercise, equipment: frozenset[str]) -> bool:
    return any(set(option) <= equipment for option in exercise.equipment)


def is_safe(exercise: Exercise, injured: frozenset[str]) -> bool:
    return not (set(exercise.loads) & injured)


def is_bodyweight_only(exercise: Exercise) -> bool:
    return all(option == () for option in exercise.equipment)


def muscle_overlap(a: Exercise, b: Exercise) -> float:
    pa, pb = set(a.primary), set(b.primary)
    return len(pa & pb) / len(pa | pb)


def find_alternatives(
    target: Exercise,
    library: Iterable[Exercise],
    *,
    equipment: frozenset[str],
    injured: frozenset[str] = frozenset(),
    hidden: frozenset[str] = frozenset(),
    favorites: frozenset[str] = frozenset(),
    limit: int = 3,
) -> list[Exercise]:
    candidates = [
        c
        for c in library
        if c.id != target.id
        and c.id not in hidden
        and is_available(c, equipment)
        and is_safe(c, injured)
        and (c.pattern == target.pattern or set(c.primary) & set(target.primary))
    ]

    def rank(c: Exercise) -> tuple:
        return (
            c.pattern != target.pattern,  # False sorts first
            c.kind != target.kind,
            -muscle_overlap(c, target),
            is_bodyweight_only(c) != is_bodyweight_only(target),
            c.id not in favorites,
            abs(c.difficulty - target.difficulty),
            c.name,
        )

    return sorted(candidates, key=rank)[:limit]
