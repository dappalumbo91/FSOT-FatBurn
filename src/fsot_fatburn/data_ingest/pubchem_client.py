"""PubChem PUG REST client — enrich compounds with SMILES + properties."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from ..paths import load_config, project_path, ensure_dirs
from ..interventions.compounds import SEED_COMPOUNDS, CompoundAgent


def _session() -> requests.Session:
    cfg = load_config()
    s = requests.Session()
    s.headers.update({"User-Agent": cfg["apis"]["user_agent"]})
    return s


def fetch_pubchem_cid(cid: int, session: Optional[requests.Session] = None) -> Dict[str, Any]:
    cfg = load_config()
    base = cfg["apis"]["pubchem_pug"]
    sess = session or _session()
    cache = project_path("data", "cache", "pubchem", f"cid_{cid}.json")
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))

    url = f"{base}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IUPACName,CanonicalSMILES,IsomericSMILES,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount/JSON"
    r = sess.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()
    cache.write_text(json.dumps(data, indent=2), encoding="utf-8")
    time.sleep(0.2)  # be polite to NCBI
    return data


def fetch_pubchem_cids(cids: List[int]) -> List[Dict[str, Any]]:
    ensure_dirs()
    sess = _session()
    out = []
    for cid in cids:
        try:
            out.append({"cid": cid, "ok": True, "data": fetch_pubchem_cid(cid, sess)})
        except Exception as e:
            out.append({"cid": cid, "ok": False, "error": str(e)})
    path = project_path("data", "derived", "pubchem_fetch_batch.json")
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def _props_from_pug(data: dict) -> dict:
    try:
        props = data["PropertyTable"]["Properties"][0]
    except (KeyError, IndexError, TypeError):
        return {}
    return props


def enrich_compounds_pubchem(compounds: Optional[List[CompoundAgent]] = None) -> List[dict]:
    """Merge PubChem properties into seed catalog; write compounds_enriched.json."""
    ensure_dirs()
    compounds = compounds or list(SEED_COMPOUNDS)
    cids = [c.pubchem_cid for c in compounds if c.pubchem_cid]
    batch = {row["cid"]: row for row in fetch_pubchem_cids(cids)}

    enriched = []
    for c in compounds:
        row = c.to_dict()
        if c.pubchem_cid and c.pubchem_cid in batch and batch[c.pubchem_cid].get("ok"):
            props = _props_from_pug(batch[c.pubchem_cid]["data"])
            row["molecular_formula"] = props.get("MolecularFormula") or row.get("molecular_formula")
            row["molecular_weight"] = (
                float(props["MolecularWeight"]) if props.get("MolecularWeight") else row.get("molecular_weight")
            )
            row["iupac_name"] = props.get("IUPACName") or row.get("iupac_name")
            row["smiles"] = (
                props.get("CanonicalSMILES")
                or props.get("IsomericSMILES")
                or row.get("smiles")
            )
            row["xlogp"] = props.get("XLogP")
            row["tpsa"] = props.get("TPSA")
            row["hbd"] = props.get("HBondDonorCount")
            row["hba"] = props.get("HBondAcceptorCount")
            row["rotatable_bonds"] = props.get("RotatableBondCount")
            row["source"] = "seed+pubchem"
        enriched.append(row)

    out = project_path("data", "derived", "compounds_enriched.json")
    out.write_text(json.dumps(enriched, indent=2), encoding="utf-8")
    return enriched


def search_pubchem_name(name: str) -> Optional[int]:
    """Resolve a compound name to CID."""
    cfg = load_config()
    base = cfg["apis"]["pubchem_pug"]
    sess = _session()
    url = f"{base}/compound/name/{requests.utils.quote(name)}/cids/JSON"
    r = sess.get(url, timeout=60)
    if r.status_code != 200:
        return None
    data = r.json()
    try:
        return int(data["IdentifierList"]["CID"][0])
    except (KeyError, IndexError, TypeError, ValueError):
        return None
