"""Read-only reference data for the app: equipment, gym presets, body parts.

Public (no login needed): it contains nothing personal, and the app caches it for
offline use.
"""

from dataclasses import asdict

from fastapi import APIRouter

from app.catalog import BODY_PARTS, CATEGORIES, EQUIPMENT, MUSCLES, PATTERNS, PRESETS

router = APIRouter(tags=["catalog"])


@router.get("/catalog")
async def get_catalog() -> dict:
    return {
        "categories": [asdict(c) for c in CATEGORIES],
        "equipment": [asdict(e) for e in EQUIPMENT],
        "presets": [asdict(p) | {"equipment": list(p.equipment)} for p in PRESETS],
        "body_parts": [asdict(b) for b in BODY_PARTS],
        "muscles": [asdict(m) for m in MUSCLES],
        "patterns": [asdict(p) for p in PATTERNS],
    }
