"""
Population anthropometry grid — select and critique toward personal measures.

Loads seed archetypes spanning lean→extreme tails, calibrates each via Navy
composition + depot mapping, and matches user measurements to nearest archetypes.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple

from ..paths import project_path, ensure_dirs
from .calibration import Anthropometry, calibrate_subject, CalibrationResult


def load_seed_grid() -> dict:
    path = project_path("data", "seed", "anthropometry_population_grid.json")
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class UserMeasures:
    sex: str
    height_cm: float
    weight_kg: float
    waist_cm: float
    hip_cm: float
    neck_cm: float
    age_y: float = 35.0

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_navy(sex: str, height: float, neck: float, waist: float, hip: float) -> Optional[float]:
    try:
        from .calibration import navy_body_fat_pct
        return navy_body_fat_pct(
            sex=sex, height_cm=height, neck_cm=neck, waist_cm=waist, hip_cm=hip
        )
    except Exception:
        return None


def calibrate_archetype(row: dict) -> dict:
    """Run full calibration on one seed archetype; attach Navy-safe fallbacks."""
    anthro = Anthropometry(
        sex=row["sex"],
        age_y=float(row.get("age_y", 35)),
        height_cm=float(row["height_cm"]),
        weight_kg=float(row["weight_kg"]),
        waist_cm=float(row["waist_cm"]),
        hip_cm=float(row["hip_cm"]),
        neck_cm=float(row["neck_cm"]),
    )
    try:
        cal = calibrate_subject(anthro)
        cal_dict = cal.to_dict()
        subject = cal.to_subject_dict()
        ok = True
        err = None
    except Exception as e:
        # Extreme geometries can break Navy log domain — still keep raw measures
        bf = _safe_navy(row["sex"], row["height_cm"], row["neck_cm"], row["waist_cm"], row["hip_cm"])
        cal_dict = {
            "method": "raw_only",
            "error": str(e),
            "body_fat_pct": bf,
            "whr": row["waist_cm"] / row["hip_cm"] if row["hip_cm"] else None,
        }
        subject = {
            "sex": row["sex"],
            "age_y": row.get("age_y", 35),
            "height_cm": row["height_cm"],
            "weight_kg": row["weight_kg"],
            "waist_cm": row["waist_cm"],
            "hip_cm": row["hip_cm"],
            "neck_cm": row["neck_cm"],
            "body_fat_pct": bf or 25.0,
            "somatotype": "meso_endo",
        }
        ok = False
        err = str(e)

    whr = row["waist_cm"] / row["hip_cm"] if row["hip_cm"] else None
    whtr = row["waist_cm"] / row["height_cm"] if row["height_cm"] else None
    bmi = row["weight_kg"] / ((row["height_cm"] / 100.0) ** 2)

    return {
        "id": row["id"],
        "label": row["label"],
        "seed": row,
        "calibration_ok": ok,
        "calibration_error": err,
        "calibration": cal_dict,
        "subject": subject,
        "derived": {
            "bmi": round(bmi, 2),
            "whr": round(whr, 3) if whr else None,
            "whtr": round(whtr, 3) if whtr else None,
            "body_fat_pct": cal_dict.get("body_fat_pct") or cal_dict.get("navy_bf_pct"),
            "somatotype": subject.get("somatotype"),
            "fat_mass_kg": cal_dict.get("fat_mass_kg"),
            "lean_mass_kg": cal_dict.get("lean_mass_kg"),
            "depot_fractions": cal_dict.get("depot_fractions") or subject.get("depot_fraction_overrides"),
        },
        "bands": {
            "shape": row.get("shape"),
            "scale": row.get("scale"),
            "adiposity_band": row.get("adiposity_band"),
            "literature_anchor": row.get("literature_anchor"),
        },
    }


def build_population_catalog(*, run_sims: bool = False, sim_days: int = 14) -> dict:
    """Calibrate all seed archetypes → derived catalog JSON."""
    ensure_dirs()
    seed = load_seed_grid()
    entries = []
    for row in seed["archetypes"]:
        entry = calibrate_archetype(row)
        if run_sims and entry["calibration_ok"]:
            try:
                from .energy import SubjectProfile
                from ..sim.fat_cell_sim import FatBurnSimulator, SimConfig
                sub = SubjectProfile.from_calibration_dict(
                    entry["subject"],
                    age_y=row.get("age_y", 35),
                    activity_factor=1.35,
                    steps_per_day=7000,
                )
                res = FatBurnSimulator(SimConfig(
                    days=sim_days,
                    subject=sub,
                    diet_id="moderate_deficit_balanced",
                    exercise_ids=["resistance_full_45", "zone2_bike_40", "steps_10k"],
                    compound_ids=["caffeine", "egcg"],
                    label=row["id"],
                )).run()
                entry["sim_probe"] = {
                    "days": sim_days,
                    "fat_lost_kg": res.summary["fat_lost_kg"],
                    "scale_delta_kg": res.summary["scale_delta_kg"],
                    "mean_fat_burn_index": res.summary["mean_fat_burn_index"],
                    "mean_daily_deficit_kcal": res.summary["mean_daily_deficit_kcal"],
                    "depot_delta_kg": res.summary["depot_delta_kg"],
                    "protocol": res.summary["protocol"],
                }
            except Exception as e:
                entry["sim_probe"] = {"error": str(e)}
        entries.append(entry)

    # Axis summary stats from successful calibrations
    waists = [e["seed"]["waist_cm"] for e in entries]
    hips = [e["seed"]["hip_cm"] for e in entries]
    necks = [e["seed"]["neck_cm"] for e in entries]
    bfs = [e["derived"]["body_fat_pct"] for e in entries if e["derived"].get("body_fat_pct") is not None]

    catalog = {
        "version": seed.get("version"),
        "description": seed.get("description"),
        "references": seed.get("references"),
        "measurement_axes": seed.get("measurement_axes"),
        "n_archetypes": len(entries),
        "n_calibrated_ok": sum(1 for e in entries if e["calibration_ok"]),
        "range_summary": {
            "waist_cm": {"min": min(waists), "max": max(waists)},
            "hip_cm": {"min": min(hips), "max": max(hips)},
            "neck_cm": {"min": min(necks), "max": max(necks)},
            "body_fat_pct": {
                "min": min(bfs) if bfs else None,
                "max": max(bfs) if bfs else None,
            },
            "sex_counts": {
                "male": sum(1 for e in entries if e["seed"]["sex"] == "male"),
                "female": sum(1 for e in entries if e["seed"]["sex"] == "female"),
            },
        },
        "archetypes": entries,
    }
    out = project_path("data", "derived", "population_anthropometry_catalog.json")
    out.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    # Compact selection table for humans
    table = []
    for e in entries:
        table.append({
            "id": e["id"],
            "label": e["label"],
            "sex": e["seed"]["sex"],
            "height_cm": e["seed"]["height_cm"],
            "weight_kg": e["seed"]["weight_kg"],
            "waist_cm": e["seed"]["waist_cm"],
            "hip_cm": e["seed"]["hip_cm"],
            "neck_cm": e["seed"]["neck_cm"],
            "bmi": e["derived"]["bmi"],
            "whr": e["derived"]["whr"],
            "whtr": e["derived"]["whtr"],
            "body_fat_pct": e["derived"].get("body_fat_pct"),
            "somatotype": e["derived"].get("somatotype"),
            "shape": e["bands"]["shape"],
            "adiposity_band": e["bands"]["adiposity_band"],
            "literature_anchor": e["bands"]["literature_anchor"],
            "sim_fat_lost_kg": (e.get("sim_probe") or {}).get("fat_lost_kg"),
        })
    project_path("data", "derived", "population_selection_table.json").write_text(
        json.dumps(table, indent=2), encoding="utf-8"
    )
    return catalog


def load_population_catalog() -> dict:
    path = project_path("data", "derived", "population_anthropometry_catalog.json")
    if not path.is_file():
        return build_population_catalog(run_sims=False)
    return json.loads(path.read_text(encoding="utf-8"))


def _feature_vector(sex: str, height: float, weight: float, waist: float, hip: float, neck: float) -> List[float]:
    """Normalized features for nearest-neighbor (sex filtered separately)."""
    # Rough population scales for z-like normalization
    return [
        height / 180.0,
        weight / 100.0,
        waist / 100.0,
        hip / 100.0,
        neck / 40.0,
        (waist / hip) if hip else 1.0,
        (waist / height) if height else 0.5,
        (weight / ((height / 100.0) ** 2)) / 30.0,  # BMI / 30
    ]


def _distance(a: List[float], b: List[float], weights: Optional[List[float]] = None) -> float:
    w = weights or [1.2, 1.0, 2.0, 1.5, 1.0, 2.0, 1.8, 1.0]
    # waist, WHR, WHtR weighted higher — selection is circumference-first
    s = 0.0
    for i, (x, y) in enumerate(zip(a, b)):
        wi = w[i] if i < len(w) else 1.0
        s += wi * (x - y) ** 2
    return math.sqrt(s)


def match_user_to_archetypes(
    user: UserMeasures,
    *,
    top_k: int = 5,
    same_sex_only: bool = True,
    catalog: Optional[dict] = None,
) -> dict:
    """
    Find nearest population archetypes and critique measurement deltas.
    """
    catalog = catalog or load_population_catalog()
    uvec = _feature_vector(
        user.sex, user.height_cm, user.weight_kg,
        user.waist_cm, user.hip_cm, user.neck_cm,
    )
    u_whr = user.waist_cm / user.hip_cm
    u_whtr = user.waist_cm / user.height_cm
    u_bmi = user.weight_kg / ((user.height_cm / 100.0) ** 2)
    u_navy = _safe_navy(user.sex, user.height_cm, user.neck_cm, user.waist_cm, user.hip_cm)

    scored = []
    for e in catalog["archetypes"]:
        if same_sex_only and e["seed"]["sex"].lower() != user.sex.lower():
            # allow prefix match male/female
            if not e["seed"]["sex"].lower().startswith(user.sex.lower()[:1]):
                continue
        s = e["seed"]
        avec = _feature_vector(
            s["sex"], s["height_cm"], s["weight_kg"],
            s["waist_cm"], s["hip_cm"], s["neck_cm"],
        )
        dist = _distance(uvec, avec)
        deltas = {
            "height_cm": round(user.height_cm - s["height_cm"], 1),
            "weight_kg": round(user.weight_kg - s["weight_kg"], 1),
            "waist_cm": round(user.waist_cm - s["waist_cm"], 1),
            "hip_cm": round(user.hip_cm - s["hip_cm"], 1),
            "neck_cm": round(user.neck_cm - s["neck_cm"], 1),
            "whr": round(u_whr - (s["waist_cm"] / s["hip_cm"]), 3),
            "whtr": round(u_whtr - (s["waist_cm"] / s["height_cm"]), 3),
            "bmi": round(u_bmi - e["derived"]["bmi"], 2),
        }
        # Human critique strings
        critique = []
        if abs(deltas["waist_cm"]) >= 3:
            critique.append(
                f"Your waist is {abs(deltas['waist_cm']):.0f} cm "
                f"{'larger' if deltas['waist_cm']>0 else 'smaller'} than this archetype."
            )
        if abs(deltas["hip_cm"]) >= 3:
            critique.append(
                f"Your hips are {abs(deltas['hip_cm']):.0f} cm "
                f"{'larger' if deltas['hip_cm']>0 else 'smaller'} than this archetype."
            )
        if abs(deltas["neck_cm"]) >= 1.5:
            critique.append(
                f"Your neck is {abs(deltas['neck_cm']):.1f} cm "
                f"{'larger' if deltas['neck_cm']>0 else 'smaller'} than this archetype."
            )
        if deltas["whr"] >= 0.03:
            critique.append("Higher WHR than archetype → more android/central pattern than template.")
        elif deltas["whr"] <= -0.03:
            critique.append("Lower WHR than archetype → more gynoid/pear bias than template.")
        if abs(deltas["weight_kg"]) >= 5:
            critique.append(
                f"Mass offset {deltas['weight_kg']:+.1f} kg vs archetype — scale protocols to your TDEE."
            )
        if not critique:
            critique.append("Very close match across waist/hip/neck/height/weight.")

        scored.append({
            "distance": round(dist, 4),
            "id": e["id"],
            "label": e["label"],
            "seed": s,
            "derived": e["derived"],
            "bands": e["bands"],
            "deltas_user_minus_archetype": deltas,
            "critique": critique,
            "sim_probe": e.get("sim_probe"),
            "subject_path_hint": f"data/derived/population_subjects/{e['id']}.json",
        })

    scored.sort(key=lambda x: x["distance"])
    top = scored[:top_k]

    # Band placement for user alone
    waist_axis = catalog.get("measurement_axes", {}).get("waist_cm", {})
    sex_key = "male_approx" if user.sex.lower().startswith("m") else "female_approx"
    waist_bands = waist_axis.get(sex_key, {})
    band_name = "unclassified"
    # find closest named band
    if waist_bands:
        band_name = min(waist_bands.items(), key=lambda kv: abs(kv[1] - user.waist_cm))[0]

    result = {
        "user": {
            **user.to_dict(),
            "bmi": round(u_bmi, 2),
            "whr": round(u_whr, 3),
            "whtr": round(u_whtr, 3),
            "navy_bf_pct": u_navy,
            "waist_band_nearest_label": band_name,
        },
        "matches": top,
        "best": top[0] if top else None,
        "how_to_use": [
            "Pick the closest archetype (or 2–3 neighbors) as your selection baseline.",
            "Read critique deltas: positive waist_cm means you are larger-waisted than that template.",
            "Run sims on the archetype subject JSON, then re-run calibrate_subject with YOUR exact measures to refine.",
            "Do not treat archetype BF% as your diagnosis — it is a Navy-estimated composition scaffold.",
            "Extremes exist so the selector has bounds; most people fall between mid-grid nodes.",
        ],
        "grid_range": catalog.get("range_summary"),
    }
    return result


def export_population_subjects(catalog: Optional[dict] = None) -> int:
    """Write each archetype subject JSON for run_sim --subject-json."""
    catalog = catalog or load_population_catalog()
    out_dir = project_path("data", "derived", "population_subjects")
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for e in catalog["archetypes"]:
        if not e.get("subject"):
            continue
        path = out_dir / f"{e['id']}.json"
        # ensure age present
        sub = dict(e["subject"])
        sub.setdefault("age_y", e["seed"].get("age_y", 35))
        sub.setdefault("activity_factor", 1.35)
        sub.setdefault("steps_per_day", 7000)
        path.write_text(json.dumps(sub, indent=2), encoding="utf-8")
        n += 1
    return n
