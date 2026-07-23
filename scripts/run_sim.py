#!/usr/bin/env python3
"""Run a single fat-burn simulation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fsot_fatburn.paths import ensure_dirs
from fsot_fatburn.physiology.energy import SubjectProfile
from fsot_fatburn.sim.fat_cell_sim import FatBurnSimulator, SimConfig, save_result


def main() -> int:
    p = argparse.ArgumentParser(description="FSOT Fat Burn simulator")
    p.add_argument("--days", type=int, default=28)
    p.add_argument("--sex", default="male")
    p.add_argument("--weight", type=float, default=95.0)
    p.add_argument("--bf", type=float, default=28.0, help="body fat percent")
    p.add_argument("--height", type=float, default=178.0)
    p.add_argument("--age", type=float, default=35.0)
    p.add_argument(
        "--somatotype",
        default="meso_endo",
        help="ectomorph|mesomorph|endomorph|ecto_meso|meso_endo|ecto_endo",
    )
    p.add_argument("--subject-json", default=None, help="path from calibrate_subject.py")
    p.add_argument("--diet", default="moderate_deficit_balanced")
    p.add_argument("--exercise", default="resistance_full_45,zone2_bike_40,steps_10k")
    p.add_argument("--compounds", default="caffeine,egcg")
    p.add_argument("--label", default="run")
    args = p.parse_args()

    ensure_dirs()
    if args.subject_json:
        import json
        data = json.loads(Path(args.subject_json).read_text(encoding="utf-8"))
        subject = SubjectProfile.from_calibration_dict(
            data,
            age_y=args.age,
            activity_factor=data.get("activity_factor", 1.35),
            steps_per_day=data.get("steps_per_day", 6000),
        )
    else:
        subject = SubjectProfile(
            sex=args.sex,
            age_y=args.age,
            height_cm=args.height,
            weight_kg=args.weight,
            body_fat_pct=args.bf,
            somatotype=args.somatotype,
        )
    cfg = SimConfig(
        days=args.days,
        subject=subject,
        diet_id=args.diet,
        exercise_ids=[x.strip() for x in args.exercise.split(",") if x.strip()],
        compound_ids=[x.strip() for x in args.compounds.split(",") if x.strip()],
        label=args.label,
    )
    result = FatBurnSimulator(cfg).run()
    path = save_result(result, args.label)
    s = result.summary
    print(json.dumps(s, indent=2))
    print(f"\nWrote {path}")
    print(
        f"Fat lost: {s['fat_lost_kg']:.3f} kg | Scale Δ: {s['scale_delta_kg']:.3f} kg | "
        f"FSOT burn index: {s['mean_fat_burn_index']:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
