"""
Compound / chemical agents for lipolysis, appetite, thermogenesis, diuresis.

Profiles merge:
  - Seed catalog (mechanism priors + PubChem CIDs)
  - Live/local PubChem + ChEMBL caches when available
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional

from ..paths import project_path


@dataclass
class CompoundAgent:
    id: str
    name: str
    pubchem_cid: Optional[int]
    chembl_id: Optional[str]
    smiles: Optional[str]
    category: str  # lipolytic | thermogenic | appetite | diuretic | hormone | nutrient
    # Mechanism scores 0–1 (priors for simulator; refined by data when present)
    lipolytic: float
    alpha2_antagonist: float
    thermogenic: float
    appetite_suppress: float
    diuretic: float
    insulin_sensitizer: float
    oral_home_feasible: bool
    notes: str
    molecular_weight: Optional[float] = None
    molecular_formula: Optional[str] = None
    iupac_name: Optional[str] = None
    source: str = "seed"

    def to_dict(self) -> dict:
        return asdict(self)


# Core research catalog — PubChem CIDs are real identifiers for API enrichment.
SEED_COMPOUNDS: List[CompoundAgent] = [
    CompoundAgent(
        "caffeine", "Caffeine", 2519, "CHEMBL113", "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
        "thermogenic", 0.45, 0.0, 0.40, 0.15, 0.05, 0.0, True,
        "Adenosine antagonist; mild lipolysis + thermogenesis; ubiquitous.",
    ),
    CompoundAgent(
        "egcg", "EGCG (green tea catechin)", 65064, None,
        "C1=C(C=C(C(=C1O)O)O)C2=C(C(=O)C3=C(C=C(C=C3O2)O)O)OC(=O)C4=CC(=C(C(=C4)O)O)O",
        "thermogenic", 0.25, 0.0, 0.30, 0.05, 0.0, 0.1, True,
        "Green tea extract principal catechin; modest EE increase in meta-analyses.",
    ),
    CompoundAgent(
        "capsaicin", "Capsaicin", 1548943, "CHEMBL294199",
        "COc1cc(CNC(=O)CCCC/C=C/C(C)C)ccc1O",
        "thermogenic", 0.30, 0.0, 0.45, 0.10, 0.0, 0.0, True,
        "TRPV1 agonist; diet-induced thermogenesis support.",
    ),
    CompoundAgent(
        "yohimbine", "Yohimbine", 8969, "CHEMBL1242", None,
        "lipolytic", 0.55, 0.85, 0.15, 0.10, 0.0, 0.0, True,
        "α2-antagonist; researched for stubborn α2-rich depots (fasted context).",
    ),
    CompoundAgent(
        "synephrine", "p-Synephrine", 7172, None, None,
        "thermogenic", 0.35, 0.1, 0.35, 0.15, 0.0, 0.0, True,
        "Citrus aurantium alkaloid; milder sympathomimetic.",
    ),
    CompoundAgent(
        "forskolin", "Forskolin", 47936, None, None,
        "lipolytic", 0.50, 0.0, 0.20, 0.0, 0.0, 0.0, True,
        "Adenylate cyclase activator → cAMP → HSL cascade (in vitro strong).",
    ),
    CompoundAgent(
        "l_carnitine", "L-Carnitine", 288, "CHEMBL1719", "C[N+](C)(C)CC(CC(=O)[O-])O",
        "nutrient", 0.15, 0.0, 0.05, 0.0, 0.0, 0.05, True,
        "FFA mitochondrial shuttle; evidence mixed for fat loss in replete adults.",
    ),
    CompoundAgent(
        "berberine", "Berberine", 2353, "CHEMBL1200580", None,
        "nutrient", 0.10, 0.0, 0.05, 0.05, 0.0, 0.55, True,
        "AMPK / glucose disposal; insulin-index reduction pathway.",
    ),
    CompoundAgent(
        "metformin", "Metformin", 4091, "CHEMBL1431", "CN(C)C(=N)N=C(N)N",
        "hormone", 0.10, 0.0, 0.05, 0.05, 0.0, 0.70, True,
        "Biguanide insulin sensitizer; Rx context; body-weight modest effects.",
    ),
    CompoundAgent(
        "orlistat", "Orlistat", 3034010, "CHEMBL1753", None,
        "appetite", 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, True,
        "Gastric/pancreatic lipase inhibitor; fecal fat loss; GI tradeoffs.",
    ),
    CompoundAgent(
        "semaglutide", "Semaglutide", 56843331, "CHEMBL3707238", None,
        "appetite", 0.05, 0.0, 0.0, 0.95, 0.0, 0.15, False,
        "GLP-1 RA; strong clinical fat loss via intake reduction; injectable Rx.",
    ),
    CompoundAgent(
        "tirzepatide", "Tirzepatide", 156588324, None, None,
        "appetite", 0.05, 0.0, 0.0, 0.98, 0.0, 0.20, False,
        "GIP/GLP-1 dual agonist; among highest clinical weight-loss effect sizes.",
    ),
    CompoundAgent(
        "phentermine", "Phentermine", 4771, "CHEMBL1200912", None,
        "appetite", 0.25, 0.0, 0.30, 0.80, 0.0, 0.0, True,
        "Sympathomimetic anorectic; Rx controlled substance in many regions.",
    ),
    CompoundAgent(
        "nicotine", "Nicotine", 89594, "CHEMBL3", None,
        "thermogenic", 0.20, 0.0, 0.35, 0.40, 0.0, 0.0, True,
        "Appetite + EE effects; dependence/toxicity dominate risk profile.",
    ),
    CompoundAgent(
        "furosemide", "Furosemide", 3440, "CHEMBL35", None,
        "diuretic", 0.0, 0.0, 0.0, 0.0, 0.95, 0.0, True,
        "Loop diuretic — water only; not adipose TAG loss.",
    ),
    CompoundAgent(
        "spironolactone", "Spironolactone", 5833, None, None,
        "diuretic", 0.0, 0.0, 0.0, 0.0, 0.70, 0.0, True,
        "MRA; water/androgen-related retention contexts.",
    ),
    CompoundAgent(
        "dandelion_k", "Potassium-rich diuretic herbs (scaffold)", None, None, None,
        "diuretic", 0.0, 0.0, 0.0, 0.0, 0.25, 0.0, True,
        "Mild OTC diuretic class proxy; water only.",
    ),
    CompoundAgent(
        "omega3_epa_dha", "EPA/DHA omega-3", 446284, None, None,
        "nutrient", 0.05, 0.0, 0.0, 0.0, 0.0, 0.15, True,
        "Anti-inflammatory / membrane; indirect metabolic support.",
    ),
    CompoundAgent(
        "cla", "Conjugated linoleic acid", 5282800, None, None,
        "nutrient", 0.15, 0.0, 0.10, 0.0, 0.0, 0.0, True,
        "Mixed human evidence for body composition.",
    ),
    CompoundAgent(
        "green_coffee_cga", "Chlorogenic acid (green coffee)", 1794427, None, None,
        "thermogenic", 0.15, 0.0, 0.15, 0.05, 0.0, 0.10, True,
        "Carb absorption / modest weight literature.",
    ),
    CompoundAgent(
        "fucoxanthin", "Fucoxanthin", 5281239, None, None,
        "thermogenic", 0.20, 0.0, 0.25, 0.0, 0.0, 0.0, True,
        "Carotenoid; UCP1 browning literature (mostly preclinical).",
    ),
    CompoundAgent(
        "oleoylethanolamide", "Oleoylethanolamide (OEA)", 5283454, None, None,
        "appetite", 0.10, 0.0, 0.05, 0.45, 0.0, 0.0, True,
        "PPAR-α satiety lipid mediator.",
    ),
    CompoundAgent(
        "acetate_vinegar", "Acetic acid (vinegar)", 176, None, "CC(=O)O",
        "nutrient", 0.05, 0.0, 0.05, 0.05, 0.0, 0.15, True,
        "Glycemic blunting; small EE literature.",
    ),
    CompoundAgent(
        "creatine_h2o", "Creatine monohydrate", 586, None, None,
        "nutrient", 0.0, 0.0, 0.0, 0.0, -0.3, 0.0, True,
        "Intracellular water ↑ (not fat); helps resistance performance.",
    ),
]


def load_compound_catalog(enriched_path: Optional[Path] = None) -> List[CompoundAgent]:
    """Prefer full OpenFDA-expanded → trial-tuned → enriched → seed."""
    candidates = []
    if enriched_path is not None:
        candidates.append(Path(enriched_path))
    candidates.extend([
        project_path("data", "derived", "compounds_catalog_full.json"),
        project_path("data", "derived", "compounds_trial_tuned.json"),
        project_path("data", "derived", "compounds_enriched.json"),
    ])
    for path in candidates:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            out = []
            for row in data:
                out.append(CompoundAgent(**{k: row[k] for k in CompoundAgent.__dataclass_fields__ if k in row}))
            return out
    return list(SEED_COMPOUNDS)


def stack_scores(compound_ids: List[str], catalog: Optional[List[CompoundAgent]] = None) -> dict:
    catalog = catalog or load_compound_catalog()
    by_id = {c.id: c for c in catalog}
    agents = [by_id[i] for i in compound_ids if i in by_id]
    if not agents:
        return {
            "lipolytic": 0.0,
            "alpha2_antagonist": 0.0,
            "thermogenic": 0.0,
            "appetite_suppress": 0.0,
            "diuretic": 0.0,
            "insulin_sensitizer": 0.0,
            "agents": [],
        }

    def soft_or(vals: List[float]) -> float:
        # Diminishing-returns combination: 1 - Π(1-v)
        x = 1.0
        for v in vals:
            x *= 1.0 - max(0.0, min(1.0, v))
        return 1.0 - x

    return {
        "lipolytic": soft_or([a.lipolytic for a in agents]),
        "alpha2_antagonist": soft_or([a.alpha2_antagonist for a in agents]),
        "thermogenic": soft_or([a.thermogenic for a in agents]),
        "appetite_suppress": soft_or([a.appetite_suppress for a in agents]),
        "diuretic": soft_or([max(0.0, a.diuretic) for a in agents]),
        "insulin_sensitizer": soft_or([a.insulin_sensitizer for a in agents]),
        "agents": [a.to_dict() for a in agents],
    }
