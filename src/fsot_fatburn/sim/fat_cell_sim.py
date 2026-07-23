"""
Whole-body multi-depot fat cell simulator.

Couples:
  Subject energy balance
  Adipocyte per-depot dynamics
  Water retention (scale confound)
  FSOT scalar burn / retention indices
  Exercise + diet + compound stacks
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

from ..paths import load_config, project_path
from ..physiology.energy import SubjectProfile, EnergyBalance, insulin_index_from_diet
from ..physiology.adipocyte import AdipocyteModel
from ..physiology.water import WaterRetentionModel, WaterState
from ..interventions.exercise import get_exercise, combine_exercises
from ..interventions.diet import get_diet
from ..interventions.compounds import stack_scores, load_compound_catalog
from ..fsot_bridge import intervention_scalar_modulators


@dataclass
class SimConfig:
    days: int = 28
    dt_hours: float = 24.0  # daily steps by default
    subject: SubjectProfile = field(default_factory=SubjectProfile)
    diet_id: str = "moderate_deficit_balanced"
    exercise_ids: List[str] = field(default_factory=lambda: ["resistance_full_45", "zone2_bike_40", "steps_10k"])
    compound_ids: List[str] = field(default_factory=lambda: ["caffeine", "egcg"])
    # Optional explicit intake override (else TDEE + diet offset)
    intake_kcal_override: Optional[float] = None
    menstrual_phase: float = 0.0
    label: str = "default"
    # Optional food-level meal items: list of (food_id, grams) for insulin index
    meal_items: Optional[List[tuple]] = None


@dataclass
class SimResult:
    label: str
    config: dict
    daily: List[dict]
    summary: dict

    def to_dict(self) -> dict:
        return {"label": self.label, "config": self.config, "daily": self.daily, "summary": self.summary}


class FatBurnSimulator:
    def __init__(self, config: SimConfig):
        self.config = config
        self.cfg_yaml = load_config()
        self.subject = config.subject
        self.diet = get_diet(config.diet_id)
        self.ex_plan = combine_exercises(config.exercise_ids)
        self.compounds = stack_scores(config.compound_ids, load_compound_catalog())
        self.models: List[AdipocyteModel] = []
        self.water = WaterRetentionModel(
            WaterState(),
            glycogen_water_ratio=float(self.cfg_yaml["simulation"]["glycogen_water_ratio"]),
        )
        self._init_depots()

    def _init_depots(self) -> None:
        self.models = []
        for depot, kg in self.subject.allocate_depots():
            self.models.append(AdipocyteModel.from_depot(depot, kg))

    def _daily_energy(self) -> EnergyBalance:
        # Sum weekly exercise kcal → daily mean
        weekly_ex = 0.0
        for eid in self.config.exercise_ids:
            weekly_ex += get_exercise(eid).weekly_exercise_kcal(self.subject.weight_kg)
        daily_ex = weekly_ex / 7.0

        tdee_base = self.subject.tdee()
        if self.config.intake_kcal_override is not None:
            intake = self.config.intake_kcal_override
        else:
            intake = tdee_base + self.diet.calorie_offset
            # Appetite suppressants reduce intake
            intake *= 1.0 - 0.25 * self.compounds["appetite_suppress"]

        # NEAT from steps protocol
        neat_bonus = 0.0
        if any(get_exercise(e).category == "neet" for e in self.config.exercise_ids):
            neat_bonus = 150.0

        # Thermogenic compounds add EE
        therm_extra = 80.0 * self.compounds["thermogenic"]
        daily_ex += therm_extra

        return EnergyBalance.from_subject(
            self.subject,
            intake_kcal=intake,
            exercise_kcal=daily_ex,
            neat_bonus_kcal=neat_bonus,
        )

    def run(self) -> SimResult:
        daily_rows: List[dict] = []
        energy0 = self._daily_energy()
        kcal_per_kg = float(self.cfg_yaml["simulation"]["kcal_per_kg_fat"])

        fat0 = sum(m.state.lipid_kg for m in self.models)
        water0 = self.water.estimated_variable_water_kg
        scale0 = self.subject.weight_kg

        for day in range(1, self.config.days + 1):
            energy = self._daily_energy()
            macros = self.diet.macros_grams(energy.intake_kcal)
            fasting = self.diet.fasting_hours >= 14
            meal_ii = None
            if self.config.meal_items:
                try:
                    from ..data_ingest.food_client import meal_insulin_index
                    meal_ii = meal_insulin_index(list(self.config.meal_items)).insulin_index
                except Exception:
                    meal_ii = None
            insulin = insulin_index_from_diet(
                carbs_g=macros["carbs_g"],
                protein_g=macros["protein_g"],
                fat_g=macros["fat_g"],
                meal_frequency=self.diet.meal_frequency,
                is_fasting_window=fasting,
                somatotype_insulin_mult=self.subject.insulin_response_multiplier(),
                meal_insulin_index=meal_ii,
            )
            # Insulin sensitizers lower effective insulin index
            insulin *= 1.0 - 0.35 * self.compounds["insulin_sensitizer"]
            insulin = max(0.05, min(0.95, insulin))

            cat = min(1.0, self.ex_plan["daily_catecholamine_avg"] + 0.15 * self.compounds["lipolytic"])
            cold = self.ex_plan["cold_drive"] + 0.2 * self.compounds["thermogenic"]
            lip = min(
                1.0,
                self.compounds["lipolytic"] + 0.5 * self.compounds["alpha2_antagonist"],
            )
            deficit = energy.deficit_kcal

            # Dietary storage drive from surplus × somatotype fat_storage_drive
            storage_drive = 0.0
            if energy.balance_kcal > 0:
                storage_drive = min(
                    1.0,
                    (energy.balance_kcal / 500.0) * self.subject.fat_storage_drive(),
                )
            else:
                # Endomorphs still re-esterify more under deficit residual
                storage_drive = 0.08 * max(0.0, self.subject.fat_storage_drive() - 1.0)

            # --- Thermodynamic constraint ---
            # Net whole-body TAG change is fixed by energy balance (≈7700 kcal/kg).
            # Depot model supplies *relative* mobilization weights (β/α2, blood flow,
            # compounds, insulin), NOT a second independent mass sink.
            systemic_fat_delta_kg = energy.balance_kcal / kcal_per_kg  # neg = fat loss

            depot_rows = []
            weights = []
            for m in self.models:
                bf_bonus = 0.0
                for eid in self.config.exercise_ids:
                    bf_bonus += get_exercise(eid).depot_bloodflow_bonus.get(m.depot.id, 0.0)
                cat_d = min(1.0, cat + bf_bonus)

                # Probe dynamics for FSOT/trinary + relative lipolytic capacity
                flux = m.step(
                    self.config.dt_hours,
                    catecholamine_index=cat_d,
                    insulin_index=insulin,
                    compound_lipolytic=lip,
                    cold_drive=min(1.0, cold),
                    systemic_deficit_kcal_day=deficit,
                    dietary_fat_storage_drive=storage_drive * m.depot.fraction_of_total_fat,
                )
                # Undo mass change from probe step — energy balance owns net Δm
                # Restore lipid from before step by inverting net_g_h * dt
                undo_kg = (flux["net_g_h"] * self.config.dt_hours) / 1000.0
                m.state.lipid_kg = max(0.02, m.state.lipid_kg - undo_kg)

                # Weight: lipolytic capacity × mass (stubborn depots resist when deficit)
                d = m.depot
                if systemic_fat_delta_kg < 0:
                    # Losing fat: prefer high-β, low-α2, high blood flow, compound help
                    alpha_pen = d.alpha2_antilipolytic * (1.0 - 0.55 * self.compounds["alpha2_antagonist"])
                    w = (
                        m.state.lipid_kg
                        * d.beta_adrenergic_sensitivity
                        * d.blood_flow_relative
                        * (1.0 + bf_bonus)
                        * (1.0 + 0.5 * lip)
                        / max(0.35, alpha_pen)
                        * (1.0 + 0.3 * (1.0 - insulin * d.insulin_sensitivity_relative))
                    )
                else:
                    # Gaining fat: prefer insulin-sensitive storage depots
                    w = (
                        m.state.lipid_kg
                        * d.insulin_sensitivity_relative
                        * (1.2 if not d.is_visceral else 0.9)
                    )
                weights.append(max(1e-9, w))
                flux["mobilization_weight"] = w
                depot_rows.append(flux)

            wsum = sum(weights)
            for m, w, flux in zip(self.models, weights, depot_rows):
                share = w / wsum
                delta = systemic_fat_delta_kg * share
                m.state.lipid_kg = max(0.02, m.state.lipid_kg + delta)
                flux["lipid_kg"] = m.state.lipid_kg
                flux["energy_share_delta_kg"] = delta

            # Water day step
            training = cat > 0.3
            cortisol = 0.3 + 0.4 * (1.0 if deficit > 800 else 0.0) + 0.2 * cat
            w = self.water.step_day(
                sodium_relative=self.diet.sodium_relative * (1.0 - 0.5 * self.compounds["diuretic"]),
                carb_g=macros["carbs_g"],
                training_depleting=training and deficit > 200,
                cortisol_proxy=min(1.0, cortisol),
                deficit_kcal=deficit,
                menstrual_phase=self.config.menstrual_phase,
            )

            fat_now = sum(m.state.lipid_kg for m in self.models)
            lean = self.subject.lean_mass_kg
            # Crude lean protection
            if deficit > 0 and self.ex_plan["muscle_retention"] < 0.5:
                lean_loss = (deficit / kcal_per_kg) * 0.15 * (1.0 - self.ex_plan["muscle_retention"])
                lean = max(lean - lean_loss / self.config.days, lean * 0.99)

            water_now = self.water.estimated_variable_water_kg
            # Scale weight = lean + fat + variable water offset from baseline water
            scale = lean + fat_now + (water_now - water0) * 0.5 + (scale0 - fat0 - self.subject.lean_mass_kg)

            fsot = intervention_scalar_modulators(
                catecholamine_index=cat,
                insulin_index=insulin,
                deficit_kcal_day=deficit,
                cold_or_brown_drive=min(1.0, cold),
                compound_lipolytic=lip,
                fluid_sodium_load=self.diet.sodium_relative,
            )

            daily_rows.append({
                "day": day,
                "intake_kcal": energy.intake_kcal,
                "expenditure_kcal": energy.expenditure,
                "balance_kcal": energy.balance_kcal,
                "deficit_kcal": deficit,
                "fat_mass_kg": fat_now,
                "fat_delta_from_start_kg": fat_now - fat0,
                "variable_water_kg": water_now,
                "scale_weight_kg": scale,
                "insulin_index": insulin,
                "catecholamine_index": cat,
                "compound_lipolytic": lip,
                "fsot": fsot["indices"],
                "fsot_scalars": fsot["scalars"],
                "depots": {r["depot_id"]: r for r in depot_rows},
                "macros": macros,
                "water": w,
            })

            # Update subject weight for next-day EE (optional mild adaptation)
            self.subject.weight_kg = scale
            self.subject.body_fat_pct = 100.0 * fat_now / max(scale, 1.0)

        fat_f = sum(m.state.lipid_kg for m in self.models)
        last = daily_rows[-1]
        summary = {
            "days": self.config.days,
            "fat_start_kg": fat0,
            "fat_end_kg": fat_f,
            "fat_lost_kg": fat0 - fat_f,
            "scale_start_kg": scale0,
            "scale_end_kg": last["scale_weight_kg"],
            "scale_delta_kg": scale0 - last["scale_weight_kg"],
            "water_confound_end_kg": last["variable_water_kg"],
            "mean_daily_deficit_kcal": sum(r["deficit_kcal"] for r in daily_rows) / len(daily_rows),
            "mean_fat_burn_index": sum(r["fsot"]["fat_burn_index"] for r in daily_rows) / len(daily_rows),
            "mean_water_retention_index": sum(r["fsot"]["water_retention_index"] for r in daily_rows) / len(daily_rows),
            "depot_end_kg": {m.depot.id: m.state.lipid_kg for m in self.models},
            "depot_delta_kg": {
                m.depot.id: m.state.lipid_kg - fat0 * m.depot.fraction_of_total_fat
                for m in self.models
            },
            "protocol": {
                "diet": self.diet.id,
                "exercise": self.config.exercise_ids,
                "compounds": self.config.compound_ids,
            },
            "somatotype": self.subject.somatotype,
            "somatotype_meta": self.subject.somatotype_profile().to_dict(),
            "bmr_kcal": energy0.bmr_kcal,
        }
        return SimResult(
            label=self.config.label,
            config={
                "subject": self.config.subject.to_dict(),
                "diet_id": self.config.diet_id,
                "exercise_ids": self.config.exercise_ids,
                "compound_ids": self.config.compound_ids,
                "days": self.config.days,
            },
            daily=daily_rows,
            summary=summary,
        )


def save_result(result: SimResult, name: str) -> str:
    path = project_path("reports", f"{name}.json")
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return str(path)
