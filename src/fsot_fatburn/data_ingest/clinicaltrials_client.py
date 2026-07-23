"""ClinicalTrials.gov v2 pack — obesity / lipolysis / weight-loss studies."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests

from ..paths import load_config, project_path, ensure_dirs

DEFAULT_QUERIES = [
    "obesity weight loss drug",
    "semaglutide obesity",
    "tirzepatide obesity",
    "orlistat weight",
    "phentermine topiramate",
    "liraglutide weight management",
    "bupropion naltrexone obesity",
    "metformin weight loss",
    "green tea catechin weight",
    "caffeine thermogenesis obesity",
    "yohimbine body composition",
    "capsaicin energy expenditure",
    "forskolin body fat",
    "exercise high intensity fat loss",
    "intermittent fasting obesity",
    "visceral adipose tissue reduction",
    "lipolysis catecholamine adipose",
    "GLP-1 receptor agonist weight",
]


def _session() -> requests.Session:
    cfg = load_config()
    s = requests.Session()
    s.headers.update({"User-Agent": cfg["apis"]["user_agent"]})
    return s


def fetch_studies(query: str, page_size: int = 20) -> Dict[str, Any]:
    cfg = load_config()
    base = cfg["apis"]["clinicaltrials"].rstrip("/")
    url = f"{base}/studies"
    params = {
        "query.term": query,
        "pageSize": page_size,
        "format": "json",
    }
    r = _session().get(url, params=params, timeout=90)
    r.raise_for_status()
    data = r.json()
    data["query"] = query
    return data


def _flatten_study(study: dict, query: str) -> dict:
    proto = study.get("protocolSection") or {}
    ident = proto.get("identificationModule") or {}
    status = proto.get("statusModule") or {}
    design = proto.get("designModule") or {}
    arms = proto.get("armsInterventionsModule") or {}
    outcomes = proto.get("outcomesModule") or {}
    conditions = proto.get("conditionsModule") or {}
    desc = proto.get("descriptionModule") or {}

    interventions = []
    for iv in arms.get("interventions") or []:
        interventions.append({
            "type": iv.get("type"),
            "name": iv.get("name"),
            "description": (iv.get("description") or "")[:400],
        })

    primary = []
    for o in outcomes.get("primaryOutcomes") or []:
        primary.append({
            "measure": o.get("measure"),
            "description": (o.get("description") or "")[:300],
            "timeFrame": o.get("timeFrame"),
        })

    return {
        "query": query,
        "nct_id": ident.get("nctId"),
        "title": ident.get("briefTitle") or ident.get("officialTitle"),
        "overall_status": status.get("overallStatus"),
        "start_date": (status.get("startDateStruct") or {}).get("date"),
        "completion_date": (status.get("completionDateStruct") or {}).get("date"),
        "study_type": design.get("studyType"),
        "phases": design.get("phases") or [],
        "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
        "conditions": conditions.get("conditions") or [],
        "interventions": interventions,
        "primary_outcomes": primary[:5],
        "brief_summary": (desc.get("briefSummary") or "")[:1200],
    }


def build_clinicaltrials_obesity_pack(
    queries: Optional[List[str]] = None,
    page_size: int = 15,
) -> Dict[str, Any]:
    ensure_dirs()
    queries = queries or DEFAULT_QUERIES
    cache_dir = project_path("data", "cache", "clinical")
    cache_dir.mkdir(parents=True, exist_ok=True)

    studies: List[dict] = []
    errors: List[dict] = []
    seen = set()

    for q in queries:
        cache_path = cache_dir / f"ct_{abs(hash(q))}.json"
        try:
            if cache_path.is_file():
                data = json.loads(cache_path.read_text(encoding="utf-8"))
            else:
                data = fetch_studies(q, page_size=page_size)
                cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                time.sleep(0.3)
            for st in data.get("studies") or []:
                row = _flatten_study(st, q)
                nct = row.get("nct_id")
                if not nct or nct in seen:
                    continue
                seen.add(nct)
                studies.append(row)
        except Exception as e:
            errors.append({"query": q, "error": str(e)})

    # Agent hit counts from intervention names
    agent_hits: Dict[str, int] = {}
    keywords = [
        "semaglutide", "tirzepatide", "liraglutide", "orlistat", "phentermine",
        "metformin", "caffeine", "yohimbine", "capsaicin", "green tea",
        "exercise", "fasting", "bupropion", "naltrexone", "topiramate",
    ]
    for s in studies:
        blob = " ".join(
            [(i.get("name") or "") + " " + (i.get("description") or "") for i in s.get("interventions") or []]
        ).lower()
        blob += " " + (s.get("title") or "").lower()
        for k in keywords:
            if k in blob:
                agent_hits[k] = agent_hits.get(k, 0) + 1

    pack = {
        "source": "clinicaltrials.gov/api/v2",
        "query_count": len(queries),
        "study_count": len(studies),
        "agent_hits": dict(sorted(agent_hits.items(), key=lambda x: -x[1])),
        "errors": errors,
        "studies": studies,
    }
    out = project_path("data", "derived", "clinicaltrials_obesity_pack.json")
    out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    return pack
