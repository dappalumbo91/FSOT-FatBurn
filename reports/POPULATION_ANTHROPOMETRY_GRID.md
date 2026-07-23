# Population Anthropometry Selection Grid

Select the closest archetype to your waist / hip / neck / height / weight, then critique the deltas.
These are **population bounds and clinical cut-points**, not one person's body.

- Archetypes: **43**
- Waist span: **56–180 cm**
- Hip span: **82–170 cm**
- Neck span: **29–52 cm**

| ID | Label | Sex | Ht | Wt | Waist | Hip | Neck | BMI | WHR | BF%≈ | Shape | Band |
|----|-------|-----|----|----|-------|-----|------|-----|-----|------|-------|------|
| `M_lean_ectomorph_short` | Male · short · very lean linear | M | 165 | 55 | 70 | 86 | 34 | 20.2 | 0.81 | 8.8 | linear | very_lean |
| `M_lean_mesomorph_avg` | Male · average height · lean athletic | M | 178 | 75 | 78 | 95 | 38 | 23.7 | 0.82 | 10.5 | athletic | lean |
| `M_lean_tall` | Male · tall · lean | M | 193 | 82 | 80 | 98 | 37 | 22.0 | 0.82 | 10.7 | linear | lean |
| `M_contest_lean_extreme` | Male · contest-lean extreme (low waist) | M | 175 | 72 | 68 | 92 | 39 | 23.5 | 0.74 | 3.0 | athletic_extreme | extreme_lean |
| `M_who_action1` | Male · WHO waist action level 1 (94 cm) | M | 178 | 88 | 94 | 102 | 39 | 27.8 | 0.92 | 22.4 | android_mild | borderline |
| `M_atp3_102` | Male · ATP-III waist 102 cm | M | 178 | 98 | 102 | 106 | 41 | 30.9 | 0.96 | 26.2 | android | elevated |
| `M_avg_nhanes_class` | Male · mid-population abdominal (≈110 cm waist class) | M | 176 | 105 | 110 | 112 | 42 | 33.9 | 0.98 | 30.6 | android | high |
| `M_high_120` | Male · high waist 120 cm | M | 175 | 118 | 120 | 118 | 44 | 38.5 | 1.02 | 35.0 | apple | high |
| `M_severe_140` | Male · severe abdominal 140 cm | M | 178 | 140 | 140 | 135 | 46 | 44.2 | 1.04 | 42.4 | apple | severe |
| `M_extreme_165` | Male · extreme waist tail ~165 cm | M | 180 | 180 | 165 | 155 | 50 | 55.6 | 1.06 | 49.6 | apple_extreme | extreme |
| `M_extreme_180_tail` | Male · ultra-extreme waist tail ~180 cm | M | 178 | 210 | 180 | 170 | 52 | 66.3 | 1.06 | 53.9 | apple_ultra | ultra_extreme |
| `M_pear_soft` | Male · softer lower-body bias (lower WHR) | M | 178 | 95 | 92 | 110 | 38 | 30.0 | 0.84 | 21.7 | gynoid_bias | moderate |
| `M_apple_hard` | Male · hard apple (waist ≥ hip) | M | 175 | 110 | 118 | 112 | 43 | 35.9 | 1.05 | 34.5 | apple | high |
| `M_short_stocky` | Male · short stocky endomorph | M | 165 | 100 | 108 | 108 | 42 | 36.7 | 1.00 | 31.5 | stocky | high |
| `M_tall_heavy` | Male · tall heavy | M | 193 | 130 | 112 | 115 | 43 | 34.9 | 0.97 | 28.4 | android | high |
| `M_skinny_fat` | Male · normal-BMI high waist (skinny-fat class) | M | 178 | 78 | 96 | 98 | 37 | 24.6 | 0.98 | 25.0 | central_normalweight | central_lean_mass_low |
| `M_thick_neck_power` | Male · power athlete thick neck lower waist | M | 180 | 100 | 88 | 104 | 46 | 30.9 | 0.85 | 11.9 | mesomorph_power | moderate_lean_mass_high |
| `M_elderly_central` | Male · older adult central adiposity | M | 173 | 92 | 108 | 106 | 40 | 30.7 | 1.02 | 31.2 | android_age | elevated |
| `F_lean_ectomorph` | Female · lean linear | F | 168 | 52 | 62 | 88 | 30 | 18.4 | 0.70 | 17.0 | linear | very_lean |
| `F_lean_athletic` | Female · athletic lean | F | 170 | 62 | 68 | 94 | 32 | 21.4 | 0.72 | 22.2 | athletic | lean |
| `F_contest_lean_extreme` | Female · contest-lean extreme | F | 165 | 55 | 58 | 86 | 31 | 20.2 | 0.67 | 13.5 | athletic_extreme | extreme_lean |
| `F_who_action1` | Female · WHO waist action level 1 (80 cm) | F | 163 | 70 | 80 | 100 | 33 | 26.4 | 0.80 | 32.7 | balanced | borderline |
| `F_atp3_88` | Female · ATP-III waist 88 cm | F | 163 | 78 | 88 | 106 | 34 | 29.4 | 0.83 | 38.7 | android_mild | elevated |
| `F_pear_classic` | Female · classic pear (low WHR, high hip) | F | 165 | 82 | 78 | 118 | 33 | 30.1 | 0.66 | 39.5 | pear | moderate_gynoid |
| `F_pear_extreme` | Female · extreme pear (hip >> waist) | F | 168 | 95 | 82 | 130 | 34 | 33.7 | 0.63 | 45.0 | pear_extreme | high_gynoid |
| `F_apple_classic` | Female · classic apple (high WHR) | F | 162 | 90 | 105 | 108 | 36 | 34.3 | 0.97 | 46.1 | apple | high_android |
| `F_high_105` | Female · high waist 105 cm | F | 160 | 100 | 105 | 115 | 37 | 39.1 | 0.91 | 49.0 | android | high |
| `F_severe_125` | Female · severe waist 125 cm | F | 163 | 125 | 125 | 130 | 39 | 47.0 | 0.96 | 60.0 | apple | severe |
| `F_extreme_150` | Female · extreme waist tail ~150 cm | F | 165 | 160 | 150 | 155 | 42 | 58.8 | 0.97 | 60.0 | apple_extreme | extreme |
| `F_short_stocky` | Female · short stocky | F | 155 | 85 | 98 | 112 | 35 | 35.4 | 0.88 | 47.2 | stocky | high |
| `F_tall_pear` | Female · tall pear | F | 178 | 85 | 76 | 112 | 33 | 26.8 | 0.68 | 32.7 | pear | moderate |
| `F_postmeno_central` | Female · post-menopausal central shift | F | 162 | 80 | 96 | 106 | 35 | 30.5 | 0.91 | 42.0 | android_age | elevated |
| `F_skinny_fat` | Female · normal-weight high waist class | F | 165 | 62 | 86 | 96 | 32 | 22.8 | 0.90 | 33.6 | central_normalweight | central_lean_mass_low |
| `F_hourglass_mid` | Female · hourglass mid (balanced WHR ~0.7) | F | 168 | 68 | 70 | 100 | 32 | 24.1 | 0.70 | 26.9 | hourglass | moderate_lean |
| `F_thick_neck_risk` | Female · elevated neck circumference class | F | 163 | 95 | 100 | 115 | 40 | 35.8 | 0.87 | 45.1 | android | high |
| `M_teen_early_adult_lean` | Male · young adult lean | M | 180 | 70 | 74 | 92 | 36 | 21.6 | 0.80 | 8.2 | linear | lean |
| `F_teen_early_adult_lean` | Female · young adult lean | F | 165 | 55 | 66 | 92 | 31 | 20.2 | 0.72 | 21.8 | linear | lean |
| `M_waist_height_risk` | Male · waist-to-height ≈ 0.6 risk class | M | 175 | 100 | 105 | 108 | 41 | 32.6 | 0.97 | 28.5 | android | elevated |
| `F_waist_height_risk` | Female · waist-to-height ≈ 0.6 risk class | F | 160 | 85 | 96 | 110 | 35 | 33.2 | 0.87 | 44.2 | android_mild | elevated |
| `M_hip_dominant_rare` | Male · hip-dominant rare pattern | M | 176 | 100 | 95 | 120 | 39 | 32.3 | 0.79 | 23.4 | gynoid_rare | moderate_high |
| `F_waist_equals_hip` | Female · cylindrical (waist ≈ hip) | F | 164 | 92 | 110 | 111 | 36 | 34.2 | 0.99 | 48.7 | cylinder_apple | high |
| `M_micro_waist_tall_thin` | Male · tall thin micro-waist bound | M | 193 | 68 | 66 | 88 | 33 | 18.3 | 0.75 | 3.0 | extreme_ectomorph | extreme_lean |
| `F_micro_waist_petite` | Female · petite micro-waist bound | F | 155 | 45 | 56 | 82 | 29 | 18.7 | 0.68 | 13.6 | extreme_ectomorph | extreme_lean |

## How to select

```powershell
python scripts/select_archetype.py --sex male --height 178 --weight 95 --waist 102 --hip 108 --neck 40
python scripts/run_sim.py --subject-json data/derived/population_subjects/M_atp3_102.json
```

Then refine with your exact measures via `calibrate_subject.py` if you want a personal overlay.
