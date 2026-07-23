"""
Tune compound mechanism scores from published trial anchors.

FSOT seeds stay fixed. Only intervention routing magnitudes change.
"""

from __future__ import annotations

import json
from typing import Dict, List, Any, Optional

from ..paths import project_path
from .compounds import CompoundAgent, SEED_COMPOUNDS, load_compound_catalog


def load_trial_anchors() -> List[dict]:
    path = project_path("data", "seed", "trial_effect_anchors.json")
    return json.loads(path.read_text(encoding="utf-8"))["anchors"]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def anchor_to_score_deltas(anchor: dict) -> Dict[str, float]:
    """
    Map a literature endpoint onto mechanism score targets (0–1).

    These are effect-size → sim-routing conversions, not free least-squares
    on FSOT constants.
    """
    route = anchor.get("route") or ""
    measured = float(anchor.get("measured") or 0)
    placebo = float(anchor.get("placebo") or 0)
    duration_w = max(1.0, float(anchor.get("duration_weeks") or 12))
    unit = anchor.get("unit") or ""
    net = measured - placebo

    out: Dict[str, float] = {}

    if unit in ("percent_body_weight", "percent_body_weight_vs_placebo"):
        # ~15% over 68w is very strong appetite route
        # Normalize: 15% loss → appetite ~0.95; 3% → ~0.35
        strength = min(1.0, abs(net) / 18.0)
        if "appetite" in route or "intake" in route:
            out["appetite_suppress"] = _clamp01(0.15 + 0.85 * strength)
        if "malabsorption" in route:
            out["appetite_suppress"] = _clamp01(0.05 + 0.25 * strength)
            out["lipolytic"] = _clamp01(0.05 + 0.1 * strength)

    elif unit == "kg":
        # kg loss over duration → weekly rate
        weekly = abs(net) / (duration_w / 4.0)  # per ~month-ish strength
        strength = min(1.0, abs(net) / 8.0)
        if "appetite" in route or "intake" in route:
            out["appetite_suppress"] = _clamp01(0.1 + 0.75 * strength)
        if "insulin" in route:
            out["insulin_sensitizer"] = _clamp01(0.2 + 0.55 * strength)
            out["appetite_suppress"] = max(out.get("appetite_suppress", 0), _clamp01(0.05 + 0.2 * strength))
        if "thermogenesis" in route:
            out["thermogenic"] = _clamp01(0.15 + 0.4 * strength)
        if "lipolysis" in route or "camp" in route:
            out["lipolytic"] = _clamp01(0.15 + 0.5 * strength)
        if "shuttle" in route:
            out["lipolytic"] = _clamp01(0.05 + 0.2 * strength)
        if "glycemic" in route or "carb_absorption" in route:
            out["insulin_sensitizer"] = _clamp01(0.15 + 0.35 * strength)

    elif unit == "kcal_day":
        # 50 kcal → mild; 200 kcal → strong thermogenic
        strength = min(1.0, abs(net) / 200.0)
        out["thermogenic"] = _clamp01(0.1 + 0.7 * strength)
        if "appetite" in route:
            out["appetite_suppress"] = _clamp01(0.1 + 0.4 * strength)

    elif unit in ("kg_water", "kg_water_gain"):
        strength = min(1.0, abs(net) / 2.0)
        sign = 1.0 if net < 0 or unit == "kg_water" else -1.0
        # diuretic positive = water loss; creatine negative diuretic = water gain
        if "water_gain" in unit or net > 0 and "gain" in unit:
            out["diuretic"] = -_clamp01(0.2 + 0.5 * strength)
        else:
            out["diuretic"] = _clamp01(0.3 + 0.65 * strength) * (1 if net <= 0 else 1)

    elif unit == "percent_body_fat_points_approx":
        strength = min(1.0, abs(net) / 6.0)
        out["lipolytic"] = _clamp01(0.2 + 0.55 * strength)

    if "alpha2" in route:
        out["alpha2_antagonist"] = _clamp01(0.5 + 0.4 * min(1.0, abs(net) / 3.0))
        out["lipolytic"] = max(out.get("lipolytic", 0), _clamp01(0.35 + 0.3 * min(1.0, abs(net) / 3.0)))

    return out


