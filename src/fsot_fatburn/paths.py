"""Path resolution for the FSOT Fat Burn project (paths relative to the project root; env overrides)."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


_FSOT_PATH_KEYS = (
    "archive_root",
    "lean_hub",
    "compute_module",
    "public_data",
    "smiles_dataset",
    "pubchem_cache",
    "chembl_cache",
)
_ENV_REF = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")


def _resolve_config_path(value: str) -> str:
    """Expand ${VAR} / ${VAR:-default} and make relative paths relative to PROJECT_ROOT."""
    expanded = _ENV_REF.sub(lambda m: os.environ.get(m.group(1)) or (m.group(2) or ""), value)
    p = Path(expanded).expanduser()
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    fsot = cfg.get("fsot") or {}
    for key in _FSOT_PATH_KEYS:
        if isinstance(fsot.get(key), str):
            fsot[key] = _resolve_config_path(fsot[key])
    return cfg


def project_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)


def ensure_dirs() -> None:
    cfg = load_config()
    for key in ("seed", "cache", "derived", "reports"):
        rel = cfg["paths"][key]
        (PROJECT_ROOT / rel).mkdir(parents=True, exist_ok=True)
    for sub in (
        "cache/pubchem",
        "cache/chembl",
        "cache/openfda",
        "cache/clinical",
        "cache/food",
    ):
        (PROJECT_ROOT / "data" / sub).mkdir(parents=True, exist_ok=True)


def archive_path(key: str) -> Path:
    """Resolve a configured archive path from config.yaml fsot section."""
    cfg = load_config()
    p = Path(cfg["fsot"][key])
    if not p.exists():
        # Fall back to env override
        env = os.environ.get("FSOT_ARCHIVE_ROOT")
        if env and key == "archive_root":
            return Path(env)
    return p
