"""
Human adipose depot map.

Regional fat differs in adrenergic receptor density, blood flow, and lipolytic
sensitivity. These are literature-ordered relative factors used as simulation
priors (not free fits to an individual subject).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class FatDepot:
    """One anatomical fat store."""

    id: str
    name: str
    region: str  # trunk | upper_body | lower_body | visceral
    fraction_of_total_fat: float  # prior mass share (sums ~1 across defaults)
    # Relative lipolytic sensitivity under catecholamines (1.0 = reference)
    beta_adrenergic_sensitivity: float
    # α2-adrenergic anti-lipolytic tone (higher = harder to mobilize; e.g. lower body)
    alpha2_antilipolytic: float
    blood_flow_relative: float
    insulin_sensitivity_relative: float
    # Visceral vs subcutaneous behavior
    is_visceral: bool
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


# Mass-share priors for a typical adult with mixed distribution (sex-averaged scaffold).
# Sex-specific redistribution is applied in SubjectProfile.scale_depots().
DEFAULT_DEPOTS: List[FatDepot] = [
    FatDepot(
        id="visceral_omental",
        name="Visceral (omental / mesenteric)",
        region="visceral",
        fraction_of_total_fat=0.12,
        beta_adrenergic_sensitivity=1.35,
        alpha2_antilipolytic=0.55,
        blood_flow_relative=1.40,
        insulin_sensitivity_relative=0.85,
        is_visceral=True,
        notes="Portal drainage; highly lipolytic; metabolic risk depot.",
    ),
    FatDepot(
        id="subq_abdominal",
        name="Subcutaneous abdomen (belly)",
        region="trunk",
        fraction_of_total_fat=0.28,
        beta_adrenergic_sensitivity=1.10,
        alpha2_antilipolytic=0.85,
        blood_flow_relative=1.00,
        insulin_sensitivity_relative=1.00,
        is_visceral=False,
        notes="Primary aesthetic/metabolic target for many protocols.",
    ),
    FatDepot(
        id="subq_chest",
        name="Subcutaneous chest / pectoral",
        region="upper_body",
        fraction_of_total_fat=0.08,
        beta_adrenergic_sensitivity=1.05,
        alpha2_antilipolytic=0.90,
        blood_flow_relative=0.95,
        insulin_sensitivity_relative=1.00,
        is_visceral=False,
        notes="Male-pattern upper body; female breast adipose separate glandular tissue.",
    ),
    FatDepot(
        id="subq_back_flanks",
        name="Flanks / lower back / love handles",
        region="trunk",
        fraction_of_total_fat=0.12,
        beta_adrenergic_sensitivity=0.95,
        alpha2_antilipolytic=1.05,
        blood_flow_relative=0.90,
        insulin_sensitivity_relative=1.05,
        is_visceral=False,
        notes="Often stubborn relative to visceral under mild deficit alone.",
    ),
    FatDepot(
        id="subq_gluteofemoral",
        name="Gluteofemoral (hips / thighs)",
        region="lower_body",
        fraction_of_total_fat=0.25,
        beta_adrenergic_sensitivity=0.70,
        alpha2_antilipolytic=1.45,
        blood_flow_relative=0.75,
        insulin_sensitivity_relative=1.15,
        is_visceral=False,
        notes="α2-rich; classically resistant; yohimbine/fasted cardio literature target.",
    ),
    FatDepot(
        id="subq_arms",
        name="Upper arms",
        region="upper_body",
        fraction_of_total_fat=0.07,
        beta_adrenergic_sensitivity=0.90,
        alpha2_antilipolytic=1.00,
        blood_flow_relative=0.85,
        insulin_sensitivity_relative=1.05,
        is_visceral=False,
        notes="Mixed; improves with systemic deficit + resistance training.",
    ),
    FatDepot(
        id="subq_face_neck",
        name="Face / neck / submental",
        region="upper_body",
        fraction_of_total_fat=0.03,
        beta_adrenergic_sensitivity=1.00,
        alpha2_antilipolytic=0.95,
        blood_flow_relative=1.10,
        insulin_sensitivity_relative=1.00,
        is_visceral=False,
        notes="Small mass; water/glycogen swings dominate short-term appearance.",
    ),
    FatDepot(
        id="im_ectopic",
        name="Intramuscular + ectopic residual",
        region="trunk",
        fraction_of_total_fat=0.05,
        beta_adrenergic_sensitivity=1.20,
        alpha2_antilipolytic=0.70,
        blood_flow_relative=1.20,
        insulin_sensitivity_relative=0.70,
        is_visceral=False,
        notes="IMTG + residual; exercise-sensitive.",
    ),
]


def depots_by_id() -> Dict[str, FatDepot]:
    return {d.id: d for d in DEFAULT_DEPOTS}


def normalize_fractions(depots: List[FatDepot]) -> List[FatDepot]:
    s = sum(d.fraction_of_total_fat for d in depots)
    if s <= 0:
        return depots
    out = []
    for d in depots:
        out.append(
            FatDepot(
                **{
                    **asdict(d),
                    "fraction_of_total_fat": d.fraction_of_total_fat / s,
                }
            )
        )
    return out


def sex_adjust_depots(sex: str) -> List[FatDepot]:
    """
    Redistribute mass shares by sex pattern (approximate adult priors).
    male: more trunk/visceral; female: more gluteofemoral.
    """
    depots = [FatDepot(**asdict(d)) for d in DEFAULT_DEPOTS]
    sex = (sex or "unspecified").lower()
    if sex.startswith("f"):
        for d in depots:
            if d.id == "subq_gluteofemoral":
                d.fraction_of_total_fat *= 1.35
            if d.id == "visceral_omental":
                d.fraction_of_total_fat *= 0.70
            if d.id == "subq_abdominal":
                d.fraction_of_total_fat *= 0.90
            if d.id == "subq_chest":
                d.fraction_of_total_fat *= 1.15  # breast adipose mass share
    elif sex.startswith("m"):
        for d in depots:
            if d.id == "visceral_omental":
                d.fraction_of_total_fat *= 1.25
            if d.id == "subq_abdominal":
                d.fraction_of_total_fat *= 1.10
            if d.id == "subq_gluteofemoral":
                d.fraction_of_total_fat *= 0.75
            if d.id == "subq_chest":
                d.fraction_of_total_fat *= 0.85
    return normalize_fractions(depots)
