"""Fixed reference data: equipment, gym presets and body parts.

This lives in code, not the database, because it changes only when the app changes
(and is then reviewed and tested like code). Users store equipment *ids*.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    id: str
    name: str


@dataclass(frozen=True)
class Equipment:
    id: str
    name: str
    category: str


CATEGORIES: tuple[Item, ...] = (
    Item("free_weights", "Free weights"),
    Item("racks_benches", "Racks & benches"),
    Item("cables", "Cables"),
    Item("machines", "Machines"),
    Item("accessories", "Bands & accessories"),
    Item("cardio", "Cardio"),
)

EQUIPMENT: tuple[Equipment, ...] = (
    # free weights
    Equipment("barbell", "Barbell + plates", "free_weights"),
    Equipment("dumbbells", "Dumbbells", "free_weights"),
    Equipment("ez_bar", "EZ curl bar", "free_weights"),
    Equipment("kettlebells", "Kettlebells", "free_weights"),
    Equipment("trap_bar", "Trap / hex bar", "free_weights"),
    # racks & benches
    Equipment("squat_rack", "Squat / power rack", "racks_benches"),
    Equipment("flat_bench", "Flat bench", "racks_benches"),
    Equipment("adjustable_bench", "Adjustable bench", "racks_benches"),
    Equipment("pull_up_bar", "Pull-up bar", "racks_benches"),
    Equipment("dip_station", "Dip station", "racks_benches"),
    Equipment("smith_machine", "Smith machine", "racks_benches"),
    # cables
    Equipment("cable_station", "Adjustable cable station", "cables"),
    Equipment("lat_pulldown", "Lat pulldown", "cables"),
    Equipment("cable_row", "Seated cable row", "cables"),
    # machines
    Equipment("leg_press", "Leg press", "machines"),
    Equipment("hack_squat", "Hack squat", "machines"),
    Equipment("leg_extension", "Leg extension", "machines"),
    Equipment("leg_curl", "Leg curl", "machines"),
    Equipment("calf_raise_machine", "Calf raise machine", "machines"),
    Equipment("hip_thrust_machine", "Hip thrust / glute machine", "machines"),
    Equipment("chest_press_machine", "Chest press machine", "machines"),
    Equipment("pec_deck", "Pec deck / rear delt fly", "machines"),
    Equipment("shoulder_press_machine", "Shoulder press machine", "machines"),
    Equipment("row_machine", "Chest-supported row machine", "machines"),
    Equipment("assisted_pull_up", "Assisted pull-up / dip machine", "machines"),
    # accessories
    Equipment("resistance_bands", "Resistance bands", "accessories"),
    Equipment("suspension_trainer", "Suspension trainer (TRX)", "accessories"),
    Equipment("ab_wheel", "Ab wheel", "accessories"),
    Equipment("medicine_ball", "Medicine ball", "accessories"),
    Equipment("plyo_box", "Plyo box / step", "accessories"),
    # cardio
    Equipment("treadmill", "Treadmill", "cardio"),
    Equipment("rower", "Rowing machine", "cardio"),
    Equipment("bike", "Exercise bike", "cardio"),
    Equipment("elliptical", "Elliptical", "cardio"),
)

EQUIPMENT_IDS: frozenset[str] = frozenset(e.id for e in EQUIPMENT)


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    description: str
    equipment: tuple[str, ...]


PRESETS: tuple[Preset, ...] = (
    Preset(
        "commercial",
        "Commercial gym",
        "A typical full gym: free weights, racks, cables and machines.",
        tuple(e.id for e in EQUIPMENT),
    ),
    Preset(
        "home",
        "Home gym",
        "Dumbbells, a bench, a pull-up bar and bands.",
        ("dumbbells", "adjustable_bench", "pull_up_bar", "resistance_bands", "kettlebells"),
    ),
    Preset(
        "garage",
        "Barbell garage gym",
        "A rack, barbell, bench and dumbbells.",
        ("barbell", "squat_rack", "flat_bench", "dumbbells", "pull_up_bar"),
    ),
    Preset(
        "bodyweight",
        "Bodyweight only",
        "No equipment. Bodyweight exercises are always available.",
        (),
    ),
)

BODY_PARTS: tuple[Item, ...] = (
    Item("neck", "Neck"),
    Item("shoulder", "Shoulder"),
    Item("elbow", "Elbow"),
    Item("wrist", "Wrist / hand"),
    Item("upper_back", "Upper back"),
    Item("lower_back", "Lower back"),
    Item("hip", "Hip"),
    Item("knee", "Knee"),
    Item("ankle", "Ankle / foot"),
)

BODY_PART_IDS: frozenset[str] = frozenset(b.id for b in BODY_PARTS)
