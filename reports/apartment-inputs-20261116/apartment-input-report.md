# HomePulse apartment input experiment — 16 November 2026

Adding bedrooms, building age and main heating fuel improves this historical apartment model, but does not establish precise individual-home or future-month accuracy. The live app, production model and database were not changed.

## What was tested

The question is whether adding three answerable home details improves prediction of one apartment's annual electricity use. Target: RECS 2020 `KWH`, annual household electricity in kWh. No past electricity bill, electricity spending, target-derived end-use consumption or actual test KWH is an input.

| App question represented | Dataset field | Handling |
|---|---|---|
| State | `state_postal` | Category |
| Apartment building category | `TYPEHUQ` | 2–4 or 5+ apartments; category |
| Your own apartment size | `TOTSQFT_EN` | Numeric square feet, not total building area |
| Number of bedrooms | `BEDROOMS` | Numeric 0–6; 6 is top-coded |
| When the building/home was built | `YEARMADERANGE` | Nine year ranges, not an exact year |
| Main heating fuel | `FUELHEAT` | Electricity, natural gas, propane, oil, wood, other, or Not applicable |

Here heating type means **fuel**, not heating equipment (furnace versus heat pump). The `-2` fuel code is an explicit Not applicable category, not a negative number or an automatically missing answer. All 3,452 apartment records have values for these fields. Survey values may include EIA imputations. No valid extreme-consumption records were removed. Exact building apartment counts are still unavailable: this experiment does not distinguish a 5-apartment building from a 100-apartment building on that attribute.

## Fair comparison and model selection

- Reused the prior household IDs: **2,071 development apartments**, **691 validation apartments**, **690 evaluation apartments**.
- The prior experiment's calibration partition is repurposed for validation here. It is not used to claim a calibrated prediction interval.
- Trained five XGBoost feature sets: core, each new field individually, and all three together. Four fixed settings each; **20 fits total**. Settings are in `protocol-before-training.json` and every validation result is saved.
- Primary selection metric: **unweighted validation MAE**. The all-three variant was also best on validation (MAE 2,417 kWh/year). No tuning or feature selection followed inspection of evaluation results; no refit on validation.
- One-hot categorical preprocessing and XGBoost were fitted on development apartments only and saved together. Numeric values pass through. Predictions are clipped at zero consistently.
- Predictions were saved before evaluation KWH was joined. An explicit input allowlist and a poisoned-target check verify that the answer cannot enter inference. Saved-pipeline reload reproduces predictions.
- The current app's method is represented by its existing historical annual diagnostic: pre-2020 state forecasts and development-only RECS profile adjustments. Its 31 unsupported evaluation apartments remain documented, not silently dropped. Paired comparisons use the **same 659 supported apartments**; full-cohort scores are also below.

## Results on the same 659 apartments

| Method | R² | MAE (kWh/year) | Within ±20% |
|---|---:|---:|---:|
| Current household method | 0.168 | 2,648 | 27.8% |
| Apartment regional median | 0.064 | 2,735 | 27.3% |
| XGBoost: existing inputs | 0.210 | 2,640 | 27.9% |
| XGBoost: + bedrooms | 0.234 | 2,620 | 29.0% |
| XGBoost: + building age | 0.208 | 2,642 | 28.1% |
| XGBoost: + heating fuel | 0.295 | 2,434 | 30.7% |
| XGBoost: + all three | 0.325 | 2,377 | 31.4% |


**Controlled input comparison:** core XGBoost → all-three XGBoost raises R² from 0.210 to 0.325 and lowers MAE by 9.97%. Relative to the current household method, MAE falls by 10.23%. The latter comparison changes both method and features; it does not isolate the effect of the extra questions.

Heating fuel supplies most of the improvement. Bedrooms alone help a little. Building age alone does not improve this run. Because the experiment did not include a bedrooms-plus-heating-only model, it cannot isolate the added value of age after those two are included.

The prespecified exploratory success rule required at least 10% lower paired MAE than core XGBoost and higher R². The actual reduction is **9.9721%**, so it narrowly misses that exact threshold; rounding to about 10% must not be presented as passing it. This threshold was a project decision, not a universal definition of accuracy.

