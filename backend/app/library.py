"""The exercise library: loaded once from app/data/exercises.json and validated.

Like the equipment catalog, the library is versioned data that ships with the code,
so every change is reviewed and tested. Validation runs at import time: a typo in an
equipment id or muscle name stops the app from starting rather than silently
producing wrong plans.

Sources (see docs/LICENSES.md): exercise facts are cross-checked against
free-exercise-db (public domain); all cues, mistakes and safety notes are written
for Vyayam.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.catalog import BODY_PART_IDS, EQUIPMENT_IDS, MUSCLE_IDS, PATTERN_IDS

DATA_FILE = Path(__file__).resolve().parent / "data" / "exercises.json"


class Exercise(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    pattern: str
    kind: Literal["main", "accessory"]  # main = heavy compound, trimmed last
    primary: tuple[str, ...] = Field(min_length=1)
    secondary: tuple[str, ...]
    # Any ONE of these option sets is enough. [] means "bodyweight, always available".
    equipment: tuple[tuple[str, ...], ...] = Field(min_length=1)
    difficulty: int = Field(ge=1, le=3)
    unilateral: bool
    loads: tuple[str, ...]  # joints/areas this exercise stresses (for injury exclusion)
    setup: tuple[str, ...] = Field(min_length=1)
    execution: tuple[str, ...] = Field(min_length=1)
    breathing: str
    mistakes: tuple[str, ...] = Field(min_length=1)
    safety: str
    source: str | None

    @field_validator("pattern")
    @classmethod
    def _pattern(cls, v: str) -> str:
        if v not in PATTERN_IDS:
            raise ValueError(f"unknown pattern {v!r}")
        return v

    @field_validator("primary", "secondary")
    @classmethod
    def _muscles(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        unknown = set(v) - MUSCLE_IDS
        if unknown:
            raise ValueError(f"unknown muscles {sorted(unknown)}")
        return v

    @field_validator("equipment")
    @classmethod
    def _equipment(cls, v: tuple[tuple[str, ...], ...]) -> tuple[tuple[str, ...], ...]:
        unknown = {e for option in v for e in option} - EQUIPMENT_IDS
        if unknown:
            raise ValueError(f"unknown equipment {sorted(unknown)}")
        return v

    @field_validator("loads")
    @classmethod
    def _loads(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        unknown = set(v) - BODY_PART_IDS
        if unknown:
            raise ValueError(f"unknown body parts {sorted(unknown)}")
        return v

    @model_validator(mode="after")
    def _no_overlap(self) -> "Exercise":
        if set(self.primary) & set(self.secondary):
            raise ValueError(f"{self.id}: a muscle can't be both primary and secondary")
        return self


@lru_cache
def load_library() -> dict[str, Exercise]:
    """All exercises by id. Cached: the file is read once per process."""
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    exercises = [Exercise.model_validate(item) for item in raw]
    by_id = {e.id: e for e in exercises}
    if len(by_id) != len(exercises):
        raise ValueError("duplicate exercise ids in exercises.json")
    return by_id
