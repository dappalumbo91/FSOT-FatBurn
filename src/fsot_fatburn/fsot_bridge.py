"""
Bridge into the canonical FSOT 2.1 compute engine on the physical archive.

All numeric FSOT claims in this app flow through vendor/fsot_compute.py
(zero free parameters; seeds π, e, φ, γ, G).
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import load_config


def _load_fsot_compute():
    cfg = load_config()
    path = Path(cfg["fsot"]["compute_module"])
    if not path.is_file():
        raise FileNotFoundError(
            f"FSOT compute engine not found at {path}. "
            "Set config.yaml fsot.compute_module to the archive vendor/fsot_compute.py"
        )
    spec = importlib.util.spec_from_file_location("fsot_compute_authority", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load fsot_compute from {path}")
    mod = importlib.util.module_from_spec(spec)
    # Avoid polluting if already loaded under same name
    sys.modules["fsot_compute_authority"] = mod
    spec.loader.exec_module(mod)
    return mod


_MOD = None


def get_engine():
    global _MOD
    if _MOD is None:
        _MOD = _load_fsot_compute()
    return _MOD


@dataclass
class ScalarSnapshot:
    """FSOT scalar readout for a physiological regime."""

    domain: str
    D_eff: int
    delta_psi: float
    recent_hits: int
    observed: bool
    raw_S: float
    scaled_S: float
    poof: float
    p_new: float
    c_eff: float
    consciousness_factor: float
    interpretation: str  # emergence | dispersal | boundary


def compute_domain_scalar(domain_name: str) -> float:
    eng = get_engine()
    if domain_name not in eng.DOMAINS:
        raise KeyError(f"Unknown FSOT domain: {domain_name}. Known: {list(eng.DOMAINS)}")
    return float(eng.domain_scalar(domain_name))


def compute_custom_scalar(
    *,
    N: float = 1.0,
    P: float = 1.0,
    D_eff: float = 12.0,
    delta_psi: float = 0.08,
    delta_theta: float = 1.0,
    recent_hits: float = 0.0,
    observed: bool = False,
    scale: float = 1.0,
    amplitude: float = 1.0,
    trend_bias: float = 0.0,
    rho: float = 1.0,
) -> float:
    eng = get_engine()
    mpf = eng.mpf
    si = eng.ScalarInput(
        N=mpf(N),
        P=mpf(P),
        D_eff=mpf(D_eff),
        delta_psi=mpf(delta_psi),
        delta_theta=mpf(delta_theta),
        recent_hits=mpf(recent_hits),
        observed=observed,
        scale=mpf(scale),
        amplitude=mpf(amplitude),
        trend_bias=mpf(trend_bias),
        rho=mpf(rho),
    )
    return float(eng.compute_scalar(si))


def seed_constants() -> dict[str, float]:
    eng = get_engine()
    return {
        "pi": float(eng.PI),
        "e": float(eng.E),
        "phi": float(eng.PHI),
        "gamma": float(eng.GAMMA),
        "G_catalan": float(eng.G_CAT),
        "poof": float(eng.POOF),
        "p_new": float(eng.P_NEW),
        "c_eff": float(eng.C_EFF),
        "consciousness_factor": float(eng.C_FACTOR),
        "K": float(eng.K),
        "alpha": float(eng.ALPHA),
        "psi_con": float(eng.PSI_CON),
        "eta_eff": float(eng.ETA_EFF),
    }


def regime_snapshot(fold_key: str) -> ScalarSnapshot:
    """Map config domain fold → scalar snapshot with emergence/dispersal label."""
    cfg = load_config()
    fold = cfg["fsot"]["domains"][fold_key]
    S = compute_custom_scalar(
        D_eff=fold["D_eff"],
        delta_psi=fold["delta_psi"],
        recent_hits=fold["recent_hits"],
        observed=fold["observed"],
    )
    # Sign convention (FSOT): positive raw_S → emergence; negative → dispersal.
    # For fat: storage ~ emergence of lipid structure; burn ~ dispersal.
    if S > 0.05:
        interp = "emergence"
    elif S < -0.05:
        interp = "dispersal"
    else:
        interp = "boundary"
    c = seed_constants()
    return ScalarSnapshot(
        domain=fold["name"],
        D_eff=fold["D_eff"],
        delta_psi=float(fold["delta_psi"]),
        recent_hits=int(fold["recent_hits"]),
        observed=bool(fold["observed"]),
        raw_S=S,
        scaled_S=S,
        poof=c["poof"],
        p_new=c["p_new"],
        c_eff=c["c_eff"],
        consciousness_factor=c["consciousness_factor"],
        interpretation=interp,
    )


def intervention_scalar_modulators(
    *,
    catecholamine_index: float = 0.0,  # 0–1 sympathetic drive
    insulin_index: float = 0.5,  # 0 fasting … 1 high fed
    deficit_kcal_day: float = 0.0,
    cold_or_brown_drive: float = 0.0,
    compound_lipolytic: float = 0.0,
    fluid_sodium_load: float = 0.5,
) -> dict[str, Any]:
    """
    Map physiological drivers onto FSOT scalar inputs.

    Design (seed-folded, not free least-squares):
    - Higher catecholamines / cold / lipolytic compounds → raise observed + P
      (active measurement/agency of the system) and push toward dispersal of lipid.
    - High insulin / storage signal → lower P relative to storage N, favor emergence.
    - Energy deficit modulates amplitude (thermodynamic environment term2).
    - Sodium/fluid load routes through Fluid_Dynamics-like delta_psi.
    """
    c = seed_constants()
    phi, e, pi = c["phi"], c["e"], c["pi"]

    # Clamp
    cat = max(0.0, min(1.0, catecholamine_index))
    ins = max(0.0, min(1.0, insulin_index))
    cold = max(0.0, min(1.0, cold_or_brown_drive))
    lip = max(0.0, min(1.0, compound_lipolytic))
    sod = max(0.0, min(1.0, fluid_sodium_load))

    # N ~ structural mass scale of adipose compartment (held unit; sim scales separately)
    N = 1.0
    # P ~ power throughput: exercise + catecholamine + thermogenesis
    P = 1.0 + cat * phi + cold * (e / pi) + lip * c["p_new"]
    # Insulin opposes lipolysis power
    P = max(0.2, P * (1.0 - 0.45 * ins))

    # Observed flag: active intervention / training / cold exposure
    observed = (cat + cold + lip) > 0.25

    # Phase offset: storage vs mobilization — insulin raises δψ toward storage fold
    delta_psi = 0.08 + 0.4 * ins - 0.25 * cat - 0.15 * lip + 0.1 * sod

    # Thermodynamic amplitude from caloric state (deficit → more negative bias on storage)
    # deficit_kcal_day positive means under-eating
    amplitude = 1.0 + (deficit_kcal_day / 7700.0) * phi  # fraction of ~1 kg fat energy
    trend_bias = -0.15 * (deficit_kcal_day / 500.0)  # mild dispersal bias under deficit

    # Hits: repeated stimulus (training frequency proxy)
    recent_hits = min(3, int(cat * 2 + cold + lip))

    S_bio = compute_custom_scalar(
        N=N,
        P=P,
        D_eff=12,
        delta_psi=delta_psi,
        recent_hits=recent_hits,
        observed=observed,
        amplitude=amplitude,
        trend_bias=trend_bias,
    )
    S_therm = compute_custom_scalar(
        N=N,
        P=P * (1.0 + cold),
        D_eff=15,
        delta_psi=0.9 - 0.2 * cat,
        recent_hits=recent_hits,
        observed=True,
        amplitude=amplitude,
        trend_bias=trend_bias,
    )
    S_fluid = compute_custom_scalar(
        N=N,
        P=1.0,
        D_eff=15,
        delta_psi=0.5 + 0.8 * sod,
        recent_hits=0,
        observed=False,
        amplitude=1.0 + 0.3 * sod,
        trend_bias=0.2 * sod,  # positive fluid "emergence" = retention
    )

    # Dispersal score for lipid: more negative S_bio under active lipolytic drive is favorable for burn
    # We also want high S_therm (expenditure). Combine as burn_index.
    burn_index = (-S_bio) * 0.55 + (S_therm) * 0.35 + lip * c["poof"] * 10 - ins * 0.2
    retention_index = S_fluid + sod * phi - cat * 0.1

    return {
        "inputs": {
            "N": N,
            "P": P,
            "delta_psi": delta_psi,
            "observed": observed,
            "amplitude": amplitude,
            "trend_bias": trend_bias,
            "recent_hits": recent_hits,
            "catecholamine_index": cat,
            "insulin_index": ins,
            "deficit_kcal_day": deficit_kcal_day,
            "cold_or_brown_drive": cold,
            "compound_lipolytic": lip,
            "fluid_sodium_load": sod,
        },
        "scalars": {
            "S_biology_adipose": S_bio,
            "S_thermogenesis": S_therm,
            "S_fluid_retention": S_fluid,
        },
        "indices": {
            "fat_burn_index": burn_index,
            "water_retention_index": retention_index,
        },
        "seeds": c,
    }


def smoke_test() -> dict[str, Any]:
    c = seed_constants()
    snaps = {k: regime_snapshot(k).__dict__ for k in load_config()["fsot"]["domains"]}
    demo = intervention_scalar_modulators(
        catecholamine_index=0.7,
        insulin_index=0.2,
        deficit_kcal_day=500,
        cold_or_brown_drive=0.3,
        compound_lipolytic=0.4,
        fluid_sodium_load=0.3,
    )
    return {"seeds": c, "regimes": snaps, "demo_intervention": demo}
