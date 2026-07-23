"""ChEMBL API client for pharmacology / medical profiles."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests

from ..paths import load_config, project_path, ensure_dirs


def _session() -> requests.Session:
    cfg = load_config()
    s = requests.Session()
    s.headers.update({
        "User-Agent": cfg["apis"]["user_agent"],
        "Accept": "application/json",
    })
    return s


def fetch_chembl_molecule(chembl_id: str, session: Optional[requests.Session] = None) -> dict:
    cfg = load_config()
    base = cfg["apis"]["chembl"].rstrip("/")
    sess = session or _session()
    cache = project_path("data", "cache", "chembl", f"{chembl_id}.json")
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))
    url = f"{base}/molecule/{chembl_id}.json"
    r = sess.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, indent=2), encoding="utf-8")
    time.sleep(0.15)
    return data


def fetch_chembl_molecules(chembl_ids: List[str]) -> List[dict]:
    ensure_dirs()
    sess = _session()
    out = []
    for cid in chembl_ids:
        try:
            out.append({"chembl_id": cid, "ok": True, "data": fetch_chembl_molecule(cid, sess)})
        except Exception as e:
            out.append({"chembl_id": cid, "ok": False, "error": str(e)})
    path = project_path("data", "derived", "chembl_fetch_batch.json")
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def search_chembl_by_name(name: str, limit: int = 5) -> List[dict]:
    cfg = load_config()
    base = cfg["apis"]["chembl"].rstrip("/")
    sess = _session()
    url = f"{base}/molecule/search.json"
    r = sess.get(url, params={"q": name, "limit": limit}, timeout=60)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("molecules") or data.get("page_meta") and data.get("molecules") or []
