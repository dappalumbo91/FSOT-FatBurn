#!/usr/bin/env python3
"""Fetch OpenFDA + ClinicalTrials + food packs; tune compounds; meal insulin report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fsot_fatburn.paths import ensure_dirs, project_path
from fsot_fatburn.data_ingest.openfda_client import build_openfda_obesity_pack
from fsot_fatburn.data_ingest.clinicaltrials_client import build_clinicaltrials_obesity_pack
from fsot_fatburn.data_ingest.food_client import build_food_pack, example_meals
from fsot_fatburn.interventions.effect_tuning import tune_compounds_from_trials


def main() -> int:
    ensure_dirs()
    print("=== Medical + food packs ===")

    print("[1/4] OpenFDA obesity / weight labels...")
    try:
        fda = build_openfda_obesity_pack()
        print(f"  labels={fda['label_count']} errors={len(fda['errors'])}")
    except Exception as e:
        print(f"  OpenFDA failed: {e}")

    print("[2/4] ClinicalTrials.gov obesity / lipolysis...")
    try:
        ct = build_clinicaltrials_obesity_pack()
        print(f"  studies={ct['study_count']} agent_hits={ct.get('agent_hits')}")
    except Exception as e:
        print(f"  ClinicalTrials failed: {e}")

    print("[3/4] Food pack (seed + Open Food Facts; USDA if FDC_API_KEY)...")
    try:
        food = build_food_pack()
        print(f"  foods={food['food_count']} errors={len(food['errors'])}")
    except Exception as e:
        print(f"  Food pack failed: {e}")

    print("[4/4] Trial-tune compound effect sizes + meal insulin examples...")
    tuned = tune_compounds_from_trials()
    print(f"  tuned compounds={len(tuned)}")
    meals = {k: v.to_dict() for k, v in example_meals().items()}
    project_path("data", "derived", "meal_insulin_examples.json").write_text(
        json.dumps(meals, indent=2), encoding="utf-8"
    )
    for name, m in meals.items():
        print(f"  meal {name}: insulin_index={m['insulin_index']:.3f} GL={m['glycemic_load']:.1f} kcal={m['total_kcal']:.0f}")

    print("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
