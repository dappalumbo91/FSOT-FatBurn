"""Exercise library with catecholamine, EPOC, and regional blood-flow effects."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class ExerciseProtocol:
    id: str
    name: str
    category: str  # resistance | hiit | liss | zone2 | sprint | neet | cold
    minutes: float
    sessions_per_week: float
    # Acute effects during / shortly after session (0–1)
    catecholamine_index: float
    # Extra kcal per session (rough MET-derived scaffold; scaled by body mass in sim)
    kcal_per_session_per_kg: float
    epoc_kcal_per_session: float
    # Preferential blood-flow bonus to depot ids
    depot_bloodflow_bonus: Dict[str, float]
    muscle_retention: float  # 0–1 protects lean mass under deficit
    notes: str

    def weekly_exercise_kcal(self, weight_kg: float) -> float:
        per = self.kcal_per_session_per_kg * weight_kg + self.epoc_kcal_per_session
        return per * self.sessions_per_week

    def daily_catecholamine_avg(self) -> float:
        # Spread sessions across week
        session_days = min(7.0, self.sessions_per_week)
        return self.catecholamine_index * (session_days / 7.0)

    def to_dict(self) -> dict:
        return asdict(self)


EXERCISE_LIBRARY: List[ExerciseProtocol] = [
    ExerciseProtocol(
        id="liss_walk_45",
        name="Brisk walk 45 min (LISS)",
        category="liss",
        minutes=45,
        sessions_per_week=5,
        catecholamine_index=0.25,
        kcal_per_session_per_kg=1.8,
        epoc_kcal_per_session=15,
        depot_bloodflow_bonus={"subq_abdominal": 0.05, "subq_gluteofemoral": 0.05},
        muscle_retention=0.2,
        notes="High adherence; NEAT-compatible; modest catecholamines.",
    ),
    ExerciseProtocol(
        id="zone2_bike_40",
        name="Zone-2 cardio 40 min",
        category="zone2",
        minutes=40,
        sessions_per_week=4,
        catecholamine_index=0.35,
        kcal_per_session_per_kg=2.4,
        epoc_kcal_per_session=30,
        depot_bloodflow_bonus={"visceral_omental": 0.08, "subq_abdominal": 0.06},
        muscle_retention=0.25,
        notes="Fat-oxidation zone; sustainable aerobic base.",
    ),
    ExerciseProtocol(
        id="hiit_20",
        name="HIIT intervals 20 min",
        category="hiit",
        minutes=20,
        sessions_per_week=3,
        catecholamine_index=0.75,
        kcal_per_session_per_kg=2.0,
        epoc_kcal_per_session=80,
        depot_bloodflow_bonus={"visceral_omental": 0.15, "subq_abdominal": 0.10},
        muscle_retention=0.45,
        notes="High catecholamines + EPOC; recovery-limited frequency.",
    ),
    ExerciseProtocol(
        id="sprint_10",
        name="Sprint / all-out 10 min total work",
        category="sprint",
        minutes=10,
        sessions_per_week=2,
        catecholamine_index=0.90,
        kcal_per_session_per_kg=1.2,
        epoc_kcal_per_session=100,
        depot_bloodflow_bonus={"visceral_omental": 0.18, "im_ectopic": 0.12},
        muscle_retention=0.5,
        notes="Max sympathetic spike; short duration; high recovery cost.",
    ),
    ExerciseProtocol(
        id="resistance_full_45",
        name="Full-body resistance 45 min",
        category="resistance",
        minutes=45,
        sessions_per_week=3,
        catecholamine_index=0.55,
        kcal_per_session_per_kg=1.6,
        epoc_kcal_per_session=50,
        depot_bloodflow_bonus={
            "subq_arms": 0.12,
            "subq_chest": 0.10,
            "subq_gluteofemoral": 0.10,
            "im_ectopic": 0.15,
        },
        muscle_retention=0.90,
        notes="Primary lean-mass defense; raises TDEE long-term via muscle.",
    ),
    ExerciseProtocol(
        id="resistance_hypertrophy_60",
        name="Hypertrophy split 60 min",
        category="resistance",
        minutes=60,
        sessions_per_week=4,
        catecholamine_index=0.50,
        kcal_per_session_per_kg=1.9,
        epoc_kcal_per_session=60,
        depot_bloodflow_bonus={
            "subq_arms": 0.15,
            "subq_chest": 0.12,
            "subq_gluteofemoral": 0.12,
        },
        muscle_retention=0.95,
        notes="Higher volume; best with protein ≥1.6 g/kg.",
    ),
    ExerciseProtocol(
        id="fasted_liss_yohimbine_window",
        name="Fasted LISS 40 min (α2-stubborn window)",
        category="liss",
        minutes=40,
        sessions_per_week=4,
        catecholamine_index=0.40,
        kcal_per_session_per_kg=1.7,
        epoc_kcal_per_session=20,
        depot_bloodflow_bonus={
            "subq_gluteofemoral": 0.20,
            "subq_back_flanks": 0.12,
            "subq_abdominal": 0.08,
        },
        muscle_retention=0.15,
        notes="Low insulin + mild catecholamines; pairs with α2 antagonists in compound stack.",
    ),
    ExerciseProtocol(
        id="steps_10k",
        name="Daily steps target 10k (NEAT)",
        category="neet",
        minutes=90,
        sessions_per_week=7,
        catecholamine_index=0.15,
        kcal_per_session_per_kg=2.2,
        epoc_kcal_per_session=5,
        depot_bloodflow_bonus={"subq_abdominal": 0.04, "subq_gluteofemoral": 0.04},
        muscle_retention=0.1,
        notes="Often largest real-world lever via non-exercise activity.",
    ),
    ExerciseProtocol(
        id="cold_shower_exposure",
        name="Cold exposure 10 min",
        category="cold",
        minutes=10,
        sessions_per_week=5,
        catecholamine_index=0.45,
        kcal_per_session_per_kg=0.4,
        epoc_kcal_per_session=25,
        depot_bloodflow_bonus={"visceral_omental": 0.05},
        muscle_retention=0.05,
        notes="Brown/beige thermogenesis drive; individual tolerance varies.",
    ),
]


def get_exercise(ex_id: str) -> ExerciseProtocol:
    for e in EXERCISE_LIBRARY:
        if e.id == ex_id:
            return e
    raise KeyError(ex_id)


def combine_exercises(ids: List[str]) -> dict:
    """Aggregate multi-modality weekly plan."""
    plans = [get_exercise(i) for i in ids]
    cat = sum(p.daily_catecholamine_avg() for p in plans)
    cat = min(1.0, cat)
    return {
        "ids": ids,
        "daily_catecholamine_avg": cat,
        "muscle_retention": max(p.muscle_retention for p in plans) if plans else 0.0,
        "cold_drive": min(1.0, sum(0.35 for p in plans if p.category == "cold")),
        "protocols": [p.to_dict() for p in plans],
    }
