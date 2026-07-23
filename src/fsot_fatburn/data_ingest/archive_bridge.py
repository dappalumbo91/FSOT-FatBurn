"""Pull existing FSOT archive medical/chemistry caches into this project."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from ..paths import load_config, project_path, ensure_dirs


def _safe_load(path: Path) -> Any:
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def import_archive_caches() -> Dict[str, Any]:
    """
    Copy/symlink-relevant JSON from FSOT-Physical-Archive into data/cache
    and build a fat-burn oriented index.
    """
    ensure_dirs()
    cfg = load_config()
    fsot = cfg["fsot"]
    report: Dict[str, Any] = {"copied": [], "indexed": {}, "missing": []}

    mapping = {
        "pubchem_archive.json": Path(fsot["pubchem_cache"]),
        "chembl_archive.json": Path(fsot["chembl_cache"]),
    }
    smiles = Path(fsot.get("smiles_dataset", ""))
    if smiles.is_file():
        mapping["smiles_lab_dataset.json"] = smiles

    # Extra medical panels from lean hub data/
    lean = Path(fsot["lean_hub"]) / "data"
    extras = {
        "clinicaltrials_medical_panel.json": lean / "clinicaltrials_medical_panel_benchmark.json",
        "pubchem_compound_properties_benchmark.json": lean / "pubchem_compound_properties_benchmark.json",
        "pubchem_live_deep_benchmark.json": lean / "pubchem_live_deep_benchmark.json",
        "pharmacology_chembl_manifest.yaml": lean / "pharmacology_chembl_manifest.yaml",
        "biology_strict_empirical.json": lean / "biology_strict_empirical.json",
        "sports_biomechanics_reference.json": lean / "sports_biomechanics_reference_observables.json",
    }
    mapping.update(extras)

    cache_root = project_path("data", "cache", "archive")
    cache_root.mkdir(parents=True, exist_ok=True)

    for dest_name, src in mapping.items():
        if not src.is_file():
            report["missing"].append(str(src))
            continue
        dest = cache_root / dest_name
        shutil.copy2(src, dest)
        report["copied"].append({"src": str(src), "dest": str(dest), "bytes": dest.stat().st_size})

    # Build compound index from pubchem archive
    pub = _safe_load(cache_root / "pubchem_archive.json")
    fat_relevant = []
    keywords = (
        "lipid", "fat", "drug", "vitamin", "alkaloid", "nutraceutical",
        "metabolite", "hormone", "culinary_fat", "phytochemical", "beverage",
    )
    if isinstance(pub, dict) and "compounds" in pub:
        for c in pub["compounds"]:
            cat = (c.get("category") or "").lower()
            dom = (c.get("domain") or "").lower()
            if any(k in cat for k in keywords) or dom == "medical":
                fat_relevant.append(c)
        report["indexed"]["pubchem_fat_relevant"] = len(fat_relevant)
        out = project_path("data", "derived", "pubchem_fat_relevant.json")
        out.write_text(json.dumps(fat_relevant, indent=2), encoding="utf-8")

    chem = _safe_load(cache_root / "chembl_archive.json")
    if isinstance(chem, dict) and "molecules" in chem:
        report["indexed"]["chembl_molecules"] = len(chem["molecules"])
        # Prefer oral + max_phase >= 3
        def _phase(m):
            try:
                return float(m.get("max_phase") or 0)
            except (TypeError, ValueError):
                return 0.0

        oral = [
            m for m in chem["molecules"]
            if m.get("oral") and _phase(m) >= 3
        ]
        report["indexed"]["chembl_oral_phase3plus"] = len(oral)
        project_path("data", "derived", "chembl_oral_phase3.json").write_text(
            json.dumps(oral, indent=2), encoding="utf-8"
        )

    summary_path = project_path("data", "derived", "archive_import_report.json")
    summary_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
