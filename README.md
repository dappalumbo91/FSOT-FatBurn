# FSOT Fat Burn

**Apply Fluid Spacetime Omni-Theory (FSOT) to human adipose physiology** — multi-depot fat-cell simulation, medical/SMILES compound profiles, exercise + diet + chemical protocol ranking.

Project root: `I:\fsot fat burn`  
FSOT authority: `I:\FSOT-Physical-Archive\02_FSOT-2.1-Lean-Full\vendor\fsot_compute.py`

---

## What this is

A research simulator that:

1. **Loads the canonical FSOT scalar engine** (seeds π, e, φ, γ, G — zero free parameters).
2. **Models fat depots** (visceral, belly, chest, flanks, gluteofemoral, arms, face/neck, intramuscular) with region-specific β/α2 adrenergic and blood-flow priors.
3. **Steps adipocyte TAG turnover** (lipolysis, re-esterification, brown burn) coupled to insulin, catecholamines, compounds, and energy balance.
4. **Tracks water retention** (glycogen-bound water, sodium, cortisol, menstrual) so scale weight is not confused with fat loss.
5. **Ingests chemistry/medical data** from the FSOT archive (PubChem cache, ChEMBL, SMILES lab, clinical panels) and enriches seed agents live via PubChem PUG REST + ChEMBL API.
6. **Ranks home-feasible protocols** (diet × exercise × stack) by true fat loss + FSOT burn index − water confound.

---

## Quick start

```powershell
cd "I:\fsot fat burn"
pip install -r requirements.txt

# Full bootstrap: archive + PubChem/ChEMBL + OpenFDA + ClinicalTrials + foods + trial-tune + Lean panel export
python scripts/bootstrap_data.py

# Or refresh medical/food packs only
python scripts/fetch_medical_packs.py
python scripts/export_adipose_panel.py

# Single simulation (somatotype-aware)
python scripts/run_sim.py --days 28 --weight 95 --bf 28 --sex male --somatotype endomorph

# Rank protocols
python scripts/rank_protocols.py --weight 95 --bf 28 --somatotype meso_endo

# Compare ectomorph / mesomorph / endomorph metabolism under same protocol
python scripts/compare_somatotypes.py
```

Optional USDA live foods: set `$env:FDC_API_KEY = "..."`.

Reports land in `reports/`. Derived data in `data/derived/`. Lean panel lands in  
`I:\FSOT-Physical-Archive\02_FSOT-2.1-Lean-Full\data\adipose_lipolysis_panel_benchmark.json`.

---

## Architecture

```
config.yaml                 # archive paths, domain folds, API bases
src/fsot_fatburn/
  fsot_bridge.py            # load archive fsot_compute → scalars + modulators
  physiology/
    depots.py               # anatomical fat map
    adipocyte.py            # per-depot TAG dynamics + trinary state
    energy.py               # BMR/TDEE/insulin index
    water.py                # retention / scale confound
  interventions/
    exercise.py             # LISS, zone2, HIIT, sprint, resistance, NEAT, cold
    diet.py                 # deficit, keto, IF, high protein, low sodium, …
    compounds.py            # caffeine, yohimbine, GLP-1, diuretics, …
  data_ingest/
    archive_bridge.py       # copy PubChem/ChEMBL/SMILES from physical archive
    pubchem_client.py       # PUG REST SMILES + properties
    chembl_client.py        # medical/pharmacology profiles
  sim/
    fat_cell_sim.py         # whole-body runner
    optimizer.py            # protocol grid ranking
scripts/
  bootstrap_data.py
  run_sim.py
  rank_protocols.py
```

### FSOT coupling (application layer)

| Physiology | FSOT fold / term |
|------------|------------------|
| White adipocyte storage | Biology `D_eff=12`, emergence / Spin Up |
| Lipolysis enzyme cascade | Biochemistry `D_eff=13` |
| Exercise thermogenesis | Thermodynamics `D_eff=15` |
| Water / sodium ECF | Fluid_Dynamics-like δψ + retention index |
| Active training / cold / agents | `observed=true`, ↑P, `quirk_mod` path |
| Caloric deficit | term2 amplitude / trend_bias |

`fat_burn_index` combines dispersal-favoring biology scalar, thermogenesis scalar, and lipolytic compound drive. **Water retention is scored separately** and penalized in protocol ranking so diuretics cannot “win” as fat loss.

---

## Depots modeled

| ID | Region | Notes |
|----|--------|-------|
| `visceral_omental` | Visceral | High β, metabolic risk, mobile |
| `subq_abdominal` | Belly | Primary trunk target |
| `subq_chest` | Chest | Upper-body pattern |
| `subq_back_flanks` | Love handles | Moderately stubborn |
| `subq_gluteofemoral` | Hips/thighs | High α2 — stubborn |
| `subq_arms` | Arms | Training-responsive |
| `subq_face_neck` | Face/neck | Water-dominated short term |
| `im_ectopic` | Intramuscular | Exercise-sensitive |

Sex priors redistribute mass (male → more visceral/trunk; female → more gluteofemoral).

---

## Data sources

| Source | Role |
|--------|------|
| FSOT `pubchem_cache.json` (500 compounds) | Local chemistry seed |
| FSOT ChEMBL pharmacology cache | Medical molecule profiles |
| FSOT SMILES Lab dataset | Seed-mapped chemical constants |
| PubChem PUG REST | Live SMILES, MW, XLogP, TPSA |
| ChEMBL REST | Live max phase, oral flags, structures |
| ClinicalTrials medical panel (archive) | Trial-domain benchmarks |
| Sports biomechanics observables | Exercise domain anchors |

