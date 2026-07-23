#!/usr/bin/env python3
"""Export Adipose_Lipolysis_Live_Panel into FSOT-2.1-Lean archive."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fsot_fatburn.paths import ensure_dirs
from fsot_fatburn.sim.export_adipose_panel import export_to_archive


def main() -> int:
    ensure_dirs()
    report = export_to_archive()
    print(json.dumps(report, indent=2))
    print(
        f"\nPanel records={report['record_count']} "
        f"pooled_median={report['pooled_median_error_pct']}% "
        f"Lean → {report['lean_module']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
