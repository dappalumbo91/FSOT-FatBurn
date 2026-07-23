"""OpenFDA drug label pack — obesity / weight / lipolysis agents."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from ..paths import load_config, project_path, ensure_dirs

# Queries covering medical weight / fat / appetite space
DEFAULT_QUERIES = [
    'indications_and_usage:"weight loss"',
    'indications_and_usage:obesity',
    'indications_and_usage:"weight management"',
    'indications_and_usage:"overweight"',
    'openfda.generic_name:semaglutide',
    'openfda.generic_name:tirzepatide',
    'openfda.generic_name:orlistat',
    'openfda.generic_name:phentermine',
    'openfda.generic_name:liraglutide',
    'openfda.generic_name:naltrexone',
    'openfda.generic_name:bupropion',
    'openfda.generic_name:metformin',
    'openfda.brand_name:Wegovy',
    'openfda.brand_name:Ozempic',
    'openfda.brand_name:Mounjaro',
    'openfda.brand_name:Zepbound',
    'openfda.brand_name:Xenical',
    'openfda.brand_name:Alli',
    'openfda.brand_name:Qsymia',
    'openfda.brand_name:Contrave',
    'openfda.brand_name:Saxenda',
]


def _session() -> requests.Session:
    cfg = load_config()
    s = requests.Session()
    s.headers.update({"User-Agent": cfg["apis"]["user_agent"]})
    return s


def fetch_openfda_search(query: str, limit: int = 25) -> Dict[str, Any]:
    cfg = load_config()
    base = cfg["apis"]["openfda"].rstrip("/")
    # openfda base is https://api.fda.gov/drug — label endpoint
    url = f"{base}/label.json"
    params = {"search": query, "limit": limit}
    sess = _session()
    r = sess.get(url, params=params, timeout=90)
    if r.status_code == 404:
        return {"meta": {"results": {"total": 0}}, "results": [], "query": query}
    r.raise_for_status()
    data = r.json()
    data["query"] = query
    return data


def _extract_row(result: dict, query: str) -> dict:
    openfda = result.get("openfda") or {}
    return {
        "query": query,
        "id": result.get("id"),
        "set_id": result.get("set_id"),
        "effective_time": result.get("effective_time"),
        "brand_name": (openfda.get("brand_name") or [None])[0],
        "generic_name": (openfda.get("generic_name") or [None])[0],
        "substance_name": openfda.get("substance_name") or [],
        "manufacturer_name": (openfda.get("manufacturer_name") or [None])[0],
        "product_type": (openfda.get("product_type") or [None])[0],
        "route": openfda.get("route") or [],
        "rxcui": openfda.get("rxcui") or [],
        "unii": openfda.get("unii") or [],
        "pharm_class_epc": openfda.get("pharm_class_epc") or [],
        "indications_and_usage": (result.get("indications_and_usage") or [""])[0][:2000],
        "warnings": (result.get("warnings") or result.get("boxed_warning") or [""])[0][:1500]
        if (result.get("warnings") or result.get("boxed_warning"))
        else "",
        "adverse_reactions": (result.get("adverse_reactions") or [""])[0][:1500]
        if result.get("adverse_reactions")
        else "",
        "mechanism": (result.get("mechanism_of_action") or [""])[0][:1500]
        if result.get("mechanism_of_action")
        else "",
    }


def build_openfda_obesity_pack(
    queries: Optional[List[str]] = None,
    limit_per_query: int = 15,
) -> Dict[str, Any]:
    """Fetch and dedupe OpenFDA labels for obesity / weight agents."""
    ensure_dirs()
    queries = queries or DEFAULT_QUERIES
    cache_dir = project_path("data", "cache", "openfda")
    cache_dir.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    errors: List[dict] = []
    seen = set()

    for q in queries:
        safe = quote(q, safe="")[:80]
        cache_path = cache_dir / f"q_{abs(hash(q))}.json"
        try:
            if cache_path.is_file():
                data = json.loads(cache_path.read_text(encoding="utf-8"))
            else:
                data = fetch_openfda_search(q, limit=limit_per_query)
                cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                time.sleep(0.25)
            for res in data.get("results") or []:
                row = _extract_row(res, q)
                key = row.get("id") or (row.get("brand_name"), row.get("generic_name"), row.get("set_id"))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
        except Exception as e:
            errors.append({"query": q, "error": str(e)})

    pack = {
        "source": "open.fda.gov/drug/label",
        "query_count": len(queries),
        "label_count": len(rows),
        "errors": errors,
        "labels": rows,
    }
    out = project_path("data", "derived", "openfda_obesity_pack.json")
    out.write_text(json.dumps(pack, indent=2), encoding="utf-8")

    # Compact index by generic name
    by_generic: Dict[str, List[dict]] = {}
    for r in rows:
        g = (r.get("generic_name") or "unknown").lower()
        by_generic.setdefault(g, []).append({
            "brand": r.get("brand_name"),
            "id": r.get("id"),
            "route": r.get("route"),
            "pharm_class": r.get("pharm_class_epc"),
        })
    project_path("data", "derived", "openfda_by_generic.json").write_text(
        json.dumps(by_generic, indent=2), encoding="utf-8"
    )
    return pack
