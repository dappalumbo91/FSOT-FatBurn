#!/usr/bin/env python3
"""
Build the population anthropometry catalog from seed extremes/percentiles.

Calibrates every archetype (Navy BF + depot map) and optionally runs a short
fat-burn probe sim so users can compare protocol response across the human range.
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
    build_population_catalog,
    export_population_subjects,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Build population waist/hip/neck archetype grid")
    p.add_argument("--sim", action="store_true", help="Run probe sim on each archetype")
    p.add_argument("--days", type=int, default=14, help="Probe sim days when --sim")
    args = p.parse_args()

    ensure_dirs()
    print("=== Building population anthropometry catalog ===")
    cat = build_population_catalog(run_sims=args.sim, sim_days=args.days)
    n_sub = export_population_subjects(cat)

    rs = cat["range_summary"]
    print(f"archetypes:     {cat['n_archetypes']} (calibrated ok: {cat['n_calibrated_ok']})")
    print(f"waist range:    {rs['waist_cm']['min']}–{rs['waist_cm']['max']} cm")
    print(f"hip range:      {rs['hip_cm']['min']}–{rs['hip_cm']['max']} cm")
    print(f"neck range:     {rs['neck_cm']['min']}–{rs['neck_cm']['max']} cm")
    print(f"BF% range:      {rs['body_fat_pct']['min']}–{rs['body_fat_pct']['max']}")
    print(f"sex counts:     {rs['sex_counts']}")
    print(f"subject JSONs:  {n_sub} → data/derived/population_subjects/")
    print(f"catalog:        data/derived/population_anthropometry_catalog.json")
    print(f"selection table:data/derived/population_selection_table.json")

    # Human-readable markdown summary
    lines = [
        "# Population Anthropometry Selection Grid",
        "",
        "Select the closest archetype to your waist / hip / neck / height / weight, then critique the deltas.",
        "These are **population bounds and clinical cut-points**, not one person's body.",
        "",
        f"- Archetypes: **{cat['n_archetypes']}**",
        f"- Waist span: **{rs['waist_cm']['min']}–{rs['waist_cm']['max']} cm**",
        f"- Hip span: **{rs['hip_cm']['min']}–{rs['hip_cm']['max']} cm**",
        f"- Neck span: **{rs['neck_cm']['min']}–{rs['neck_cm']['max']} cm**",
        "",
        "| ID | Label | Sex | Ht | Wt | Waist | Hip | Neck | BMI | WHR | BF%≈ | Shape | Band |",
        "|----|-------|-----|----|----|-------|-----|------|-----|-----|------|-------|------|",
    ]
    for e in cat["archetypes"]:
        s = e["seed"]
        d = e["derived"]
        bf = d.get("body_fat_pct")
        bf_s = f"{bf:.1f}" if isinstance(bf, (int, float)) else "—"
        lines.append(
            f"| `{e['id']}` | {e['label']} | {s['sex'][0].upper()} | "
            f"{s['height_cm']:.0f} | {s['weight_kg']:.0f} | {s['waist_cm']:.0f} | "
            f"{s['hip_cm']:.0f} | {s['neck_cm']:.0f} | {d['bmi']:.1f} | {d['whr']:.2f} | "
            f"{bf_s} | {e['bands']['shape']} | {e['bands']['adiposity_band']} |"
        )
    lines.extend([
        "",
        "## How to select",
        "",
        "```powershell",
        "python scripts/select_archetype.py --sex male --height 178 --weight 95 --waist 102 --hip 108 --neck 40",
        "python scripts/run_sim.py --subject-json data/derived/population_subjects/M_atp3_102.json",
        "```",
        "",
        "Then refine with your exact measures via `calibrate_subject.py` if you want a personal overlay.",
        "",
    ])
    md_path = project_path("reports", "POPULATION_ANTHROPOMETRY_GRID.md")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"markdown:       {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
