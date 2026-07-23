#!/usr/bin/env python3
"""Auto-expand compound catalog from OpenFDA generics + optional PubChem resolve."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fsot_fatburn.paths import ensure_dirs
from fsot_fatburn.interventions.openfda_expand import expand_catalog_from_openfda
from fsot_fatburn.interventions.effect_tuning import tune_compounds_from_trials
from fsot_fatburn.interventions.compounds import load_compound_catalog


def main() -> int:
    p = argparse.ArgumentParser(description="Expand FSOT Fat Burn catalog from OpenFDA")
    p.add_argument("--no-pubchem", action="store_true", help="Skip live PubChem CID resolve")
    p.add_argument("--retune", action="store_true", help="Re-apply trial anchors after expand")
    args = p.parse_args()

    ensure_dirs()
    report = expand_catalog_from_openfda(resolve_pubchem=not args.no_pubchem)
    print(json.dumps(report, indent=2))
    print(
        f"\nCatalog {report['existing_count']} → {report['final_count']} "
        f"(+{len(report['added_ids'])} new): {report['added_ids']}"
    )

    if args.retune:
        # Retune works on SEED list primarily; re-merge trial into full catalog scores for known ids
        tuned = {r["id"]: r for r in tune_compounds_from_trials()}
        full = load_compound_catalog()
        # reload full file
        from fsot_fatburn.paths import project_path
        path = project_path("data", "derived", "compounds_catalog_full.json")
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            if row["id"] in tuned:
                t = tuned[row["id"]]
                for k in (
                    "lipolytic", "alpha2_antagonist", "thermogenic",
                    "appetite_suppress", "diuretic", "insulin_sensitizer",
                    "tune_source", "trial_anchors",
                ):
                    if k in t:
                        row[k] = t[k]
                row["source"] = row.get("source", "seed") + "+trial"
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Re-merged trial tunes into {path}")

    cat = load_compound_catalog()
    print(f"load_compound_catalog() → {len(cat)} agents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
