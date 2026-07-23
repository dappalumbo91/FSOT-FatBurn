"""
Auto-expand compound catalog from OpenFDA obesity / weight labels.

- Parse generics from openfda_obesity_pack.json
- Normalize salt/combo names
- Map EPC pharmacologic classes → mechanism scores
- Resolve PubChem CIDs (optional live)
- Merge with seed/trial-tuned catalog without clobbering curated agents
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from ..paths import project_path, ensure_dirs
from .compounds import CompoundAgent, SEED_COMPOUNDS, load_compound_catalog

# Homeopathic / noise generics to skip
SKIP_SUBSTRINGS = (
    "adeps", "adrenalin", "calcarea", "chelidoni", "agrimonia", "ammonium bromatum",
    "fucus vesiculosus", "kali phosphoricum", "lycopodium", "spongia", "natrum",
    "non-standardized", "allergenic", "isoniazid", "ursodiol", "methylphenidate",
    "serdexmethylphenidate", "dexmethylphenidate",
)

# Drop provisional auto-ids that are not weight-management relevant
SKIP_AGENT_IDS = {
    "isoniazid", "ursodiol", "serdexmethylphenidate", "dexmethylphenidate",
}

# Normalize salt suffixes
SALT_SUFFIXES = re.compile(
    r"\b(hydrochloride|hcl|hydrobromide|sulfate|sulphate|acetate|sodium|"
    r"potassium|mesylate|tartrate|phosphate|extended-release|er|xr|sr|"
    r"oral|and|extended release)\b",
    re.I,
)

# Known alias → catalog id
ALIAS_TO_ID = {
    "semaglutide": "semaglutide",
    "oral semaglutide": "semaglutide",
    "tirzepatide": "tirzepatide",
    "liraglutide": "liraglutide",
    "orlistat": "orlistat",
    "phentermine": "phentermine",
    "metformin": "metformin",
    "metformin hydrochloride": "metformin",
    "metformin hcl": "metformin",
    "metformin er 500 mg": "metformin",
    "naltrexone": "naltrexone",
    "naltrexone hydrochloride": "naltrexone",
    "bupropion": "bupropion",
    "bupropion hydrochloride": "bupropion",
    "topiramate": "topiramate",
    "sitagliptin": "sitagliptin",
    "glipizide": "glipizide",
    "omega-3-acid ethyl esters": "omega3_epa_dha",
    "omega-3": "omega3_epa_dha",
    "nicotine": "nicotine",
    "caffeine": "caffeine",
}

# New agents not in original seed — base priors before class mapping
CURATED_NEW = {
    "liraglutide": dict(
        name="Liraglutide", category="appetite",
        lipolytic=0.05, alpha2_antagonist=0.0, thermogenic=0.0,
        appetite_suppress=0.75, diuretic=0.0, insulin_sensitizer=0.20,
        oral_home_feasible=False,
        notes="GLP-1 RA (Saxenda); strong clinical weight loss; injectable.",
        pubchem_cid=16134956, chembl_id="CHEMBL1200690",
    ),
    "naltrexone": dict(
        name="Naltrexone", category="appetite",
        lipolytic=0.0, alpha2_antagonist=0.0, thermogenic=0.0,
        appetite_suppress=0.35, diuretic=0.0, insulin_sensitizer=0.0,
        oral_home_feasible=True,
        notes="Opioid antagonist; used with bupropion (Contrave) for weight.",
        pubchem_cid=5360515, chembl_id="CHEMBL190",
    ),
    "bupropion": dict(
        name="Bupropion", category="appetite",
        lipolytic=0.05, alpha2_antagonist=0.0, thermogenic=0.15,
        appetite_suppress=0.40, diuretic=0.0, insulin_sensitizer=0.0,
        oral_home_feasible=True,
        notes="NDRI; appetite/EE component of Contrave.",
        pubchem_cid=444, chembl_id="CHEMBL894",
    ),
    "topiramate": dict(
        name="Topiramate", category="appetite",
        lipolytic=0.05, alpha2_antagonist=0.0, thermogenic=0.05,
        appetite_suppress=0.45, diuretic=0.0, insulin_sensitizer=0.0,
        oral_home_feasible=True,
        notes="Anticonvulsant; Qsymia with phentermine.",
        pubchem_cid=5284627, chembl_id="CHEMBL220492",
    ),
    "sitagliptin": dict(
        name="Sitagliptin", category="hormone",
        lipolytic=0.0, alpha2_antagonist=0.0, thermogenic=0.0,
        appetite_suppress=0.05, diuretic=0.0, insulin_sensitizer=0.35,
        oral_home_feasible=True,
        notes="DPP-4 inhibitor; glucose/insulin pathway; modest weight-neutral.",
        pubchem_cid=4369359, chembl_id="CHEMBL1422",
    ),
    "glipizide": dict(
        name="Glipizide", category="hormone",
        lipolytic=0.0, alpha2_antagonist=0.0, thermogenic=0.0,
        appetite_suppress=0.0, diuretic=0.0, insulin_sensitizer=-0.1,
        oral_home_feasible=True,
        notes="Sulfonylurea — insulin secretagogue; may promote weight gain.",
        pubchem_cid=3478, chembl_id="CHEMBL1071",
    ),
    "phentermine_topiramate": dict(
        name="Phentermine + Topiramate (Qsymia-class)", category="appetite",
        lipolytic=0.20, alpha2_antagonist=0.0, thermogenic=0.30,
        appetite_suppress=0.70, diuretic=0.0, insulin_sensitizer=0.0,
        oral_home_feasible=True,
        notes="Fixed combo; strong clinical weight loss; Rx controlled.",
        pubchem_cid=None, chembl_id=None,
    ),
    "naltrexone_bupropion": dict(
        name="Naltrexone + Bupropion (Contrave-class)", category="appetite",
        lipolytic=0.05, alpha2_antagonist=0.0, thermogenic=0.15,
        appetite_suppress=0.65, diuretic=0.0, insulin_sensitizer=0.0,
        oral_home_feasible=True,
        notes="Central appetite combo; Rx.",
        pubchem_cid=None, chembl_id=None,
    ),
    "insulin_degludec_liraglutide": dict(
        name="Insulin degludec + Liraglutide", category="hormone",
        lipolytic=0.0, alpha2_antagonist=0.0, thermogenic=0.0,
        appetite_suppress=0.35, diuretic=0.0, insulin_sensitizer=0.40,
        oral_home_feasible=False,
        notes="Xultophy-class; diabetes; weight effect mixed vs pure GLP-1.",
        pubchem_cid=None, chembl_id=None,
    ),
    "cholestyramine": dict(
        name="Cholestyramine", category="nutrient",
        lipolytic=0.0, alpha2_antagonist=0.0, thermogenic=0.0,
        appetite_suppress=0.05, diuretic=0.0, insulin_sensitizer=0.05,
        oral_home_feasible=True,
        notes="Bile acid sequestrant; lipid, not primary fat-loss agent.",
        pubchem_cid=70695641, chembl_id=None,
    ),
    "megestrol": dict(
        name="Megestrol acetate", category="hormone",
        lipolytic=0.0, alpha2_antagonist=0.0, thermogenic=0.0,
        appetite_suppress=-0.5, diuretic=0.0, insulin_sensitizer=0.0,
        oral_home_feasible=True,
        notes="Appetite stimulant — opposite of fat-loss; tracked for completeness.",
        pubchem_cid=19090, chembl_id=None,
    ),
    "amphetamine": dict(
        name="Amphetamine", category="appetite",
        lipolytic=0.25, alpha2_antagonist=0.0, thermogenic=0.45,
        appetite_suppress=0.70, diuretic=0.0, insulin_sensitizer=0.0,
        oral_home_feasible=True,
        notes="Strong sympathomimetic anorectic; controlled substance.",
        pubchem_cid=3007, chembl_id="CHEMBL405",
    ),
}

# EPC class → score boosts (added then clamped)
EPC_SCORE_MAP = {
    "GLP-1 Receptor Agonist": {
        "appetite_suppress": 0.85, "insulin_sensitizer": 0.25, "category": "appetite",
        "oral_home_feasible": False,
    },
    "Glucose-dependent Insulinotropic Polypeptide Receptor Agonist": {
        "appetite_suppress": 0.95, "insulin_sensitizer": 0.30, "category": "appetite",
        "oral_home_feasible": False,
    },
    "Intestinal Lipase Inhibitor": {
        "appetite_suppress": 0.05, "lipolytic": 0.05, "category": "appetite",
    },
    "Catecholamine": {
        "thermogenic": 0.50, "appetite_suppress": 0.40, "lipolytic": 0.25, "category": "thermogenic",
    },
    "alpha-Adrenergic Agonist": {
        "thermogenic": 0.35, "appetite_suppress": 0.25, "category": "thermogenic",
    },
    "beta-Adrenergic Agonist": {
        "thermogenic": 0.40, "lipolytic": 0.30, "category": "thermogenic",
    },
    "Dipeptidyl Peptidase 4 Inhibitor": {
        "insulin_sensitizer": 0.35, "appetite_suppress": 0.05, "category": "hormone",
    },
    "Sulfonylurea": {
        "insulin_sensitizer": -0.1, "appetite_suppress": 0.0, "category": "hormone",
    },
    "Bile Acid Sequestrant": {
        "category": "nutrient", "appetite_suppress": 0.05,
    },
    "Insulin Analog": {
        "insulin_sensitizer": 0.3, "appetite_suppress": 0.0, "category": "hormone",
        "oral_home_feasible": False,
    },
}


def _slug(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")[:64]


def _clean_generic(raw: str) -> str:
    s = (raw or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _should_skip(generic: str) -> bool:
    g = generic.lower()
    return any(x in g for x in SKIP_SUBSTRINGS)


def _split_components(generic: str) -> List[str]:
    """Split combo products into component candidates + full combo key."""
    g = _clean_generic(generic)
    if " and " in g or " + " in g:
        parts = re.split(r"\s+and\s+|\s*\+\s*", g)
        parts = [p.strip() for p in parts if p.strip()]
        # strip dose noise
        cleaned = []
        for p in parts:
            p2 = SALT_SUFFIXES.sub(" ", p)
            p2 = re.sub(r"\d+\s*mg", " ", p2)
            p2 = re.sub(r"\s+", " ", p2).strip(" ,")
            if p2:
                cleaned.append(p2)
        return cleaned
    # strip salts for single agents
    p2 = SALT_SUFFIXES.sub(" ", g)
    p2 = re.sub(r"\d+\s*mg", " ", p2)
    p2 = re.sub(r"\s+", " ", p2).strip(" ,")
    return [p2] if p2 else [g]


def _resolve_id(generic: str) -> Optional[str]:
    g = _clean_generic(generic)
    if g in ALIAS_TO_ID:
        return ALIAS_TO_ID[g]
    # stripped
    stripped = SALT_SUFFIXES.sub(" ", g)
    stripped = re.sub(r"\d+\s*mg", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    if stripped in ALIAS_TO_ID:
        return ALIAS_TO_ID[stripped]
    # combo specials
    if "phentermine" in g and "topiramate" in g:
        return "phentermine_topiramate"
    if "naltrexone" in g and "bupropion" in g:
        return "naltrexone_bupropion"
    if "insulin degludec" in g and "liraglutide" in g:
        return "insulin_degludec_liraglutide"
    if "sitagliptin" in g and "metformin" in g:
        return "sitagliptin"  # expand metformin separately via components
    if "glipizide" in g and "metformin" in g:
        return "glipizide"
    # single word root
    root = stripped.split(",")[0].strip()
    if root in ALIAS_TO_ID:
        return ALIAS_TO_ID[root]
    if root in CURATED_NEW:
        return root
    # amphetamine
    if "amphetamine" in g and "methylphenidate" not in g:
        return "amphetamine"
    if "megestrol" in g:
        return "megestrol"
    if "cholestyramine" in g:
        return "cholestyramine"
    return None


def _apply_epc(scores: dict, classes: List[str]) -> dict:
    out = dict(scores)
    for c in classes:
        key = c.replace(" [EPC]", "").strip()
        for epc, boost in EPC_SCORE_MAP.items():
            if epc.lower() in key.lower() or key.lower() in epc.lower():
                for k, v in boost.items():
                    if k == "category":
                        out["category"] = v
                    elif k == "oral_home_feasible":
                        out["oral_home_feasible"] = v
                    elif k in out:
                        # take max of absolute intent for positive; min for negative
                        if v < 0:
                            out[k] = min(float(out[k]), v)
                        else:
                            out[k] = max(float(out[k]), v)
    # clamp display scores to [-0.5, 1]
    for k in ("lipolytic", "alpha2_antagonist", "thermogenic", "appetite_suppress",
              "diuretic", "insulin_sensitizer"):
        if k in out:
            out[k] = max(-0.5, min(1.0, float(out[k])))
    return out


def load_openfda_pack() -> dict:
    path = project_path("data", "derived", "openfda_obesity_pack.json")
    if not path.is_file():
        from ..data_ingest.openfda_client import build_openfda_obesity_pack
        return build_openfda_obesity_pack()
    return json.loads(path.read_text(encoding="utf-8"))


def extract_openfda_agent_index(pack: Optional[dict] = None) -> Dict[str, dict]:
    """
    Returns agent_id → {generic_names, brands, epc_classes, label_count, routes, raw}
    """
    pack = pack or load_openfda_pack()
    index: Dict[str, dict] = {}

    for lab in pack.get("labels") or []:
        generic = _clean_generic(lab.get("generic_name") or "")
        if not generic or _should_skip(generic):
            continue

        candidates = set()
        rid = _resolve_id(generic)
        if rid:
            candidates.add(rid)
        for comp in _split_components(generic):
            cid = _resolve_id(comp)
            if cid:
                candidates.add(cid)
            elif comp and not _should_skip(comp):
                # unknown component — provisional slug if looks like single drug
                if len(comp.split()) <= 3 and "and" not in comp:
                    candidates.add(_slug(comp))

        classes = list(lab.get("pharm_class_epc") or [])
        brand = lab.get("brand_name")
        routes = lab.get("route") or []

        for aid in candidates:
            slot = index.setdefault(aid, {
                "id": aid,
                "generic_names": set(),
                "brands": set(),
                "epc_classes": set(),
                "routes": set(),
                "label_count": 0,
                "sample_indication": "",
            })
            slot["generic_names"].add(generic)
            if brand:
                slot["brands"].add(brand)
            for c in classes:
                slot["epc_classes"].add(c)
            for r in routes:
                slot["routes"].add(r)
            slot["label_count"] += 1
            if not slot["sample_indication"]:
                slot["sample_indication"] = (lab.get("indications_and_usage") or "")[:400]

    # serialize sets
    out = {}
    for k, v in index.items():
        out[k] = {
            **v,
            "generic_names": sorted(v["generic_names"]),
            "brands": sorted(v["brands"]),
            "epc_classes": sorted(v["epc_classes"]),
            "routes": sorted(v["routes"]),
        }
    return out


def _base_agent_dict(agent_id: str, meta: dict) -> dict:
    seed_map = {c.id: c for c in SEED_COMPOUNDS}
    if agent_id in seed_map:
        base = seed_map[agent_id].to_dict()
        base["source"] = "seed+openfda"
        return base

    if agent_id in CURATED_NEW:
        c = CURATED_NEW[agent_id]
        return {
            "id": agent_id,
            "name": c["name"],
            "pubchem_cid": c.get("pubchem_cid"),
            "chembl_id": c.get("chembl_id"),
            "smiles": None,
            "category": c["category"],
            "lipolytic": c["lipolytic"],
            "alpha2_antagonist": c["alpha2_antagonist"],
            "thermogenic": c["thermogenic"],
            "appetite_suppress": c["appetite_suppress"],
            "diuretic": c["diuretic"],
            "insulin_sensitizer": c["insulin_sensitizer"],
            "oral_home_feasible": c["oral_home_feasible"],
            "notes": c["notes"],
            "molecular_weight": None,
            "molecular_formula": None,
            "iupac_name": None,
            "source": "openfda_curated",
        }

    # Unknown provisional agent from FDA text
    name = meta["generic_names"][0] if meta.get("generic_names") else agent_id
    scores = {
        "lipolytic": 0.05,
        "alpha2_antagonist": 0.0,
        "thermogenic": 0.05,
        "appetite_suppress": 0.15,
        "diuretic": 0.0,
        "insulin_sensitizer": 0.0,
        "category": "drug_pharmacology",
        "oral_home_feasible": True,
    }
    scores = _apply_epc(scores, meta.get("epc_classes") or [])
    return {
        "id": agent_id,
        "name": name.title() if len(name) < 60 else agent_id.replace("_", " ").title(),
        "pubchem_cid": None,
        "chembl_id": None,
        "smiles": None,
        "category": scores.get("category", "drug_pharmacology"),
        "lipolytic": scores["lipolytic"],
        "alpha2_antagonist": scores["alpha2_antagonist"],
        "thermogenic": scores["thermogenic"],
        "appetite_suppress": scores["appetite_suppress"],
        "diuretic": scores["diuretic"],
        "insulin_sensitizer": scores["insulin_sensitizer"],
        "oral_home_feasible": scores.get("oral_home_feasible", True),
        "notes": f"Auto-expanded from OpenFDA ({meta.get('label_count', 0)} labels). Verify before use.",
        "molecular_weight": None,
        "molecular_formula": None,
        "iupac_name": None,
        "source": "openfda_auto",
    }


def expand_catalog_from_openfda(
    *,
    resolve_pubchem: bool = True,
    merge_existing: bool = True,
) -> Dict[str, Any]:
    """
    Build expanded catalog JSON and write derived artifacts.
    """
    ensure_dirs()
    index = extract_openfda_agent_index()

    # Start from best existing catalog (purge known noise ids)
    existing = {c.id: c.to_dict() for c in load_compound_catalog()} if merge_existing else {}
    for bad in SKIP_AGENT_IDS:
        existing.pop(bad, None)
    seed_ids = {c.id for c in SEED_COMPOUNDS}

    expanded: Dict[str, dict] = dict(existing)
    added = []
    updated_fda_meta = []

    for agent_id, meta in sorted(index.items(), key=lambda x: -x[1]["label_count"]):
        if agent_id in SKIP_AGENT_IDS:
            continue
        if agent_id in expanded:
            row = expanded[agent_id]
            row["openfda"] = {
                "label_count": meta["label_count"],
                "brands": meta["brands"][:10],
                "generic_names": meta["generic_names"][:10],
                "epc_classes": meta["epc_classes"],
                "routes": meta["routes"],
            }
            # Apply EPC boosts only if not trial-tuned heavily
            if row.get("tune_source") != "seed+trial" and row.get("source") != "seed+trial_tuned":
                scores = {k: row[k] for k in (
                    "lipolytic", "alpha2_antagonist", "thermogenic",
                    "appetite_suppress", "diuretic", "insulin_sensitizer", "category",
                    "oral_home_feasible",
                ) if k in row}
                scores = _apply_epc(scores, meta["epc_classes"])
                row.update({k: scores[k] for k in scores})
            updated_fda_meta.append(agent_id)
            continue

        row = _base_agent_dict(agent_id, meta)
        row = _apply_epc(row, meta["epc_classes"])
        row["openfda"] = {
            "label_count": meta["label_count"],
            "brands": meta["brands"][:10],
            "generic_names": meta["generic_names"][:10],
            "epc_classes": meta["epc_classes"],
            "routes": meta["routes"],
        }
        expanded[agent_id] = row
        added.append(agent_id)

    # Optional PubChem CID fill for new agents missing CID
    pubchem_hits = 0
    if resolve_pubchem:
        try:
            from ..data_ingest.pubchem_client import search_pubchem_name, fetch_pubchem_cid, _props_from_pug
            for aid in added:
                row = expanded[aid]
                if row.get("pubchem_cid"):
                    continue
                query = row.get("name") or aid.replace("_", " ")
                # skip multi-ingredient combos
                if "+" in query or " and " in query.lower():
                    continue
                try:
                    cid = search_pubchem_name(query.split("(")[0].strip())
                    if cid:
                        row["pubchem_cid"] = cid
                        data = fetch_pubchem_cid(cid)
                        props = _props_from_pug(data)
                        if props.get("CanonicalSMILES"):
                            row["smiles"] = props["CanonicalSMILES"]
                        if props.get("MolecularWeight"):
                            row["molecular_weight"] = float(props["MolecularWeight"])
                        if props.get("MolecularFormula"):
                            row["molecular_formula"] = props["MolecularFormula"]
                        if props.get("IUPACName"):
                            row["iupac_name"] = props["IUPACName"]
                        pubchem_hits += 1
                    time.sleep(0.15)
                except Exception:
                    continue
        except Exception:
            pass

    catalog_list = list(expanded.values())
    # Prefer higher label_count / known agents first in file order
    catalog_list.sort(key=lambda r: (
        0 if r["id"] in seed_ids else 1,
        0 if r.get("source") in ("seed+trial", "seed+trial_tuned", "seed+openfda") else 1,
        -(r.get("openfda") or {}).get("label_count", 0),
        r["id"],
    ))

    out_path = project_path("data", "derived", "compounds_catalog_full.json")
    out_path.write_text(json.dumps(catalog_list, indent=2), encoding="utf-8")

    # Also write openfda-only newcomers
    newcomers = [expanded[a] for a in added]
    project_path("data", "derived", "compounds_openfda_new.json").write_text(
        json.dumps(newcomers, indent=2), encoding="utf-8"
    )

    report = {
        "existing_count": len(existing),
        "final_count": len(catalog_list),
        "added_ids": added,
        "updated_openfda_meta": updated_fda_meta,
        "pubchem_resolved": pubchem_hits,
        "openfda_index_size": len(index),
        "catalog_path": str(out_path),
    }
    project_path("data", "derived", "openfda_expand_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report
