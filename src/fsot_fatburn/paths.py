"""Path resolution for the FSOT Fat Burn project (drive-letter portable within I:)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


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
