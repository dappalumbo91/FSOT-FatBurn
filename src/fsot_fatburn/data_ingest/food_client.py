"""
Food-level data: seed catalog + Open Food Facts + optional USDA FDC.

Builds meal insulin index from macros + glycemic index.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..paths import load_config, project_path, ensure_dirs


def _session() -> requests.Session:
    cfg = load_config()
    s = requests.Session()
    s.headers.update({"User-Agent": cfg["apis"]["user_agent"]})
    return s


def load_seed_foods() -> List[dict]:
    path = project_path("data", "seed", "foods_seed.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["foods"]


def fetch_openfoodfacts_search(query: str, page_size: int = 20) -> dict:
    cfg = load_config()
    base = cfg["apis"]["openfoodfacts"].rstrip("/")
    url = f"{base}/cgi/search.pl"
    params = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": page_size,
        "fields": "product_name,code,nutriments,nutriscore_grade,categories_tags,brands",
    }
    r = _session().get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def _off_to_food(product: dict, query: str) -> Optional[dict]:
    nutr = product.get("nutriments") or {}
    name = product.get("product_name") or query
    # Prefer per 100g
    def g(key: str) -> float:
        v = nutr.get(key)
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    carb = g("carbohydrates_100g")
    protein = g("proteins_100g")
    fat = g("fat_100g")
    fiber = g("fiber_100g")
    sugars = g("sugars_100g")
    kcal = g("energy-kcal_100g")
    if kcal <= 0 and (carb or protein or fat):
        kcal = carb * 4 + protein * 4 + fat * 9
    if kcal <= 0 and carb == 0 and protein == 0 and fat == 0:
        return None
    return {
        "id": f"off_{product.get('code') or name}",
        "name": name,
        "source": "openfoodfacts",
        "barcode": product.get("code"),
        "brands": product.get("brands"),
        "per_100g": {
            "kcal": kcal,
            "protein_g": protein,
            "carb_g": carb,
            "fat_g": fat,
            "fiber_g": fiber,
            "sugars_g": sugars,
        },
        "gi": None,  # unknown unless seed match
        "category": "off",
        "query": query,
    }


def fetch_usda_fdc_search(query: str, page_size: int = 10) -> dict:
    """Requires FDC_API_KEY environment variable."""
    key = os.environ.get("FDC_API_KEY") or os.environ.get("USDA_FDC_API_KEY")
    if not key:
        return {"error": "FDC_API_KEY not set", "foods": []}
    cfg = load_config()
    base = cfg["apis"]["usda_fdc"].rstrip("/")
    url = f"{base}/foods/search"
    r = _session().post(
        url,
        params={"api_key": key},
        json={"query": query, "pageSize": page_size},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def _usda_to_food(food: dict, query: str) -> Optional[dict]:
    nutrients = {n.get("nutrientName"): n.get("value") for n in food.get("foodNutrients") or []}

    def g(*names: str) -> float:
        for n in names:
            if n in nutrients and nutrients[n] is not None:
                try:
                    return float(nutrients[n])
                except (TypeError, ValueError):
                    pass
        return 0.0

    protein = g("Protein")
    fat = g("Total lipid (fat)", "Fat")
    carb = g("Carbohydrate, by difference", "Carbohydrate")
    fiber = g("Fiber, total dietary")
    sugars = g("Sugars, total including NLEA", "Sugars, total")
    kcal = g("Energy")
    if kcal <= 0:
        kcal = protein * 4 + carb * 4 + fat * 9
    return {
        "id": f"fdc_{food.get('fdcId')}",
        "name": food.get("description") or query,
        "source": "usda_fdc",
        "fdc_id": food.get("fdcId"),
        "per_100g": {
            "kcal": kcal,
            "protein_g": protein,
            "carb_g": carb,
            "fat_g": fat,
            "fiber_g": fiber,
            "sugars_g": sugars,
        },
        "gi": None,
        "category": "usda",
        "query": query,
    }


DEFAULT_FOOD_QUERIES = [
    "chicken breast", "white rice", "brown rice", "oatmeal", "banana",
    "greek yogurt", "olive oil", "whole wheat bread", "black beans",
    "salmon", "broccoli", "ice cream", "cola", "almonds", "pasta",
    "egg", "avocado", "sweet potato", "protein bar", "pizza",
]


def build_food_pack(
    queries: Optional[List[str]] = None,
    use_openfoodfacts: bool = True,
    use_usda: bool = True,
) -> Dict[str, Any]:
    ensure_dirs()
    queries = queries or DEFAULT_FOOD_QUERIES
    foods: List[dict] = []
    # Always include seed
    for f in load_seed_foods():
        f = dict(f)
        f["source"] = f.get("source") or "seed"
        foods.append(f)

    errors = []
    cache_dir = project_path("data", "cache", "food")
    cache_dir.mkdir(parents=True, exist_ok=True)

    if use_openfoodfacts:
        for q in queries:
            cache = cache_dir / f"off_{abs(hash(q))}.json"
            try:
                if cache.is_file():
                    data = json.loads(cache.read_text(encoding="utf-8"))
                else:
                    data = fetch_openfoodfacts_search(q)
                    cache.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    time.sleep(0.2)
                for p in (data.get("products") or [])[:8]:
                    row = _off_to_food(p, q)
                    if row:
                        foods.append(row)
            except Exception as e:
                errors.append({"source": "openfoodfacts", "query": q, "error": str(e)})

    if use_usda and (os.environ.get("FDC_API_KEY") or os.environ.get("USDA_FDC_API_KEY")):
        for q in queries[:12]:
            cache = cache_dir / f"fdc_{abs(hash(q))}.json"
            try:
                if cache.is_file():
                    data = json.loads(cache.read_text(encoding="utf-8"))
                else:
                    data = fetch_usda_fdc_search(q)
                    cache.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    time.sleep(0.2)
                for f in (data.get("foods") or [])[:5]:
                    row = _usda_to_food(f, q)
                    if row:
                        foods.append(row)
            except Exception as e:
                errors.append({"source": "usda_fdc", "query": q, "error": str(e)})

    # Dedupe by id
    seen = set()
    unique = []
    for f in foods:
        if f["id"] in seen:
            continue
        seen.add(f["id"])
        unique.append(f)

    pack = {
        "food_count": len(unique),
        "seed_count": len(load_seed_foods()),
        "errors": errors,
        "foods": unique,
    }
    project_path("data", "derived", "food_pack.json").write_text(
        json.dumps(pack, indent=2), encoding="utf-8"
    )
    return pack


# ---------------------------------------------------------------------------
# Insulin index
# ---------------------------------------------------------------------------

@dataclass
class MealItem:
    food_id: str
    grams: float


@dataclass
class MealInsulinResult:
    total_kcal: float
    protein_g: float
    carb_g: float
    fat_g: float
    fiber_g: float
    sugars_g: float
    available_carb_g: float
    weighted_gi: float
    glycemic_load: float
    insulin_index: float  # 0–1 systemic pressure for sim
    insulinogenic_score: float
    items: List[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _food_index(foods: Optional[List[dict]] = None) -> Dict[str, dict]:
    if foods is None:
        path = project_path("data", "derived", "food_pack.json")
        if path.is_file():
            foods = json.loads(path.read_text(encoding="utf-8"))["foods"]
        else:
            foods = load_seed_foods()
    return {f["id"]: f for f in foods}


def estimate_gi(food: dict) -> float:
    if food.get("gi") is not None:
        return float(food["gi"])
    # Heuristic from macros when GI unknown
    p = food["per_100g"]
    carb = float(p.get("carb_g") or 0)
    fiber = float(p.get("fiber_g") or 0)
    sugars = float(p.get("sugars_g") or 0)
    protein = float(p.get("protein_g") or 0)
    fat = float(p.get("fat_g") or 0)
    if carb < 1:
        return 0.0
    sugar_frac = sugars / max(carb, 1e-6)
    fiber_frac = fiber / max(carb, 1e-6)
    gi = 55 + 25 * sugar_frac - 30 * fiber_frac - 0.3 * protein - 0.2 * fat
    return max(0.0, min(100.0, gi))


def meal_insulin_index(
    items: List[Tuple[str, float]],
    foods: Optional[List[dict]] = None,
    meal_frequency_day: int = 3,
) -> MealInsulinResult:
    """
    items: list of (food_id, grams)
    Insulin index 0–1 for FSOT sim from glycemic load + macro mix.
    """
    idx = _food_index(foods)
    protein = carb = fat = fiber = sugars = kcal = 0.0
    gl_num = 0.0
    carb_for_gi = 0.0
    detail = []

    for food_id, grams in items:
        if food_id not in idx:
            raise KeyError(f"Unknown food_id: {food_id}")
        f = idx[food_id]
        scale = grams / 100.0
        p = f["per_100g"]
        pg = float(p["protein_g"]) * scale
        cg = float(p["carb_g"]) * scale
        fg = float(p["fat_g"]) * scale
        fib = float(p.get("fiber_g") or 0) * scale
        sug = float(p.get("sugars_g") or 0) * scale
        kc = float(p["kcal"]) * scale
        gi = estimate_gi(f)
        avail = max(0.0, cg - fib)
        gl = gi * avail / 100.0
        protein += pg
        carb += cg
        fat += fg
        fiber += fib
        sugars += sug
        kcal += kc
        gl_num += gl
        carb_for_gi += avail
        detail.append({
            "food_id": food_id,
            "name": f.get("name"),
            "grams": grams,
            "kcal": kc,
            "gi": gi,
            "glycemic_load": gl,
        })

    weighted_gi = (gl_num / carb_for_gi * 100.0) if carb_for_gi > 0 else 0.0
    # Holt-style crude insulinogenic: protein also insulinotropic
    # IIS ~ carbs + 0.5*protein scaled
    iis = carb + 0.5 * protein + 0.1 * fat
    # Map GL + IIS to 0–1
    # GL 0–60 typical meal; normalize
    gl_norm = min(1.0, gl_num / 40.0)
    carb_frac = (carb * 4 / kcal) if kcal > 0 else 0.0
    insulin = 0.15 + 0.55 * gl_norm + 0.20 * carb_frac + 0.05 * min(meal_frequency_day, 6) / 6
    # Fiber dampens
    if carb > 0:
        insulin *= 1.0 - 0.15 * min(1.0, fiber / max(carb, 1e-6))
    insulin = max(0.05, min(0.98, insulin))

    return MealInsulinResult(
        total_kcal=kcal,
        protein_g=protein,
        carb_g=carb,
        fat_g=fat,
        fiber_g=fiber,
        sugars_g=sugars,
        available_carb_g=carb_for_gi,
        weighted_gi=weighted_gi,
        glycemic_load=gl_num,
        insulin_index=insulin,
        insulinogenic_score=iis,
        items=detail,
    )


def example_meals() -> Dict[str, MealInsulinResult]:
    """Reference meal templates for reports."""
    meals = {
        "high_gi_takeout": [
            ("white_rice_cooked", 250),
            ("cola", 330),
            ("burger_beef", 200),
        ],
        "balanced_home": [
            ("chicken_breast", 150),
            ("brown_rice_cooked", 150),
            ("broccoli", 150),
            ("olive_oil", 10),
        ],
        "low_insulin_cut": [
            ("salmon", 180),
            ("spinach", 100),
            ("avocado", 80),
            ("egg_whole", 100),
        ],
        "dessert_spike": [
            ("ice_cream_vanilla", 150),
            ("table_sugar", 20),
            ("cola", 330),
        ],
        "athlete_high_carb": [
            ("oatmeal_cooked", 300),
            ("banana", 120),
            ("whey_isolate", 30),
            ("honey", 20),
        ],
    }
    out = {}
    for name, items in meals.items():
        out[name] = meal_insulin_index(items)
    return out
