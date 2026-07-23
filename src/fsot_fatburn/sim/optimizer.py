"""Protocol ranking — diet × exercise × compound grid under FSOT + physiology sim."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from ..physiology.energy import SubjectProfile
from ..interventions.diet import DIET_LIBRARY
from ..interventions.exercise import EXERCISE_LIBRARY
from ..interventions.compounds import SEED_COMPOUNDS
from .fat_cell_sim import FatBurnSimulator, SimConfig, SimResult
from ..paths import project_path


@dataclass
class ProtocolSpec:
    label: str
    diet_id: str
    exercise_ids: List[str]
    compound_ids: List[str]
    days: int = 28


# Hand-picked high-value protocols + systematic grid subset
DEFAULT_PROTOCOL_GRID: List[ProtocolSpec] = [
    ProtocolSpec("control_maintenance", "maintenance_control", ["steps_10k"], [], 28),
    ProtocolSpec("classic_cut", "moderate_deficit_balanced", ["resistance_full_45", "zone2_bike_40", "steps_10k"], ["caffeine"], 28),
    ProtocolSpec("hiit_cut", "moderate_deficit_balanced", ["resistance_full_45", "hiit_20", "steps_10k"], ["caffeine", "egcg"], 28),
    ProtocolSpec("stubborn_alpha2", "if_16_8", ["fasted_liss_yohimbine_window", "resistance_full_45", "steps_10k"], ["yohimbine", "caffeine"], 28),
    ProtocolSpec("low_carb_water", "high_protein_low_carb", ["resistance_full_45", "zone2_bike_40", "steps_10k"], ["caffeine", "berberine"], 28),
    ProtocolSpec("keto_drop", "ketogenic", ["resistance_full_45", "liss_walk_45", "steps_10k"], ["caffeine"], 28),
    ProtocolSpec("aggressive_minicut", "psmf_aggressive", ["resistance_hypertrophy_60", "steps_10k"], ["caffeine", "egcg", "capsaicin"], 14),
    ProtocolSpec("cold_thermogenic", "moderate_deficit_balanced", ["resistance_full_45", "cold_shower_exposure", "steps_10k"], ["capsaicin", "egcg", "caffeine"], 28),
    ProtocolSpec("glp1_like_intake", "moderate_deficit_balanced", ["resistance_full_45", "steps_10k"], ["semaglutide"], 28),
    ProtocolSpec("dual_agonist_like", "moderate_deficit_balanced", ["resistance_full_45", "steps_10k"], ["tirzepatide"], 28),
    ProtocolSpec("low_sodium_cut", "low_sodium_cut", ["resistance_full_45", "zone2_bike_40", "steps_10k"], ["caffeine"], 28),
    ProtocolSpec("sprint_sympathetic", "moderate_deficit_balanced", ["sprint_10", "resistance_full_45", "steps_10k"], ["caffeine", "synephrine"], 28),
    ProtocolSpec("forskolin_stack", "if_16_8", ["fasted_liss_yohimbine_window", "resistance_full_45"], ["forskolin", "caffeine", "yohimbine"], 28),
    ProtocolSpec("neat_only_deficit", "moderate_deficit_balanced", ["steps_10k"], [], 28),
    ProtocolSpec("orlistat_intake_block", "moderate_deficit_balanced", ["resistance_full_45", "steps_10k"], ["orlistat", "caffeine"], 28),
]


def _sanitize_compounds(ids: List[str]) -> List[str]:
    known = {c.id for c in SEED_COMPOUNDS}
    return [i for i in ids if i in known]


def rank_protocols(
    subject: Optional[SubjectProfile] = None,
    protocols: Optional[List[ProtocolSpec]] = None,
    days: Optional[int] = None,
) -> Dict[str, Any]:
    subject = subject or SubjectProfile()
    protocols = protocols or DEFAULT_PROTOCOL_GRID
    results = []

    for p in protocols:
        d = days or p.days
        cfg = SimConfig(
            days=d,
            subject=SubjectProfile(**subject.to_dict()),  # fresh copy
            diet_id=p.diet_id if p.diet_id in {x.id for x in DIET_LIBRARY} else "moderate_deficit_balanced",
            exercise_ids=[e for e in p.exercise_ids if e in {x.id for x in EXERCISE_LIBRARY}],
            compound_ids=_sanitize_compounds(p.compound_ids),
            label=p.label,
        )
        if not cfg.exercise_ids:
            cfg.exercise_ids = ["steps_10k"]
        sim = FatBurnSimulator(cfg)
        res = sim.run()
        s = res.summary
        # Ranking score: maximize true fat loss, penalize water-only scale tricks,
        # reward FSOT burn index, penalize extreme deficit fragility
        score = (
            s["fat_lost_kg"] * 100.0
            + s["mean_fat_burn_index"] * 15.0
            - abs(s["scale_delta_kg"] - s["fat_lost_kg"]) * 10.0  # scale vs fat mismatch
            - s["mean_water_retention_index"] * 5.0
            - max(0.0, s["mean_daily_deficit_kcal"] - 750) * 0.01  # soft penalty extreme cuts
        )
        results.append({
            "label": p.label,
            "score": score,
            "summary": s,
            "config": res.config,
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i

    out = {
        "subject": subject.to_dict(),
        "n_protocols": len(results),
        "ranking": results,
        "winner": results[0] if results else None,
        "top3": results[:3],
    }
    path = project_path("reports", "protocol_ranking.json")
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out
