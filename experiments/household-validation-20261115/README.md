# HomePulse household validation — 2026-11-15

This is a separate historical diagnostic following the plan saved on November 14. It does not replace the current app or production models. The results are preserved; reruns must use a new output directory.

Start with the included [report](../../reports/household-validation-20261115/household-validation-report.md) and [chart](../../reports/household-validation-20261115/household-validation.png). Full result artifacts are generated, not uploaded.

The annual household result is R² 0.279 and MAE 4,259 kWh/year on 3,515 supported evaluation homes. 56 further evaluation homes received no estimate. The household method improved MAE by 10.7% over the regional median and did not meet the prespecified 15% target. These are not the state-level model scores.

## Reproduce from the HomePulse project root

First complete the [monthly rebuild](../../docs/setup.md) in a **fresh checkout**, then use its activated virtual environment. The build supplies raw RECS and the monthly database. The included protocol is `docs/household-validation-plan-20261114.md`. The run manifest records package versions and hashes. The source snapshot preserves the exact app calculation and state-model functions used in this run.

```sh
.venv/bin/python experiments/household-validation-20261115/run_validation.py --project . --out experiments/household-validation-20261115/results
.venv/bin/python experiments/household-validation-20261115/verify_results.py --project . --results experiments/household-validation-20261115/results
```

These paths also supply the split IDs and predictions required by the subsequent apartment experiment. In an existing working project, do not overwrite its results; use a separate fresh checkout for the full reproduction sequence. The first command refuses to overwrite existing results. The verification recomputes every supported household prediction, checks source reference values and allowed customer counts, and independently recomputes errors and interval coverage. It does not retune the model.

Chart generation additionally requires Matplotlib, alongside pandas, NumPy and Plotly. Charts can be regenerated from saved results without retraining:

```sh
python experiments/household-validation-20261115/make_report.py --results experiments/household-validation-20261115/results
```

This diagnostic uses previously explored 2020 records. It does not establish fresh external accuracy, monthly household accuracy or present-day accuracy. The app's four user inputs are unchanged.
