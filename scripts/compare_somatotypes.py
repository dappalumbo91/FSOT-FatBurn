#!/usr/bin/env python3
"""Compare fat-loss protocols across ectomorph / mesomorph / endomorph metabolisms."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fsot_fatburn.paths import ensure_dirs, project_path
from fsot_fatburn.physiology.energy import SubjectProfile
from fsot_fatburn.physiology.somatotype import list_somatotypes, SomatotypeProfile
from fsot_fatburn.sim.fat_cell_sim import FatBurnSimulator, SimConfig


def main() -> int:
    ensure_dirs()
    pure = ["ectomorph", "mesomorph", "endomorph", "meso_endo", "ecto_endo"]
    protocol = {
        "diet_id": "moderate_deficit_balanced",
        "exercise_ids": ["resistance_full_45", "zone2_bike_40", "steps_10k"],
        "compound_ids": ["caffeine", "egcg"],
        "days": 28,
    }
    rows = []
    for st in pure:
        sp = SomatotypeProfile.from_id(st)
        # Use type-default BF for fair metabolic comparison at same lean-ish scale
        sex = "male"
        bf = sp.suggested_body_fat_pct(sex)
        # Hold weight fixed; BF differs by type default
        subject = SubjectProfile(
            sex=sex,
            age_y=35,
            height_cm=178,
            weight_kg=90.0,
            body_fat_pct=bf,
            somatotype=st,
            activity_factor=1.35,
            steps_per_day=8000,
        )
        cfg = SimConfig(
            days=protocol["days"],
            subject=subject,
            diet_id=protocol["diet_id"],
            exercise_ids=protocol["exercise_ids"],
            compound_ids=protocol["compound_ids"],
            label=f"soma_{st}",
        )
        res = FatBurnSimulator(cfg).run()
        s = res.summary
        rows.append({
            "somatotype": st,
            "name": sp.name,
            "bmr_multiplier": sp.bmr_multiplier,
            "neat_multiplier": sp.neat_multiplier,
            "insulin_response_multiplier": sp.insulin_response_multiplier,
            "body_fat_pct_start": bf,
            "bmr_kcal": s.get("bmr_kcal"),
            "fat_lost_kg": s["fat_lost_kg"],
            "scale_delta_kg": s["scale_delta_kg"],
            "mean_daily_deficit_kcal": s["mean_daily_deficit_kcal"],
            "mean_fat_burn_index": s["mean_fat_burn_index"],
            "depot_delta_kg": s["depot_delta_kg"],
        })
        print(
            f"{st:12s} BMR×{sp.bmr_multiplier:.2f}  BF={bf:4.1f}%  "
            f"fat_lost={s['fat_lost_kg']:+.3f}kg  deficit≈{s['mean_daily_deficit_kcal']:.0f}  "
            f"burn_idx={s['mean_fat_burn_index']:.3f}"
        )

    out = {
        "protocol": protocol,
        "comparison": rows,
        "known_types": list_somatotypes(),
    }
    path = project_path("reports", "somatotype_comparison.json")
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
