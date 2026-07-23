"""Dietary protocol library — macros, insulin pressure, sodium, adherence."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class DietProtocol:
    id: str
    name: str
    style: str
    # Target macros as fraction of calories (sum ~1)
    carb_frac: float
    protein_frac: float
    fat_frac: float
    calorie_offset: float  # relative to TDEE: -500 = deficit
    meal_frequency: int
    fasting_hours: float  # e.g. 16 for 16:8
    sodium_relative: float  # 0–1
    fiber_g: float
    protein_g_per_kg_lean: float
    notes: str

    def macros_grams(self, intake_kcal: float) -> dict:
        return {
            "carbs_g": (intake_kcal * self.carb_frac) / 4.0,
            "protein_g": (intake_kcal * self.protein_frac) / 4.0,
            "fat_g": (intake_kcal * self.fat_frac) / 9.0,
        }

    def to_dict(self) -> dict:
        return asdict(self)


DIET_LIBRARY: List[DietProtocol] = [
    DietProtocol(
        id="moderate_deficit_balanced",
        name="Moderate deficit, balanced macros",
        style="balanced",
        carb_frac=0.40,
        protein_frac=0.30,
        fat_frac=0.30,
        calorie_offset=-500,
        meal_frequency=3,
        fasting_hours=0,
        sodium_relative=0.5,
        fiber_g=30,
        protein_g_per_kg_lean=1.8,
        notes="Default sustainable fat-loss diet; preserves training quality.",
    ),
    DietProtocol(
        id="high_protein_low_carb",
        name="High protein, low carb",
        style="low_carb",
        carb_frac=0.15,
        protein_frac=0.40,
        fat_frac=0.45,
        calorie_offset=-500,
        meal_frequency=3,
        fasting_hours=0,
        sodium_relative=0.55,
        fiber_g=25,
        protein_g_per_kg_lean=2.2,
        notes="Lower insulin pressure; glycogen water drop early; monitor electrolytes.",
    ),
    DietProtocol(
        id="ketogenic",
        name="Ketogenic (~5–10% carb)",
        style="keto",
        carb_frac=0.08,
        protein_frac=0.25,
        fat_frac=0.67,
        calorie_offset=-400,
        meal_frequency=2,
        fasting_hours=14,
        sodium_relative=0.65,
        fiber_g=20,
        protein_g_per_kg_lean=1.6,
        notes="Strong water weight loss first 1–2 weeks; adherence variable.",
    ),
    DietProtocol(
        id="psmf_aggressive",
        name="Aggressive high-protein mini-cut",
        style="aggressive",
        carb_frac=0.20,
        protein_frac=0.50,
        fat_frac=0.30,
        calorie_offset=-900,
        meal_frequency=4,
        fasting_hours=0,
        sodium_relative=0.45,
        fiber_g=25,
        protein_g_per_kg_lean=2.4,
        notes="Fast scale drop; short duration only; higher lean-loss risk without lifting.",
    ),
    DietProtocol(
        id="if_16_8",
        name="Time-restricted 16:8 + moderate deficit",
        style="if",
        carb_frac=0.35,
        protein_frac=0.35,
        fat_frac=0.30,
        calorie_offset=-450,
        meal_frequency=2,
        fasting_hours=16,
        sodium_relative=0.5,
        fiber_g=28,
        protein_g_per_kg_lean=1.9,
        notes="Longer low-insulin window; pairs with fasted LISS.",
    ),
    DietProtocol(
        id="high_carb_recomp",
        name="High carb recomp (training fuel)",
        style="high_carb",
        carb_frac=0.50,
        protein_frac=0.30,
        fat_frac=0.20,
        calorie_offset=-250,
        meal_frequency=4,
        fasting_hours=0,
        sodium_relative=0.5,
        fiber_g=35,
        protein_g_per_kg_lean=1.8,
        notes="Supports performance; slower fat loss; glycogen holds water.",
    ),
    DietProtocol(
        id="low_sodium_cut",
        name="Moderate deficit + low sodium",
        style="low_sodium",
        carb_frac=0.40,
        protein_frac=0.30,
        fat_frac=0.30,
        calorie_offset=-500,
        meal_frequency=3,
        fasting_hours=0,
        sodium_relative=0.25,
        fiber_g=32,
        protein_g_per_kg_lean=1.8,
        notes="Targets water retention confound; not a fat-ox magic bullet.",
    ),
    DietProtocol(
        id="maintenance_control",
        name="Maintenance control (no deficit)",
        style="control",
        carb_frac=0.45,
        protein_frac=0.25,
        fat_frac=0.30,
        calorie_offset=0,
        meal_frequency=3,
        fasting_hours=0,
        sodium_relative=0.5,
        fiber_g=25,
        protein_g_per_kg_lean=1.4,
        notes="Baseline control arm for simulator comparisons.",
    ),
]


def get_diet(diet_id: str) -> DietProtocol:
    for d in DIET_LIBRARY:
        if d.id == diet_id:
            return d
    raise KeyError(diet_id)
