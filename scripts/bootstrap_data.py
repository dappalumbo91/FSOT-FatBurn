#!/usr/bin/env python3
"""Bootstrap FSOT Fat Burn data: archive import + PubChem/ChEMBL enrichment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fsot_fatburn.paths import ensure_dirs, project_path
from fsot_fatburn.data_ingest.archive_bridge import import_archive_caches
from fsot_fatburn.data_ingest.pubchem_client import enrich_compounds_pubchem
from fsot_fatburn.data_ingest.chembl_client import fetch_chembl_molecules
from fsot_fatburn.data_ingest.openfda_client import build_openfda_obesity_pack
from fsot_fatburn.data_ingest.clinicaltrials_client import build_clinicaltrials_obesity_pack
from fsot_fatburn.data_ingest.food_client import build_food_pack, example_meals
from fsot_fatburn.interventions.compounds import SEED_COMPOUNDS
from fsot_fatburn.interventions.effect_tuning import tune_compounds_from_trials
from fsot_fatburn.sim.export_adipose_panel import export_to_archive
from fsot_fatburn.fsot_bridge import smoke_test


def main() -> int:
    ensure_dirs()
    print("=== FSOT Fat Burn bootstrap ===")
    print("[1/7] FSOT engine smoke test...")
    smoke = smoke_test()
    project_path("data", "derived", "fsot_smoke.json").write_text(
        json.dumps(smoke, indent=2), encoding="utf-8"
    )
    print("  seeds phi=", smoke["seeds"]["phi"], "poof=", smoke["seeds"]["poof"])

    print("[2/7] Import archive caches (PubChem, ChEMBL, SMILES, panels)...")
    report = import_archive_caches()
    print(f"  copied={len(report['copied'])} missing={len(report['missing'])}")
    print(f"  indexed={report.get('indexed')}")

    print("[3/7] Enrich seed compounds via PubChem PUG REST...")
    try:
        enriched = enrich_compounds_pubchem()
        ok = sum(1 for r in enriched if r.get("smiles") or r.get("molecular_weight"))
        print(f"  enriched rows={len(enriched)} with structure/props≈{ok}")
    except Exception as e:
        print(f"  PubChem live fetch failed ({e}); writing seed catalog only")
        project_path("data", "derived", "compounds_enriched.json").write_text(
            json.dumps([c.to_dict() for c in SEED_COMPOUNDS], indent=2), encoding="utf-8"
        )

    print("[4/7] ChEMBL molecule profiles...")
    chembl_ids = [c.chembl_id for c in SEED_COMPOUNDS if c.chembl_id]
    try:
        batch = fetch_chembl_molecules(chembl_ids)
        ok = sum(1 for b in batch if b.get("ok"))
        print(f"  chembl ok={ok}/{len(batch)}")
    except Exception as e:
        print(f"  ChEMBL live fetch failed ({e}); archive cache still available")

    print("[5/7] OpenFDA + ClinicalTrials obesity packs...")
    try:
        fda = build_openfda_obesity_pack()
        print(f"  openfda labels={fda['label_count']}")
    except Exception as e:
        print(f"  openfda skipped: {e}")
    try:
        ct = build_clinicaltrials_obesity_pack()
        print(f"  clinicaltrials studies={ct['study_count']}")
    except Exception as e:
        print(f"  clinicaltrials skipped: {e}")

    print("[6/7] Food pack + trial-tune compounds + meal insulin...")
    try:
        food = build_food_pack()
        print(f"  foods={food['food_count']}")
    except Exception as e:
        print(f"  food pack skipped: {e}")
    tuned = tune_compounds_from_trials()
    print(f"  trial-tuned compounds={len(tuned)}")
    meals = {k: v.to_dict() for k, v in example_meals().items()}
    project_path("data", "derived", "meal_insulin_examples.json").write_text(
        json.dumps(meals, indent=2), encoding="utf-8"
    )

    print("[7/8] OpenFDA auto-expand compound catalog...")
    try:
        from fsot_fatburn.interventions.openfda_expand import expand_catalog_from_openfda
        exp_cat = expand_catalog_from_openfda(resolve_pubchem=True)
        print(
            f"  catalog {exp_cat['existing_count']}→{exp_cat['final_count']} "
            f"added={exp_cat['added_ids']}"
        )
    except Exception as e:
        print(f"  openfda expand skipped: {e}")

    print("[8/8] Export Adipose_Lipolysis panel → Lean archive...")
    try:
        exp = export_to_archive()
        print(
            f"  records={exp['record_count']} pooled_median={exp['pooled_median_error_pct']}% "
            f"→ {exp['archive_benchmark']}"
        )
    except Exception as e:
        print(f"  panel export failed: {e}")

    print("=== bootstrap complete ===")
    print("derived:", project_path("data", "derived"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