## Apartment categories and coverage

| Building category | Test apartments | Core R² → all three | Core MAE → all three (kWh/year) |
|---|---:|---:|---:|
| 2–4 apartments | 179 | 0.180 → 0.360 | 3,111 → 2,630 |
| 5+ apartments | 480 | 0.215 → 0.298 | 2,465 → 2,283 |


On **all 690 evaluation apartments**, core XGBoost has R² 0.205, MAE 2,650; all three has R² 0.323, MAE 2,370. Thus the improvement does not depend on retaining only the current method's supported rows.

Regional paired results for the all-three model vary: R² is about 0.093 in the Northeast, 0.271 in the Midwest, 0.240 in the South and 0.321 in the West. See `subgroup-metrics.csv` for every regional result and sample size. The overall number must not be used to claim equal accuracy everywhere.

## Weights, uncertainty and limits

The primary training and evaluation give each sampled apartment equal weight. Using RECS `NWEIGHT` for evaluation as a sensitivity check yields core R² 0.227, MAE 2,619; all-three R² 0.335, MAE 2,385. No replicate-weight population confidence intervals were computed. These are not precise national estimates of the model's error.

Only 31.4% of paired all-three predictions fall within ±20% of the recorded annual value. MAE around 2,377 kWh/year is a typical absolute error across the sample, **not an error bound for a particular apartment**. No new prediction interval is claimed.

These RECS records and the earlier evaluation scores were examined in previous project work. This is a controlled historical diagnostic, not a fresh independent external test. RECS annualized/imputed 2020 consumption is the reference, not continuous present-day meter readings. These annual household results cannot validate a future monthly estimate, an adjustment to a state forecast, or the statewide forecast R² around 0.99. The direct annual XGBoost model is a separate experiment and has not been connected to the live monthly application.

## Recommendation

Keep the current app unchanged while reviewing these results. Heating fuel is the strongest candidate if adding only one question. Adding all three improves historical prediction, but the remaining error is substantial. Any future deployment needs a clearly described annual-to-monthly method and separate validation of that output; do not attach the state model's high R² to an individual apartment estimate.

## Reproduction and files

From the HomePulse project root, using the project's existing environment:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python experiments/apartment-inputs-20261116/run_experiment.py --project . --out experiments/apartment-inputs-20261116/results-reproduction
.venv/bin/python -m pip install --target /tmp/homepulse-apartment-plot-deps -r experiments/apartment-inputs-20261116/requirements-plot.txt
PYTHONPATH=/tmp/homepulse-apartment-plot-deps MPLCONFIGDIR=/tmp/homepulse-mpl .venv/bin/python experiments/apartment-inputs-20261116/make_report.py --results experiments/apartment-inputs-20261116/results-reproduction --report reports/apartment-inputs-20261116-reproduction
```

Requires the RECS raw CSV and preserved results from `experiments/household-validation-20261115/results`, especially split IDs and historical predictions. Use a new output directory; the script refuses to overwrite an existing run. Numerical versions and hashes are recorded in the protocol. Training requires no downloading. Optional figure dependencies are installed into a temporary folder, leaving the app environment unchanged.

- `results/protocol-before-training.json`: frozen choices, input allowlist, hashes, dependency versions.
- `results/validation-candidates.csv`: all 20 validation runs.
- `results/selection-before-evaluation.json`: chosen configurations before scoring.
- `results/evaluation-predictions-before-labels.csv` and `evaluation-predictions-with-labels.csv`: household predictions and reference values.
- `results/metrics.csv`, `subgroup-metrics.csv`: full and paired, unweighted and weighted results.
- `results/*.joblib`: preprocessing plus trained experimental models.
- `results/integrity-checks.json`: unchanged production hashes and leakage/serialization checks.
- `verification.json`: 26 metric rows independently recomputed using direct error formulas.
- `apartment-input-comparison.png` / `.pdf`: comparative results figure.

Data source: [EIA RECS 2020 microdata and codebook](https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata).
