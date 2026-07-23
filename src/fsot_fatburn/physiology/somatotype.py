"""
Body type (somatotype) metabolic modifiers.

Ectomorph / mesomorph / endomorph + hybrids — applied as multipliers on
BMR, NEAT, insulin response, depot mass shares, and FSOT δψ bias.
Seeds remain fixed; these are physiological routing folds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any

from ..paths import project_path
from .depots import FatDepot, sex_adjust_depots, normalize_fractions
from dataclasses import asdict as dc_asdict


def _load_types() -> dict:
    path = project_path("data", "seed", "somatotypes.json")
    return json.loads(path.read_text(encoding="utf-8"))["types"]


PURE_KEYS = ("bmr_multiplier", "neat_multiplier", "insulin_sensitivity_multiplier",
             "insulin_response_multiplier", "fat_storage_drive", "muscle_gain_ease",
             "default_body_fat_pct_male", "default_body_fat_pct_female",
             "activity_factor_bias", "fsot_delta_psi_bias")


def resolve_somatotype(type_id: str) -> dict:
    """Return a fully resolved pure-type dict (blends expanded)."""
    types = _load_types()
    if type_id not in types:
        raise KeyError(f"Unknown somatotype: {type_id}. Known: {list(types)}")
    t = types[type_id]
    if "blend" in t:
        acc: Dict[str, float] = {k: 0.0 for k in PURE_KEYS}
        depot_acc: Dict[str, float] = {}
        notes = [t.get("description", "")]
        for base_id, w in t["blend"].items():
            base = resolve_somatotype(base_id)
            for k in PURE_KEYS:
                acc[k] += w * float(base[k])
            for dk, dv in (base.get("depot_mass_bias") or {}).items():
                depot_acc[dk] = depot_acc.get(dk, 0.0) + w * float(dv)
            notes.append(f"{w:.0%} {base_id}")
        # Fill missing depot keys toward 1.0
        out = {
            "id": type_id,
            "name": t.get("name", type_id),
            "description": t.get("description", ""),
            "blend": t["blend"],
            "depot_mass_bias": depot_acc,
            "notes": "; ".join(notes),
            **acc,
        }
        return out
    return dict(t)


@dataclass
class SomatotypeProfile:
    type_id: str
    name: str
    bmr_multiplier: float
    neat_multiplier: float
    insulin_sensitivity_multiplier: float
    insulin_response_multiplier: float
    fat_storage_drive: float
    muscle_gain_ease: float
    activity_factor_bias: float
    fsot_delta_psi_bias: float
    default_body_fat_pct_male: float
    default_body_fat_pct_female: float
    depot_mass_bias: Dict[str, float] = field(default_factory=dict)
    notes: str = ""

    @classmethod
    def from_id(cls, type_id: str) -> "SomatotypeProfile":
        t = resolve_somatotype(type_id)
        return cls(
            type_id=t["id"],
            name=t["name"],
            bmr_multiplier=float(t["bmr_multiplier"]),
            neat_multiplier=float(t["neat_multiplier"]),
            insulin_sensitivity_multiplier=float(t["insulin_sensitivity_multiplier"]),
            insulin_response_multiplier=float(t["insulin_response_multiplier"]),
            fat_storage_drive=float(t["fat_storage_drive"]),
            muscle_gain_ease=float(t["muscle_gain_ease"]),
            activity_factor_bias=float(t["activity_factor_bias"]),
            fsot_delta_psi_bias=float(t["fsot_delta_psi_bias"]),
            default_body_fat_pct_male=float(t["default_body_fat_pct_male"]),
            default_body_fat_pct_female=float(t["default_body_fat_pct_female"]),
            depot_mass_bias=dict(t.get("depot_mass_bias") or {}),
            notes=t.get("notes") or "",
        )

    def suggested_body_fat_pct(self, sex: str) -> float:
        if (sex or "").lower().startswith("f"):
            return self.default_body_fat_pct_female
        return self.default_body_fat_pct_male

    def adjust_depots(self, sex: str) -> List[FatDepot]:
        depots = sex_adjust_depots(sex)
        out = []
        for d in depots:
            bias = self.depot_mass_bias.get(d.id, 1.0)
            dd = FatDepot(**{**dc_asdict(d), "fraction_of_total_fat": d.fraction_of_total_fat * bias})
            # Endomorph-like: slightly higher α2 on lower body already in base; amplify storage
            if self.fat_storage_drive > 1.05 and d.id in (
                "subq_gluteofemoral", "subq_abdominal", "subq_back_flanks"
            ):
                dd = FatDepot(
                    **{
                        **dc_asdict(dd),
                        "alpha2_antilipolytic": dd.alpha2_antilipolytic * 1.08,
                        "insulin_sensitivity_relative": dd.insulin_sensitivity_relative * 1.05,
                    }
                )
            if self.fat_storage_drive < 0.9 and d.is_visceral:
                dd = FatDepot(
                    **{
                        **dc_asdict(dd),
                        "beta_adrenergic_sensitivity": dd.beta_adrenergic_sensitivity * 1.05,
                    }
                )
            out.append(dd)
        return normalize_fractions(out)

    def to_dict(self) -> dict:
        return asdict(self)


def list_somatotypes() -> List[str]:
    return list(_load_types().keys())
