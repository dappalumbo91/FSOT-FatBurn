"""
Adipocyte (fat cell) dynamical model.

Pathways modeled (coarse-grained, FSOT-coupled):
  TAG storage  ←  insulin, glucose/FFA supply, low catecholamines
  Lipolysis    →  ATGL/HSL cascade driven by cAMP (catecholamines, forskolin, etc.)
  Re-esterification  (not all FFA leave the cell)
  Browning/UCP1 thermogenesis (BAT-like fraction)

Trinary FSOT analogy at cell level:
  +1 Spin Up   ~ lipogenic / storage dominance (P_new resonance)
  0 Superposed ~ balanced turnover
  -1 Spin Down ~ lipolytic dispersal (Poof-linked mobilization)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from ..fsot_bridge import seed_constants, intervention_scalar_modulators
from .depots import FatDepot


@dataclass
class AdipocyteState:
    depot_id: str
    lipid_kg: float
    # 0–1 phenotype mix within depot
    white_fraction: float = 0.97
    brown_beige_fraction: float = 0.03
    # Internal signal proxies
    camp_tone: float = 0.2
    insulin_tone: float = 0.5
    reesterification: float = 0.4
    trinary: int = 0  # -1, 0, +1
    last_lipolysis_g_h: float = 0.0
    last_storage_g_h: float = 0.0


@dataclass
class AdipocyteModel:
    """One depot's adipocyte population treated as a lumped compartment."""

    depot: FatDepot
    state: AdipocyteState
    constants: dict = field(default_factory=seed_constants)

    @classmethod
    def from_depot(cls, depot: FatDepot, lipid_kg: float) -> "AdipocyteModel":
        brown = 0.08 if depot.is_visceral else 0.02
        if depot.id.startswith("im_"):
            brown = 0.05
        return cls(
            depot=depot,
            state=AdipocyteState(
                depot_id=depot.id,
                lipid_kg=lipid_kg,
                white_fraction=1.0 - brown,
                brown_beige_fraction=brown,
            ),
        )

    def step(
        self,
        dt_h: float,
        *,
        catecholamine_index: float,
        insulin_index: float,
        compound_lipolytic: float,
        cold_drive: float,
        systemic_deficit_kcal_day: float,
        dietary_fat_storage_drive: float = 0.0,
    ) -> Dict[str, float]:
        """
        Advance depot lipid mass by dt_h hours.
        Returns fluxes in grams and FSOT indices for this step.
        """
        d = self.depot
        c = self.constants
        st = self.state

        # Effective lipolytic drive at this depot
        # β sensitivity promotes, α2 opposes (unless compounds blunt α2)
        alpha_block = max(0.0, d.alpha2_antilipolytic * (1.0 - 0.6 * compound_lipolytic))
        lipolytic_drive = (
            catecholamine_index * d.beta_adrenergic_sensitivity * d.blood_flow_relative
            - insulin_index * d.insulin_sensitivity_relative * 0.85
            - alpha_block * 0.25
            + compound_lipolytic * 0.5
            + cold_drive * st.brown_beige_fraction * 2.0
        )
        lipolytic_drive = max(0.0, lipolytic_drive)

        # Storage drive
        storage_drive = (
            insulin_index * d.insulin_sensitivity_relative
            + dietary_fat_storage_drive
            - catecholamine_index * 0.35
        )
        storage_drive = max(0.0, storage_drive)

        # Baseline turnover scales with depot mass (larger depot → more absolute flux)
        mass_g = max(st.lipid_kg * 1000.0, 1.0)
        # Fractional lipolysis capacity ~ few %/day under strong stimulus (order-of-magnitude)
        # Strong drive ~ 0.4–0.8%/day of depot; convert to hourly
        max_frac_per_day = 0.012 * (0.5 + lipolytic_drive)  # up to ~1.8%/day extreme
        lipolysis_g_h = mass_g * max_frac_per_day / 24.0 * lipolytic_drive

        # Re-esterification retains some FFA
        reest = st.reesterification * (0.5 + 0.5 * insulin_index)
        net_export_g_h = lipolysis_g_h * (1.0 - reest * 0.5)

        # Storage accretion (from systemic surplus routed to this depot by fraction & insulin)
        storage_g_h = mass_g * 0.004 / 24.0 * storage_drive

        # Brown thermogenesis burns local lipid without export
        brown_burn_g_h = (
            mass_g * 0.003 / 24.0 * cold_drive * st.brown_beige_fraction * (1.0 + c["phi"])
        )

        net_g_h = storage_g_h - net_export_g_h - brown_burn_g_h
        delta_g = net_g_h * dt_h
        st.lipid_kg = max(0.05 * d.fraction_of_total_fat, st.lipid_kg + delta_g / 1000.0)
        st.camp_tone = 0.7 * st.camp_tone + 0.3 * lipolytic_drive
        st.insulin_tone = 0.7 * st.insulin_tone + 0.3 * insulin_index
        st.last_lipolysis_g_h = net_export_g_h + brown_burn_g_h
        st.last_storage_g_h = storage_g_h

        # Trinary collapse from FSOT modulators at this depot
        fsot = intervention_scalar_modulators(
            catecholamine_index=catecholamine_index * d.beta_adrenergic_sensitivity,
            insulin_index=insulin_index * d.insulin_sensitivity_relative,
            deficit_kcal_day=systemic_deficit_kcal_day,
            cold_or_brown_drive=cold_drive * st.brown_beige_fraction,
            compound_lipolytic=compound_lipolytic * (1.0 + 0.3 * (d.alpha2_antilipolytic - 1.0)),
            fluid_sodium_load=0.5,
        )
        burn_idx = fsot["indices"]["fat_burn_index"]
        if burn_idx > 0.15:
            st.trinary = -1  # Spin Down / dispersal
        elif burn_idx < -0.05:
            st.trinary = 1  # Spin Up / storage
        else:
            st.trinary = 0

        return {
            "depot_id": d.id,
            "lipid_kg": st.lipid_kg,
            "lipolysis_g_h": st.last_lipolysis_g_h,
            "storage_g_h": storage_g_h,
            "brown_burn_g_h": brown_burn_g_h,
            "net_g_h": net_g_h,
            "trinary": st.trinary,
            "fat_burn_index": burn_idx,
            "S_biology": fsot["scalars"]["S_biology_adipose"],
            "S_thermogenesis": fsot["scalars"]["S_thermogenesis"],
        }
