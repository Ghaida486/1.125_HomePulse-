# HomePulse — prediction accuracy check

November 14, 2026. The model and app were not changed. This recalculates the existing historical test, rather than creating a new independent test.

## The question

Can the model predict a value close to the actual recorded electricity sales when that answer is hidden?

For each test month, the prediction uses only state/calendar inputs and state electricity records at least three months old. The separate hidden-answer audit removes the target value and all newer-than-cutoff sales and reproduces all 1,632 stored predictions. Actual values are then used to score the results.

## Results

| Metric | XGBoost | Seasonal average |
|---|---:|---:|
| Pooled R² | 0.990 | 0.992 |
| Mean absolute error, MWh/state-month | 151,477 | 133,306 |
| WAPE | 6.09% | 5.36% |
| Predictions within 5% of actual | 50.9% (830/1632) | 58.0% (946/1632) |
| Predictions within 10% of actual | 82.2% (1342/1632) | 85.9% (1402/1632) |
| Predictions within 20% of actual | 99.6% (1625/1632) | 99.4% (1623/1632) |

WAPE is total absolute error divided by total actual sales. Each state-month receives equal weight in the threshold percentages. These descriptive thresholds were not a previously agreed pass criterion and are not future prediction guarantees.

## Concrete examples

The first three Massachusetts test months are shown below, without selection based on their error.

| Month | Actual MWh | Predicted MWh | Absolute error |
|---|---:|---:|---:|
| 2024-01 | 1,881,843 | 1,821,753 | 3.19% |
| 2024-02 | 1,751,571 | 1,675,800 | 4.33% |
| 2024-03 | 1,660,660 | 1,564,120 | 5.81% |

## What this answers for Abel

- The actual-versus-predicted comparison, named baseline and error measures are explicit.
- Every state has separate metrics in accuracy-results.json; the app also exposes state-specific results.
- The baseline still performs better overall, so this is not evidence that XGBoost adds predictive value over it.
- A practical household error target and independent validation of the RECS-adjusted household output are still needed.
- The evaluated target is state-level monthly sales. It is not the electricity bill or consumption of one home.
- Do not use these already-inspected test results to select further model settings and call them a fresh final test.

Source: the existing read-only data/homepulse_monthly.sqlite and its documented EIA snapshot. Prediction-time masking verification: docs/target-input-audit-20261114/result.json.

Reproduce by running evaluate_predictions.py with --project pointing at the HomePulse root and --output pointing at an output directory. The script reads the source database and produces this report, a figure and overall/per-state metrics; it never fits or replaces a model.

Plotting uses matplotlib; its exact helper dependencies are recorded in plot-requirements.txt. They were installed into an isolated work folder, not into the HomePulse app environment. Recreate these in a separate report environment when rerunning the figure.