---

## Epistemic tiers (FSOT discipline)

| Layer | Content |
|-------|---------|
| **Proved** | Seed constants + scalar engine from archive compute |
| **Measured anchors** | Mifflin–St Jeor BMR; ~7700 kcal/kg TAG; literature-ordered depot receptors |
| **Scaffold** | Absolute %/day lipolysis rates; compound effect sizes (refined as data grows) |
| **Interpretive** | Trinary Spin mapping onto storage vs burn |

This is an **FSOT application lab**, not a clinical product. Numbers are for protocol comparison under one engine — re-verify any claim you promote against the Lean/benchmark gates when you graduate a formula to “measured.”

---

## Somatotypes (body types)

| Type | BMR× | NEAT× | Insulin response× | Storage drive | Pattern |
|------|------|-------|-------------------|---------------|---------|
| Ectomorph | 1.08 | 1.15 | 0.85 | 0.75 | Hard gainer, high EE |
| Mesomorph | 1.03 | 1.05 | 0.95 | 0.95 | Athletic responder |
| Endomorph | 0.94 | 0.88 | 1.20 | 1.25 | Efficient storage, higher insulin |
| Hybrids | blended | | | | `ecto_meso`, `meso_endo`, `ecto_endo` |

Depot mass shares and α2 stubbornness also shift with type.

## Medical / food data packs

| Pack | Script / path |
|------|----------------|
| OpenFDA obesity labels | `data/derived/openfda_obesity_pack.json` |
| ClinicalTrials studies | `data/derived/clinicaltrials_obesity_pack.json` |
| Food + insulin meals | `data/derived/food_pack.json`, `meal_insulin_examples.json` |
| Trial-tuned compounds | `data/derived/compounds_trial_tuned.json` (seeds fixed) |
| Lean panel | `Adipose_Lipolysis_Live_Panel` → archive `FSOT/Formal/AdiposeLipolysisPanelPriors.lean` |

## OpenFDA catalog expansion

```powershell
python scripts/expand_catalog_openfda.py --retune
```

Pulls generics from the OpenFDA obesity pack, maps EPC classes → mechanism scores, adds curated agents (liraglutide, naltrexone, bupropion, topiramate, Qsymia/Contrave combos, …), resolves PubChem when possible. Output: `data/derived/compounds_catalog_full.json` (preferred by `load_compound_catalog()`).

## Population measurement grid (select → critique → personalize)

Not one body — a **population archetype library** from WHO/ATP cut-points, shape patterns (apple/pear/hourglass), short/tall frames, and clinical extreme tails.

| Span | Range |
|------|--------|
| Waist | **56–180 cm** |
| Hip | **82–170 cm** |
| Neck | **29–52 cm** |
| Archetypes | **43** (22 male / 21 female), all Navy-calibrated |

```powershell
# Build full catalog (+ optional 14-day probe sims)
python scripts/build_population_grid.py
python scripts/build_population_grid.py --sim --days 14

# Place measures on the grid → nearest templates + critique deltas
python scripts/select_archetype.py --sex male --height 178 --weight 95 `
  --waist 102 --hip 108 --neck 40 --top 5

# Sim a chosen population template
python scripts/run_sim.py --subject-json "data/derived/population_subjects/M_atp3_102.json"
python scripts/rank_protocols.py --subject-json "data/derived/population_subjects/M_atp3_102.json"
```

| File | Role |
|------|------|
| `data/seed/anthropometry_population_grid.json` | Seed extremes + literature anchors |
| `data/derived/population_anthropometry_catalog.json` | Calibrated catalog |
| `data/derived/population_selection_table.json` | Compact chooser |
| `data/derived/population_subjects/*.json` | `--subject-json` ready |
| `reports/POPULATION_ANTHROPOMETRY_GRID.md` | Readable table |

**Workflow:** select nearest archetype(s) → read you−template deltas → sim template → optional exact `calibrate_subject` overlay.

## Subject calibration (Navy + DEXA) — personal overlay

```powershell
python scripts/calibrate_subject.py --name me --sex male --height 178 --weight 95 `
  --waist 102 --hip 108 --neck 40 --run-sim

python scripts/run_sim.py --subject-json "data/derived/subject_me.json" --days 28
```

## Next build targets

- [x] OpenFDA + ClinicalTrials obesity / lipolysis packs  
- [x] Open Food Facts / USDA → meal insulin index  
- [x] Trial-tuned compound effect sizes (FSOT seeds fixed)  
- [x] Somatotype metabolic rates (ecto/meso/endo)  
- [x] Export `Adipose_Lipolysis_Live_Panel` to Lean archive  
- [x] Per-subject calibration from waist/hips/DEXA inputs  
- [x] OpenFDA generic names → automatic compound catalog expansion  
- [x] Population waist/hip/neck extreme grid + selector/critique  
- [ ] Continuous SR-ITE stream chew of PubMed abstracts on adipose biology  
- [ ] DEXA import from common CSV export formats  
- [ ] Photo / 3D scan circumference assist (optional) 

---

*FSOT Fat Burn — Damian Arthur Palumbo line of work; scalar authority remains the physical archive.*
