"""Energy balance and subject profile (BMR / TDEE anchors + somatotype)."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from .depots import FatDepot, sex_adjust_depots
from .somatotype import SomatotypeProfile


@dataclass
class SubjectProfile:
    sex: str = "male"  # male | female | unspecified
    age_y: float = 35.0
    height_cm: float = 178.0
    weight_kg: float = 95.0
    body_fat_pct: float = 28.0
    activity_factor: float = 1.35  # sedentary 1.2 … very active 1.9
    steps_per_day: float = 6000.0
    resistance_sessions_per_week: float = 2.0
    cardio_minutes_per_week: float = 60.0
    # ectomorph | mesomorph | endomorph | ecto_meso | meso_endo | ecto_endo
    somatotype: str = "meso_endo"
    # Anthropometry / DEXA calibration (optional)
    waist_cm: Optional[float] = None
    hip_cm: Optional[float] = None
    neck_cm: Optional[float] = None
    dexa_fat_mass_kg: Optional[float] = None
    dexa_lean_mass_kg: Optional[float] = None
    dexa_vat_kg: Optional[float] = None
    body_fat_method: str = "manual"  # manual | navy | dexa | hybrid_dexa_primary
    depot_fraction_overrides: Optional[Dict[str, float]] = None
    whr: Optional[float] = None
    calibration: Optional[dict] = None

    def somatotype_profile(self) -> SomatotypeProfile:
        return SomatotypeProfile.from_id(self.somatotype)

    @property
    def fat_mass_kg(self) -> float:
        if self.dexa_fat_mass_kg is not None and self.body_fat_method.startswith("dexa"):
            return float(self.dexa_fat_mass_kg)
        if self.dexa_fat_mass_kg is not None and self.body_fat_method.startswith("hybrid"):
            return float(self.dexa_fat_mass_kg)
        return self.weight_kg * (self.body_fat_pct / 100.0)

    @property
    def lean_mass_kg(self) -> float:
        if self.dexa_lean_mass_kg is not None and self.body_fat_method in (
            "dexa", "hybrid_dexa_primary", "hybrid"
        ):
            return float(self.dexa_lean_mass_kg)
        return self.weight_kg - self.fat_mass_kg

    def bmr_mifflin_st_jeor(self) -> float:
        """kcal/day — measured-anchor formula × somatotype metabolic multiplier."""
        s = (self.sex or "").lower()
        if s.startswith("f"):
            base = 10 * self.weight_kg + 6.25 * self.height_cm - 5 * self.age_y - 161
        else:
            base = 10 * self.weight_kg + 6.25 * self.height_cm - 5 * self.age_y + 5
        # Katch-McArdle-style lean boost when DEXA lean known (blend 30%)
        if self.dexa_lean_mass_kg is not None:
            katch = 370 + 21.6 * self.dexa_lean_mass_kg
            base = 0.7 * base + 0.3 * katch
        return base * self.somatotype_profile().bmr_multiplier

    def tdee(self) -> float:
        soma = self.somatotype_profile()
        af = max(1.15, self.activity_factor + soma.activity_factor_bias)
        return self.bmr_mifflin_st_jeor() * af

    def allocate_depots(self) -> List[tuple[FatDepot, float]]:
        from .calibration import depot_fractions_from_anthropometry
        from .depots import normalize_fractions
        from dataclasses import asdict as dc_asdict

        if self.depot_fraction_overrides:
            base = self.somatotype_profile().adjust_depots(self.sex)
            by_id = {d.id: d for d in base}
            out = []
            for did, frac in self.depot_fraction_overrides.items():
                if did in by_id:
                    d = by_id[did]
                    out.append(
                        type(d)(**{**dc_asdict(d), "fraction_of_total_fat": frac})
                    )
            if out:
                depots = normalize_fractions(out)
            else:
                depots = base
        elif self.waist_cm and self.hip_cm:
            depots = depot_fractions_from_anthropometry(
                sex=self.sex,
                somatotype=self.somatotype,
                whr=self.whr or (self.waist_cm / self.hip_cm),
                vat_fraction=(
                    (self.dexa_vat_kg / self.fat_mass_kg)
                    if self.dexa_vat_kg and self.fat_mass_kg > 0
                    else None
                ),
            )
        else:
            depots = self.somatotype_profile().adjust_depots(self.sex)
        fm = self.fat_mass_kg
        return [(d, fm * d.fraction_of_total_fat) for d in depots]

    def insulin_response_multiplier(self) -> float:
        return self.somatotype_profile().insulin_response_multiplier

    def fat_storage_drive(self) -> float:
        return self.somatotype_profile().fat_storage_drive

    @classmethod
    def from_calibration_dict(cls, data: dict, **overrides) -> "SubjectProfile":
        """Build from calibrate_subject(...).to_subject_dict() output."""
        allowed = set(cls.__dataclass_fields__.keys())
        kwargs = {k: v for k, v in data.items() if k in allowed and v is not None}
        kwargs.update({k: v for k, v in overrides.items() if v is not None})
        kwargs.setdefault("age_y", data.get("age_y", 35.0))
        return cls(**kwargs)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EnergyBalance:
    """Daily energy accounting."""

    intake_kcal: float
    bmr_kcal: float
    exercise_kcal: float
    neat_kcal: float
    tef_kcal: float  # thermic effect of food ~10% intake

    @property
    def expenditure(self) -> float:
        return self.bmr_kcal + self.exercise_kcal + self.neat_kcal + self.tef_kcal

    @property
    def balance_kcal(self) -> float:
        """Positive = surplus; negative = deficit."""
        return self.intake_kcal - self.expenditure

    @property
    def deficit_kcal(self) -> float:
        """Positive means under-eating relative to expenditure."""
        return max(0.0, -self.balance_kcal)

    def expected_fat_delta_kg(self, days: float = 1.0, kcal_per_kg: float = 7700.0) -> float:
        return (self.balance_kcal * days) / kcal_per_kg

    @classmethod
    def from_subject(
        cls,
        subject: SubjectProfile,
        intake_kcal: float,
        exercise_kcal: float = 0.0,
        neat_bonus_kcal: float = 0.0,
    ) -> "EnergyBalance":
        bmr = subject.bmr_mifflin_st_jeor()
        soma = subject.somatotype_profile()
        # NEAT proxy from steps × somatotype NEAT multiplier
        neat = (
            max(0.0, (subject.steps_per_day - 3000) * 0.04) + neat_bonus_kcal
        ) * soma.neat_multiplier
        tef = 0.10 * intake_kcal
        return cls(
            intake_kcal=intake_kcal,
            bmr_kcal=bmr,
            exercise_kcal=exercise_kcal,
            neat_kcal=neat,
            tef_kcal=tef,
        )


def insulin_index_from_diet(
    *,
    carbs_g: float,
    protein_g: float,
    fat_g: float,
    meal_frequency: int = 3,
    is_fasting_window: bool = False,
    somatotype_insulin_mult: float = 1.0,
    meal_insulin_index: Optional[float] = None,
) -> float:
    """0–1 systemic insulin pressure from macros and/or food-level meal index."""
    if is_fasting_window:
        return 0.12 * somatotype_insulin_mult
    if meal_insulin_index is not None:
        return max(0.05, min(0.98, meal_insulin_index * somatotype_insulin_mult))
    kcal = carbs_g * 4 + protein_g * 4 + fat_g * 9
    if kcal <= 0:
        return 0.2 * somatotype_insulin_mult
    carb_frac = (carbs_g * 4) / kcal
    idx = 0.25 + 0.55 * carb_frac + 0.05 * min(meal_frequency, 6) / 6
    return max(0.05, min(0.95, idx * somatotype_insulin_mult))
