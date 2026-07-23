#!/usr/bin/env python3
"""Rank diet/exercise/compound protocols under the FSOT fat-cell simulator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fsot_fatburn.paths import ensure_dirs
from fsot_fatburn.physiology.energy import SubjectProfile
from fsot_fatburn.sim.optimizer import rank_protocols


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sex", default="male")
    p.add_argument("--weight", type=float, default=95.0)
    p.add_argument("--bf", type=float, default=28.0)
    p.add_argument("--height", type=float, default=178.0)
    p.add_argument("--age", type=float, default=35.0)
    p.add_argument("--somatotype", default="meso_endo")
    p.add_argument("--subject-json", default=None, help="population or calibrated subject JSON")
    p.add_argument("--days", type=int, default=None)
    args = p.parse_args()

    ensure_dirs()
    if args.subject_json:
        import json
        from pathlib import Path
        data = json.loads(Path(args.subject_json).read_text(encoding="utf-8"))
        subject = SubjectProfile.from_calibration_dict(
            data,
            age_y=data.get("age_y", args.age),
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
    out = rank_protocols(subject=subject, days=args.days)
    print("=== PROTOCOL RANKING (FSOT Fat Burn) ===")
    for r in out["ranking"]:
        s = r["summary"]
        print(
            f"#{r['rank']:02d}  score={r['score']:7.2f}  {r['label']:28s}  "
            f"fat_lost={s['fat_lost_kg']:+.3f}kg  scaleΔ={s['scale_delta_kg']:+.3f}kg  "
            f"burn_idx={s['mean_fat_burn_index']:.3f}  diet={s['protocol']['diet']}"
        )
    print("\nWinner:", out["winner"]["label"] if out["winner"] else None)
    print("Full JSON: reports/protocol_ranking.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
