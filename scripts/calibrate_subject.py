#!/usr/bin/env python3
"""
Calibrate a subject from waist/hips/neck (Navy) and/or DEXA, then optional sim.

Examples
--------
  # Navy BF + WHR depot map
  python scripts/calibrate_subject.py --sex male --height 178 --weight 95 \\
      --waist 102 --hip 108 --neck 40 --name damian

  # DEXA primary
  python scripts/calibrate_subject.py --sex male --height 178 --weight 95 \\
      --dexa-fat 28.5 --dexa-lean 66.5 --dexa-vat 3.2 --waist 102 --hip 108 --name damian

  # Run 28-day sim on calibrated subject
  python scripts/calibrate_subject.py ... --run-sim --days 28
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fsot_fatburn.paths import ensure_dirs, project_path
from fsot_fatburn.physiology.calibration import (
    Anthropometry,
    calibrate_subject,
    save_calibration,
)
from fsot_fatburn.physiology.energy import SubjectProfile
from fsot_fatburn.sim.fat_cell_sim import FatBurnSimulator, SimConfig, save_result


def main() -> int:
    p = argparse.ArgumentParser(description="FSOT Fat Burn subject calibration")
    p.add_argument("--name", default="subject")
    p.add_argument("--sex", default="male")
    p.add_argument("--age", type=float, default=35.0)
    p.add_argument("--height", type=float, required=True, help="height cm")
    p.add_argument("--weight", type=float, required=True, help="weight kg")
    p.add_argument("--waist", type=float, default=None, help="waist cm")
    p.add_argument("--hip", type=float, default=None, help="hip cm")
    p.add_argument("--neck", type=float, default=None, help="neck cm")
    p.add_argument("--bf-manual", type=float, default=None, help="manual body fat %")
    p.add_argument("--dexa-fat", type=float, default=None, help="DEXA fat mass kg")
    p.add_argument("--dexa-lean", type=float, default=None, help="DEXA lean mass kg")
    p.add_argument("--dexa-vat", type=float, default=None, help="DEXA VAT mass kg")
    p.add_argument("--android", type=float, default=None, help="DEXA android %")
    p.add_argument("--gynoid", type=float, default=None, help="DEXA gynoid %")
    p.add_argument("--somatotype", default=None, help="override suggested somatotype")
    p.add_argument("--activity", type=float, default=1.35)
    p.add_argument("--steps", type=float, default=7000)
    p.add_argument("--run-sim", action="store_true")
    p.add_argument("--days", type=int, default=28)
    p.add_argument("--diet", default="moderate_deficit_balanced")
    p.add_argument("--exercise", default="resistance_full_45,zone2_bike_40,steps_10k")
    p.add_argument("--compounds", default="caffeine,egcg")
    args = p.parse_args()

    ensure_dirs()
    anthro = Anthropometry(
        sex=args.sex,
        age_y=args.age,
        height_cm=args.height,
        weight_kg=args.weight,
        waist_cm=args.waist,
        hip_cm=args.hip,
        neck_cm=args.neck,
        dexa_fat_mass_kg=args.dexa_fat,
        dexa_lean_mass_kg=args.dexa_lean,
        dexa_vat_kg=args.dexa_vat,
        dexa_android_pct=args.android,
        dexa_gynoid_pct=args.gynoid,
        body_fat_pct_manual=args.bf_manual,
        somatotype_override=args.somatotype,
        activity_factor=args.activity,
        steps_per_day=args.steps,
    )
    result = calibrate_subject(anthro)
    path = save_calibration(result, args.name)

    print("=== SUBJECT CALIBRATION ===")
    print(f"method:        {result.method}")
    print(f"body fat:      {result.body_fat_pct:.2f}%")
    print(f"fat mass:      {result.fat_mass_kg:.2f} kg")
    print(f"lean mass:     {result.lean_mass_kg:.2f} kg")
    if result.navy_bf_pct is not None:
        print(f"Navy BF:       {result.navy_bf_pct:.2f}%")
    if result.dexa_bf_pct is not None:
        print(f"DEXA BF:       {result.dexa_bf_pct:.2f}%")
    if result.whr is not None:
        print(f"WHR:           {result.whr:.3f}")
    if result.ffmi is not None:
        print(f"FFMI:          {result.ffmi:.2f}")
    if result.vat_fraction is not None:
        print(f"VAT / fat:     {result.vat_fraction:.3f}")
    print(f"somatotype:    {result.somatotype} (suggested {result.somatotype_suggested})")
    print("depot fractions:")
    for k, v in sorted(result.depot_fractions.items(), key=lambda x: -x[1]):
        print(f"  {k:28s} {v*100:5.2f}%  → {result.fat_mass_kg*v:.2f} kg")
    print("notes:")
    for n in result.notes:
        print(f"  - {n}")
    print(f"\nWrote {path}")
    print(f"Subject JSON: data/derived/subject_{args.name}.json")

    if args.run_sim:
        sub = SubjectProfile.from_calibration_dict(
            result.to_subject_dict(),
            age_y=args.age,
            activity_factor=args.activity,
            steps_per_day=args.steps,
        )
        cfg = SimConfig(
            days=args.days,
            subject=sub,
            diet_id=args.diet,
            exercise_ids=[x.strip() for x in args.exercise.split(",") if x.strip()],
            compound_ids=[x.strip() for x in args.compounds.split(",") if x.strip()],
            label=f"calibrated_{args.name}",
        )
        sim = FatBurnSimulator(cfg).run()
        out = save_result(sim, f"calibrated_{args.name}")
        s = sim.summary
        print("\n=== SIM ON CALIBRATED SUBJECT ===")
        print(json.dumps({
            "fat_lost_kg": s["fat_lost_kg"],
            "scale_delta_kg": s["scale_delta_kg"],
            "somatotype": s["somatotype"],
            "bmr_kcal": s.get("bmr_kcal"),
            "depot_delta_kg": s["depot_delta_kg"],
            "mean_fat_burn_index": s["mean_fat_burn_index"],
        }, indent=2))
        print(f"Report: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
