#!/usr/bin/env python3
"""
Select nearest population archetype(s) from your waist/hip/neck/height/weight.

Does NOT invent a single personal truth — places you on the population grid so you
can choose templates and critique measurement deltas toward yourself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fsot_fatburn.paths import ensure_dirs, project_path
from fsot_fatburn.physiology.population_grid import (
    UserMeasures,
    match_user_to_archetypes,
    load_population_catalog,
    build_population_catalog,
    export_population_subjects,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Match measures to population archetype grid")
    p.add_argument("--sex", required=True, choices=["male", "female"])
    p.add_argument("--height", type=float, required=True, help="cm")
    p.add_argument("--weight", type=float, required=True, help="kg")
    p.add_argument("--waist", type=float, required=True, help="cm")
    p.add_argument("--hip", type=float, required=True, help="cm")
    p.add_argument("--neck", type=float, required=True, help="cm")
    p.add_argument("--age", type=float, default=35.0)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--all-sexes", action="store_true", help="Do not filter to same sex")
    p.add_argument("--rebuild", action="store_true", help="Rebuild catalog first")
    p.add_argument("--name", default="selection", help="output report name")
    args = p.parse_args()

    ensure_dirs()
    if args.rebuild or not project_path("data", "derived", "population_anthropometry_catalog.json").is_file():
        print("Building population catalog...")
        cat = build_population_catalog(run_sims=False)
        export_population_subjects(cat)

    user = UserMeasures(
        sex=args.sex,
        age_y=args.age,
        height_cm=args.height,
        weight_kg=args.weight,
        waist_cm=args.waist,
        hip_cm=args.hip,
        neck_cm=args.neck,
    )
    result = match_user_to_archetypes(
        user,
        top_k=args.top,
        same_sex_only=not args.all_sexes,
    )

    print("=== YOUR MEASURES (input) ===")
    u = result["user"]
    print(
        f"  {u['sex']}  ht={u['height_cm']} cm  wt={u['weight_kg']} kg  "
        f"waist={u['waist_cm']}  hip={u['hip_cm']}  neck={u['neck_cm']}"
    )
    print(
        f"  BMI={u['bmi']}  WHR={u['whr']}  WHtR={u['whtr']}  "
        f"Navy BF%≈{u['navy_bf_pct']}  waist-band≈{u['waist_band_nearest_label']}"
    )
    if result.get("grid_range"):
        gr = result["grid_range"]
        print(
            f"\nGrid spans waist {gr['waist_cm']['min']}–{gr['waist_cm']['max']} cm · "
            f"hip {gr['hip_cm']['min']}–{gr['hip_cm']['max']} · "
            f"neck {gr['neck_cm']['min']}–{gr['neck_cm']['max']}"
        )

    print(f"\n=== TOP {len(result['matches'])} ARCHETYPE MATCHES ===")
    for i, m in enumerate(result["matches"], 1):
        s = m["seed"]
        d = m["deltas_user_minus_archetype"]
        print(f"\n#{i}  {m['id']}  (distance={m['distance']:.3f})")
        print(f"    {m['label']}")
        print(
            f"    template: ht={s['height_cm']} wt={s['weight_kg']} "
            f"waist={s['waist_cm']} hip={s['hip_cm']} neck={s['neck_cm']}  "
            f"WHR={m['derived']['whr']} BF%≈{m['derived'].get('body_fat_pct')}  "
            f"[{m['bands']['adiposity_band']}]"
        )
        print(
            f"    deltas (you − template): waist {d['waist_cm']:+.1f}  hip {d['hip_cm']:+.1f}  "
            f"neck {d['neck_cm']:+.1f}  wt {d['weight_kg']:+.1f}  WHR {d['whr']:+.3f}"
        )
        for c in m["critique"]:
            print(f"    • {c}")
        print(f"    sim subject: data/derived/population_subjects/{m['id']}.json")
        print(f"    anchor: {m['bands']['literature_anchor']}")

    print("\n=== HOW TO USE ===")
    for h in result["how_to_use"]:
        print(f"  • {h}")

    if result["best"]:
        bid = result["best"]["id"]
        print("\n=== SUGGESTED NEXT COMMANDS ===")
        print(f'  python scripts/run_sim.py --subject-json "data/derived/population_subjects/{bid}.json" --days 28')
        print(
            f"  python scripts/calibrate_subject.py --name personal_overlay --sex {args.sex} "
            f"--height {args.height} --weight {args.weight} "
            f"--waist {args.waist} --hip {args.hip} --neck {args.neck} --run-sim"
        )
        print(
            f"  python scripts/rank_protocols.py --subject-json "
            f'"data/derived/population_subjects/{bid}.json"'
        )

    out = project_path("reports", f"archetype_selection_{args.name}.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