def tune_compounds_from_trials(
    compounds: Optional[List[CompoundAgent]] = None,
    blend: float = 0.65,
) -> List[dict]:
    """
    blend: weight on literature-derived target vs seed prior (0=seed only, 1=trial only).
    """
    compounds = compounds or list(SEED_COMPOUNDS)
    anchors = load_trial_anchors()
    by_agent: Dict[str, List[dict]] = {}
    for a in anchors:
        by_agent.setdefault(a["agent_id"], []).append(a)

    tuned = []
    report_rows = []
    for c in compounds:
        row = c.to_dict()
        agent_anchors = by_agent.get(c.id, [])
        if not agent_anchors:
            row["tune_source"] = "seed_only"
            tuned.append(row)
            continue

        # Merge deltas across anchors (soft max per key)
        targets: Dict[str, float] = {}
        for a in agent_anchors:
            deltas = anchor_to_score_deltas(a)
            for k, v in deltas.items():
                targets[k] = max(targets.get(k, 0.0), v)

        fields = [
            "lipolytic", "alpha2_antagonist", "thermogenic",
            "appetite_suppress", "diuretic", "insulin_sensitizer",
        ]
        before = {f: row[f] for f in fields}
        after = {}
        for f in fields:
            seed_v = float(row[f])
            if f in targets:
                # Allow diuretic negative (creatine)
                tgt = targets[f]
                if f == "diuretic" and tgt < 0:
                    new_v = (1 - blend) * seed_v + blend * tgt
                else:
                    new_v = (1 - blend) * seed_v + blend * max(0.0, tgt)
                    new_v = _clamp01(new_v) if f != "diuretic" else new_v
                row[f] = new_v
            after[f] = row[f]

        row["tune_source"] = "seed+trial"
        row["trial_anchors"] = [
            {"trial": a.get("trial"), "citation": a.get("citation"), "measured": a.get("measured"), "unit": a.get("unit")}
            for a in agent_anchors
        ]
        row["source"] = "seed+trial_tuned"
        tuned.append(row)
        report_rows.append({
            "agent_id": c.id,
            "before": before,
            "after": after,
            "targets": targets,
            "anchors": len(agent_anchors),
        })

    out = project_path("data", "derived", "compounds_trial_tuned.json")
    out.write_text(json.dumps(tuned, indent=2), encoding="utf-8")
    project_path("data", "derived", "compound_tune_report.json").write_text(
        json.dumps({"blend": blend, "rows": report_rows}, indent=2), encoding="utf-8"
    )
    # Also refresh compounds_enriched if present — merge props
    enriched_path = project_path("data", "derived", "compounds_enriched.json")
    if enriched_path.is_file():
        enriched = json.loads(enriched_path.read_text(encoding="utf-8"))
        by_id = {r["id"]: r for r in tuned}
        merged = []
        for e in enriched:
            t = by_id.get(e["id"], e)
            m = dict(e)
            for f in ("lipolytic", "alpha2_antagonist", "thermogenic",
                      "appetite_suppress", "diuretic", "insulin_sensitizer",
                      "tune_source", "trial_anchors", "source"):
                if f in t:
                    m[f] = t[f]
            merged.append(m)
        enriched_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    return tuned


def load_tuned_catalog() -> List[CompoundAgent]:
    path = project_path("data", "derived", "compounds_trial_tuned.json")
    if not path.is_file():
        return load_compound_catalog()
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    fields = CompoundAgent.__dataclass_fields__
    for row in data:
        kwargs = {k: row[k] for k in fields if k in row}
        out.append(CompoundAgent(**kwargs))
    return out
