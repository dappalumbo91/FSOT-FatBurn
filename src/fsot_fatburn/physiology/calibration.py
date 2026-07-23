"""
Subject calibration from waist / hips / neck / height and optional DEXA.

Methods
-------
1. US Navy circumference body-fat (Hodgdon / Becket class)
2. DEXA fat mass / lean mass / optional VAT mass
3. Waist-hip ratio → visceral depot bias
4. Android/gynoid ratio (if provided) → trunk vs gluteofemoral mass
5. Suggest somatotype from BF% + WHR

All outputs feed SubjectProfile depot overrides and body composition fields.
FSOT seeds remain fixed — this is anthropometric routing.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any, Tuple

from ..paths import project_path, ensure_dirs
from .depots import FatDepot, sex_adjust_depots, normalize_fractions, DEFAULT_DEPOTS
from .somatotype import SomatotypeProfile, list_somatotypes
from dataclasses import asdict as dc_asdict


def cm_to_inches(cm: float) -> float:
    return cm / 2.54


def navy_body_fat_pct(
    *,
    sex: str,
    height_cm: float,
    neck_cm: float,
    waist_cm: float,
    hip_cm: Optional[float] = None,
) -> float:
    """
    US Navy method. Returns body fat percent.
    Male uses abdomen (waist) and neck; female uses waist, hip, neck.
    """
    h = cm_to_inches(height_cm)
    n = cm_to_inches(neck_cm)
    w = cm_to_inches(waist_cm)
    s = (sex or "male").lower()

    if s.startswith("f"):
        if hip_cm is None:
            raise ValueError("hip_cm required for female Navy BF%")
        hip = cm_to_inches(hip_cm)
        # BF% = 163.205*log10(waist+hip-neck) - 97.684*log10(height) - 78.387
        val = w + hip - n
        if val <= 0 or h <= 0:
            raise ValueError("invalid circumference geometry for Navy BF")
        bf = 163.205 * math.log10(val) - 97.684 * math.log10(h) - 78.387
    else:
        # BF% = 86.010*log10(abdomen-neck) - 70.041*log10(height) + 36.76
        val = w - n
        if val <= 0 or h <= 0:
            raise ValueError("waist must exceed neck for male Navy BF")
        bf = 86.010 * math.log10(val) - 70.041 * math.log10(h) + 36.76

    return max(3.0, min(60.0, bf))


def waist_hip_ratio(waist_cm: float, hip_cm: float) -> float:
    if hip_cm <= 0:
        raise ValueError("hip_cm must be positive")
    return waist_cm / hip_cm


def suggest_somatotype(
    *,
    sex: str,
    body_fat_pct: float,
    whr: Optional[float] = None,
    lean_mass_kg: Optional[float] = None,
    height_cm: Optional[float] = None,
) -> str:
    """
    Heuristic somatotype label from composition (not photographic somatotyping).
    """
    s = (sex or "male").lower()
    # FFMI-like if lean + height available
    ffmi = None
    if lean_mass_kg and height_cm and height_cm > 0:
        h_m = height_cm / 100.0
        ffmi = lean_mass_kg / (h_m ** 2)

    if s.startswith("f"):
        low, mid, high = 22.0, 30.0, 38.0
    else:
        low, mid, high = 12.0, 20.0, 28.0

    central = whr is not None and (
        (whr >= 0.90 and not s.startswith("f")) or (whr >= 0.85 and s.startswith("f"))
    )

    if body_fat_pct <= low and (ffmi is None or ffmi < 20):
        return "ectomorph" if not central else "ecto_endo"
    if body_fat_pct <= mid and ffmi is not None and ffmi >= 20:
        return "mesomorph"
    if body_fat_pct <= mid:
        return "meso_endo" if central else "mesomorph"
    if body_fat_pct <= high:
        return "meso_endo" if (ffmi is not None and ffmi >= 19) else "endomorph"
    return "endomorph"


def depot_fractions_from_anthropometry(
    *,
    sex: str,
    somatotype: str,
    whr: Optional[float] = None,
    android_gynoid_ratio: Optional[float] = None,
    vat_fraction: Optional[float] = None,
) -> List[FatDepot]:
    """
    Bias depot mass shares using WHR / android:gynoid / VAT fraction.
    """
    soma = SomatotypeProfile.from_id(somatotype)
    depots = soma.adjust_depots(sex)
    # work as mutable dicts
    fracs = {d.id: d.fraction_of_total_fat for d in depots}
    by_id = {d.id: d for d in depots}

    # WHR: high → more visceral + abdominal; low → gluteofemoral
    if whr is not None:
        s = (sex or "male").lower()
        # center thresholds
        thr = 0.85 if s.startswith("f") else 0.90
        # delta in [-1, 1]
        delta = max(-1.0, min(1.0, (whr - thr) / 0.15))
        # shift mass from gluteofemoral toward visceral/abdominal
        shift = 0.06 * delta  # up to ±6% of total fat mass share
        if "subq_gluteofemoral" in fracs and "visceral_omental" in fracs:
            take = min(fracs["subq_gluteofemoral"] * 0.4, abs(shift))
            if shift > 0:
                fracs["subq_gluteofemoral"] -= take
                fracs["visceral_omental"] += take * 0.45
                fracs["subq_abdominal"] = fracs.get("subq_abdominal", 0) + take * 0.40
                fracs["subq_back_flanks"] = fracs.get("subq_back_flanks", 0) + take * 0.15
            else:
                take = min(fracs.get("visceral_omental", 0) * 0.4, abs(shift))
                fracs["visceral_omental"] -= take * 0.5
                fracs["subq_abdominal"] = max(0.02, fracs.get("subq_abdominal", 0) - take * 0.3)
                fracs["subq_gluteofemoral"] += take * 0.8

    if android_gynoid_ratio is not None and android_gynoid_ratio > 0:
        # >1 android (trunk); <1 gynoid (hips)
        ag = math.log(android_gynoid_ratio)
        ag = max(-0.8, min(0.8, ag))
        shift = 0.05 * ag
        if shift > 0:
            take = min(fracs.get("subq_gluteofemoral", 0) * 0.35, shift)
            fracs["subq_gluteofemoral"] = fracs.get("subq_gluteofemoral", 0) - take
            fracs["subq_abdominal"] = fracs.get("subq_abdominal", 0) + take * 0.6
            fracs["visceral_omental"] = fracs.get("visceral_omental", 0) + take * 0.4
        else:
            take = min(fracs.get("subq_abdominal", 0) * 0.3, abs(shift))
            fracs["subq_abdominal"] -= take
            fracs["subq_gluteofemoral"] = fracs.get("subq_gluteofemoral", 0) + take

    if vat_fraction is not None:
        # Force visceral share toward measured VAT fraction of total fat
        vat = max(0.02, min(0.35, vat_fraction))
        current = fracs.get("visceral_omental", 0.1)
        diff = vat - current
        fracs["visceral_omental"] = vat
        # take/give from abdominal primarily
        fracs["subq_abdominal"] = max(0.05, fracs.get("subq_abdominal", 0.2) - diff)

    # rebuild FatDepot list
    out = []
    for d in depots:
        out.append(FatDepot(**{**dc_asdict(d), "fraction_of_total_fat": max(0.01, fracs[d.id])}))
    return normalize_fractions(out)


@dataclass
class Anthropometry:
    sex: str
    age_y: float
    height_cm: float
    weight_kg: float
    waist_cm: Optional[float] = None
    hip_cm: Optional[float] = None
    neck_cm: Optional[float] = None
    # DEXA
    dexa_fat_mass_kg: Optional[float] = None
    dexa_lean_mass_kg: Optional[float] = None
    dexa_vat_kg: Optional[float] = None  # visceral adipose tissue mass if reported
    dexa_android_pct: Optional[float] = None
    dexa_gynoid_pct: Optional[float] = None
    # manual override
    body_fat_pct_manual: Optional[float] = None
    somatotype_override: Optional[str] = None
    activity_factor: float = 1.35
    steps_per_day: float = 6000.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CalibrationResult:
    method: str  # navy | dexa | hybrid | manual
    sex: str
    height_cm: float
    weight_kg: float
    body_fat_pct: float
    fat_mass_kg: float
    lean_mass_kg: float
    whr: Optional[float]
    vat_fraction: Optional[float]
    somatotype: str
    somatotype_suggested: str
    depot_fractions: Dict[str, float]
    navy_bf_pct: Optional[float]
    dexa_bf_pct: Optional[float]
    ffmi: Optional[float]
    notes: List[str] = field(default_factory=list)
    anthropometry: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_subject_dict(self) -> dict:
        """Fields mergeable into SubjectProfile."""
        return {
            "sex": self.sex,
            "height_cm": self.height_cm,
            "weight_kg": self.weight_kg,
            "body_fat_pct": self.body_fat_pct,
            "somatotype": self.somatotype,
            "waist_cm": self.anthropometry.get("waist_cm"),
            "hip_cm": self.anthropometry.get("hip_cm"),
            "neck_cm": self.anthropometry.get("neck_cm"),
            "dexa_fat_mass_kg": self.anthropometry.get("dexa_fat_mass_kg"),
            "dexa_lean_mass_kg": self.anthropometry.get("dexa_lean_mass_kg"),
            "dexa_vat_kg": self.anthropometry.get("dexa_vat_kg"),
            "body_fat_method": self.method,
            "depot_fraction_overrides": self.depot_fractions,
            "whr": self.whr,
            "calibration": {
                "ffmi": self.ffmi,
                "vat_fraction": self.vat_fraction,
                "navy_bf_pct": self.navy_bf_pct,
                "dexa_bf_pct": self.dexa_bf_pct,
                "somatotype_suggested": self.somatotype_suggested,
                "notes": self.notes,
            },
        }


def calibrate_subject(anthro: Anthropometry) -> CalibrationResult:
    notes: List[str] = []
    navy_bf = None
    dexa_bf = None
    whr = None
    vat_frac = None
    android_gynoid = None

    if anthro.waist_cm and anthro.hip_cm:
        whr = waist_hip_ratio(anthro.waist_cm, anthro.hip_cm)

    if anthro.dexa_android_pct and anthro.dexa_gynoid_pct and anthro.dexa_gynoid_pct > 0:
        android_gynoid = anthro.dexa_android_pct / anthro.dexa_gynoid_pct

    # Navy
    if anthro.waist_cm and anthro.neck_cm:
        try:
            navy_bf = navy_body_fat_pct(
                sex=anthro.sex,
                height_cm=anthro.height_cm,
                neck_cm=anthro.neck_cm,
                waist_cm=anthro.waist_cm,
                hip_cm=anthro.hip_cm,
            )
            notes.append(f"Navy BF% = {navy_bf:.2f}")
        except ValueError as e:
            notes.append(f"Navy BF skipped: {e}")

    # DEXA
    fat_mass = None
    lean_mass = None
    if anthro.dexa_fat_mass_kg is not None:
        fat_mass = anthro.dexa_fat_mass_kg
        if anthro.dexa_lean_mass_kg is not None:
            lean_mass = anthro.dexa_lean_mass_kg
        else:
            lean_mass = anthro.weight_kg - fat_mass
        dexa_bf = 100.0 * fat_mass / max(anthro.weight_kg, 1e-6)
        notes.append(f"DEXA BF% = {dexa_bf:.2f} (FM={fat_mass:.2f} kg)")
        if anthro.dexa_vat_kg is not None and fat_mass > 0:
            vat_frac = max(0.02, min(0.4, anthro.dexa_vat_kg / fat_mass))
            notes.append(f"VAT fraction of fat = {vat_frac:.3f}")

    # Resolve BF%
    method = "manual"
    if anthro.body_fat_pct_manual is not None:
        bf = anthro.body_fat_pct_manual
        method = "manual"
        fat_mass = anthro.weight_kg * bf / 100.0
        lean_mass = anthro.weight_kg - fat_mass
        notes.append("Using manual BF%")
    elif dexa_bf is not None and navy_bf is not None:
        # hybrid: prefer DEXA for composition, note Navy
        bf = dexa_bf
        method = "hybrid_dexa_primary"
        notes.append("Hybrid: DEXA composition primary; Navy retained for cross-check")
    elif dexa_bf is not None:
        bf = dexa_bf
        method = "dexa"
        fat_mass = fat_mass if fat_mass is not None else anthro.weight_kg * bf / 100.0
        lean_mass = lean_mass if lean_mass is not None else anthro.weight_kg - fat_mass
    elif navy_bf is not None:
        bf = navy_bf
        method = "navy"
        fat_mass = anthro.weight_kg * bf / 100.0
        lean_mass = anthro.weight_kg - fat_mass
    else:
        # fallback mid
        bf = 25.0 if not (anthro.sex or "").lower().startswith("f") else 32.0
        method = "default_fallback"
        fat_mass = anthro.weight_kg * bf / 100.0
        lean_mass = anthro.weight_kg - fat_mass
        notes.append("No Navy/DEXA/manual BF — used population fallback")

    if fat_mass is None:
        fat_mass = anthro.weight_kg * bf / 100.0
    if lean_mass is None:
        lean_mass = anthro.weight_kg - fat_mass

    h_m = anthro.height_cm / 100.0
    ffmi = lean_mass / (h_m ** 2) if h_m > 0 else None

    suggested = suggest_somatotype(
        sex=anthro.sex,
        body_fat_pct=bf,
        whr=whr,
        lean_mass_kg=lean_mass,
        height_cm=anthro.height_cm,
    )
    soma = anthro.somatotype_override or suggested
    if anthro.somatotype_override:
        notes.append(f"Somatotype override: {soma} (suggested {suggested})")
    else:
        notes.append(f"Somatotype suggested: {suggested}")

    depots = depot_fractions_from_anthropometry(
        sex=anthro.sex,
        somatotype=soma,
        whr=whr,
        android_gynoid_ratio=android_gynoid,
        vat_fraction=vat_frac,
    )
    depot_fracs = {d.id: d.fraction_of_total_fat for d in depots}

    return CalibrationResult(
        method=method,
        sex=anthro.sex,
        height_cm=anthro.height_cm,
        weight_kg=anthro.weight_kg,
        body_fat_pct=bf,
        fat_mass_kg=fat_mass,
        lean_mass_kg=lean_mass,
        whr=whr,
        vat_fraction=vat_frac,
        somatotype=soma,
        somatotype_suggested=suggested,
        depot_fractions=depot_fracs,
        navy_bf_pct=navy_bf,
        dexa_bf_pct=dexa_bf,
        ffmi=ffmi,
        notes=notes,
        anthropometry=anthro.to_dict(),
    )


def save_calibration(result: CalibrationResult, name: str = "subject") -> str:
    ensure_dirs()
    path = project_path("data", "derived", f"calibration_{name}.json")
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    # also subject-ready profile
    sub_path = project_path("data", "derived", f"subject_{name}.json")
    sub_path.write_text(json.dumps(result.to_subject_dict(), indent=2), encoding="utf-8")
    return str(path)


def load_subject_json(path: str) -> dict:
    return json.loads(open(path, encoding="utf-8").read())
