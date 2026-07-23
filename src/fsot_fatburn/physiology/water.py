"""
Extracellular / glycogen-linked water retention model.

Short-term scale weight often moves more from water than from adipose TAG.
Targets: sodium load, glycogen stores, cortisol proxy, inflammation, menstrual.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class WaterState:
    extracellular_l: float = 15.0  # rough adult scaffold
    glycogen_g: float = 400.0  # muscle+liver order of magnitude
    sodium_relative: float = 0.5  # 0 low … 1 high intake
    cortisol_proxy: float = 0.4
    inflammation_proxy: float = 0.3
    menstrual_phase: float = 0.0  # 0 none/male … 1 late luteal peak retention


@dataclass
class WaterRetentionModel:
    state: WaterState
    glycogen_water_ratio: float = 3.0  # g water / g glycogen

    @property
    def glycogen_bound_water_kg(self) -> float:
        return (self.state.glycogen_g * self.glycogen_water_ratio) / 1000.0

    @property
    def estimated_variable_water_kg(self) -> float:
        """Portion of scale weight attributable to variable water (not fixed ECF)."""
        s = self.state
        sodium_extra = (s.sodium_relative - 0.5) * 1.2  # ± ~0.6 kg
        stress_extra = s.cortisol_proxy * 0.4
        inflam_extra = s.inflammation_proxy * 0.5
        menses_extra = s.menstrual_phase * 1.5
        return max(
            0.0,
            self.glycogen_bound_water_kg
            + sodium_extra
            + stress_extra
            + inflam_extra
            + menses_extra,
        )

    def step_day(
        self,
        *,
        sodium_relative: float,
        carb_g: float,
        training_depleting: bool,
        cortisol_proxy: float,
        deficit_kcal: float,
        menstrual_phase: float = 0.0,
    ) -> dict:
        st = self.state
        st.sodium_relative = 0.6 * st.sodium_relative + 0.4 * sodium_relative
        st.cortisol_proxy = 0.6 * st.cortisol_proxy + 0.4 * cortisol_proxy
        st.menstrual_phase = menstrual_phase

        # Glycogen dynamics: carbs refill; hard training + deficit deplete
        refill = carb_g * 0.35
        deplete = (80.0 if training_depleting else 20.0) + max(0.0, deficit_kcal) * 0.02
        st.glycogen_g = max(80.0, min(600.0, st.glycogen_g + refill - deplete))

        # Mild inflammation rise if extreme deficit
        if deficit_kcal > 1000:
            st.inflammation_proxy = min(1.0, st.inflammation_proxy + 0.05)
        else:
            st.inflammation_proxy = max(0.1, st.inflammation_proxy * 0.95)

        return {
            "glycogen_g": st.glycogen_g,
            "variable_water_kg": self.estimated_variable_water_kg,
            "sodium_relative": st.sodium_relative,
            "cortisol_proxy": st.cortisol_proxy,
            "scale_confound_kg": self.estimated_variable_water_kg,
        }

    def to_dict(self) -> dict:
        return {
            "state": asdict(self.state),
            "variable_water_kg": self.estimated_variable_water_kg,
            "glycogen_bound_water_kg": self.glycogen_bound_water_kg,
        }
