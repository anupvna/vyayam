"""Numbers check: a model may not invent weights, body measures or percentages.

Every number in the reply that comes with a unit (kg, lb, %, kcal) must already be in
the user's data, in what the user wrote, or be a standard plate step. Otherwise the
reply is rejected and the model is asked again (or the next provider answers).
"""

import json
import re

_WITH_UNIT = re.compile(
    r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(kg|kgs|kilos?|lbs?|pounds?|%|percent|kcal|calories)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")

# Plate jumps and the rate guidelines the app itself uses (0.5% and 1% of body weight a week).
ALWAYS_OK = frozenset({0.5, 1.0, 1.25, 2.0, 2.5, 5.0, 10.0})


def numbers_in(*sources: object) -> set[float]:
    found: set[float] = set()
    for s in sources:
        text = s if isinstance(s, str) else json.dumps(s, default=str)
        found.update(float(n) for n in _NUMBER.findall(text))
    return found


def _close(x: float, known: set[float]) -> bool:
    return any(abs(x - k) <= max(0.15, 0.005 * k) for k in known)


def ungrounded(reply: str, known: set[float]) -> list[str]:
    """The unit-carrying numbers in `reply` that aren't backed by `known`."""
    bad = []
    for m in _WITH_UNIT.finditer(reply):
        value = float(m.group(1).replace(",", "."))
        if value in ALWAYS_OK or _close(value, known):
            continue
        bad.append(m.group(0))
    return bad
