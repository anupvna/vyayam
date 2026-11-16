"""The 44 coach scenarios, run on the rule-based coach (no AI) on every test run."""

import json
from pathlib import Path

from app.coach.actions import Action
from app.coach.eval import SCENARIOS, run

PERSONAS = {"lifter", "lifter_rest", "lifter_skipped", "cutter", "imperial"}
GROUPS = {"explain", "adapt", "cardio", "progress", "nutrition", "safety", "robustness"}
KEYS = {"id", "group", "persona", "message", "safety", "actions", "no_actions",
        "forbid_actions", "mention_any", "mention_none"}  # fmt: skip


def test_scenarios_are_well_formed() -> None:
    raw = json.loads((Path(__file__).parents[1] / "app/coach/scenarios.json").read_text())
    assert len(raw) == 44
    assert len({s["id"] for s in raw}) == 44
    action_types = set(Action.model_fields["type"].annotation.__args__)
    for s in raw:
        assert set(s) <= KEYS, s["id"]
        assert s["persona"] in PERSONAS and s["group"] in GROUPS
        assert set(s.get("actions", []) + s.get("forbid_actions", [])) <= action_types
    assert {s["group"] for s in raw} == GROUPS


async def test_rule_based_coach_passes_all_scenarios() -> None:
    results = await run("engine")
    assert len(results) == len(SCENARIOS) == 44
    failures = {r.scenario["id"]: r.problems for r in results if r.problems}
    assert failures == {}
