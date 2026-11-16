"""Cool-down stretches matched to the muscles a session trained. Pure functions.

Static stretches after training feel good and help you wind down; they're optional.
Holds are 30 seconds (each side where it applies). All descriptions are original.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Stretch:
    id: str
    name: str
    muscles: tuple[str, ...]
    seconds: int
    each_side: bool
    how: str


STRETCHES: tuple[Stretch, ...] = (
    Stretch(
        "doorway_chest",
        "Doorway chest stretch",
        ("chest", "front_delts"),
        30,
        True,
        "Forearm on a door frame at shoulder height, step through until you feel the chest open.",
    ),
    Stretch(
        "cross_body_shoulder",
        "Cross-body shoulder stretch",
        ("rear_delts", "side_delts"),
        30,
        True,
        "Pull one arm across your chest with the other, keeping the shoulder down.",
    ),
    Stretch(
        "overhead_triceps",
        "Overhead triceps stretch",
        ("triceps",),
        30,
        True,
        "Reach one hand down your back, gently press the elbow with the other hand.",
    ),
    Stretch(
        "wall_biceps",
        "Wall biceps stretch",
        ("biceps", "forearms"),
        30,
        True,
        "Palm flat on a wall behind you at shoulder height, turn your body away.",
    ),
    Stretch(
        "childs_pose",
        "Child's pose",
        ("lats", "lower_back", "upper_back"),
        45,
        False,
        "Kneel, sit back on your heels and walk your hands forward, chest toward the mat.",
    ),
    Stretch(
        "cat_cow",
        "Cat-cow",
        ("lower_back", "upper_back", "abs"),
        45,
        False,
        "On hands and knees, slowly round your back up, then let it dip, with your breath.",
    ),
    Stretch(
        "upper_trap",
        "Neck side stretch",
        ("traps",),
        30,
        True,
        "Tilt your ear toward your shoulder; rest the other hand behind your back.",
    ),
    Stretch(
        "cobra",
        "Cobra",
        ("abs", "obliques"),
        30,
        False,
        "Lie face down, hands under shoulders, gently press your chest up, hips on the mat.",
    ),
    Stretch(
        "lying_twist",
        "Lying spinal twist",
        ("obliques", "lower_back", "glutes"),
        30,
        True,
        "On your back, drop bent knees to one side, arms out, shoulders on the mat.",
    ),
    Stretch(
        "kneeling_hip_flexor",
        "Kneeling hip flexor stretch",
        ("quads",),
        30,
        True,
        "Half-kneel, tuck your hips under and shift forward until the front of the hip stretches.",
    ),
    Stretch(
        "standing_quad",
        "Standing quad stretch",
        ("quads",),
        30,
        True,
        "Hold one ankle behind you, knees together, hips pushed slightly forward.",
    ),
    Stretch(
        "seated_hamstring",
        "Seated hamstring stretch",
        ("hamstrings", "calves"),
        30,
        True,
        "Sit with one leg straight, hinge forward from the hips with a long back.",
    ),
    Stretch(
        "figure_four",
        "Figure-four glute stretch",
        ("glutes",),
        30,
        True,
        "On your back, cross an ankle over the opposite knee and pull that thigh toward you.",
    ),
    Stretch(
        "butterfly",
        "Butterfly stretch",
        ("adductors",),
        30,
        False,
        "Sit with soles of your feet together, let the knees fall out, sit tall.",
    ),
    Stretch(
        "wall_calf",
        "Wall calf stretch",
        ("calves",),
        30,
        True,
        "Hands on a wall, one leg back with the heel down and the knee straight.",
    ),
)
STRETCH_BY_ID = {s.id: s for s in STRETCHES}


def cooldown(muscles: list[str], limit: int = 6) -> list[Stretch]:
    """Stretches for the given muscles (most important first), without repeats."""
    picked: list[Stretch] = []
    for m in muscles:
        for s in STRETCHES:
            if m in s.muscles and s not in picked:
                picked.append(s)
                break
        if len(picked) == limit:
            break
    return picked


def minutes(stretches: list[Stretch]) -> int:
    seconds = sum(s.seconds * (2 if s.each_side else 1) + 10 for s in stretches)
    return max(1, round(seconds / 60))
