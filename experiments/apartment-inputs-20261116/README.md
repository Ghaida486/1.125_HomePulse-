# Apartment input experiment — 16 November 2026

Tested bedrooms, building age range and main heating fuel before changing HomePulse. The live app was not changed.

Read the [results report](../../reports/apartment-inputs-20261116/apartment-input-report.md) and [comparison chart](../../reports/apartment-inputs-20261116/apartment-input-comparison.png).

On the same 659 supported evaluation apartments, XGBoost with state, apartment category and unit area scored R² 0.210 and annual MAE 2,640 kWh. Adding all three fields scored R² 0.325 and MAE 2,377 kWh. The current household method's annual diagnostic scored R² 0.168 and MAE 2,648 kWh. Heating fuel helped most; age alone did not improve the result.

All 690 evaluation apartments were also scored: all-three R² 0.323 and MAE 2,370 kWh. The difference in counts is the current method's coverage, not removal of hard cases. Training used 2,071 apartments and validation used 691. Four fixed configurations per feature set, 20 fits in total; selection used validation MAE before evaluation.

This is a historical annual RECS 2020 diagnostic on previously explored data. It does not validate future monthly estimates or attach the state model's R² to a household estimate.

## Code walkthrough

- `run_experiment.py`: reads the existing split IDs, validates the three new fields, fits categorical preprocessing and XGBoost together, selects settings on validation MAE, then saves predictions before joining evaluation answers.
- `make_report.py`: recomputes errors independently from the saved predictions, verifies configuration selection and produces the figure/report.
- `results/protocol-before-training.json`: explicit input fields, bounded settings, selection criterion, code/data hashes and installed versions.
- `results/`: saved experimental models, split IDs, validation results, all evaluation predictions and subgroup errors. This folder is generated and ignored by the project Git configuration.

Reproduction commands and caveats are in the results report. Figure generation uses optional `requirements-plot.txt` dependencies in a temporary folder, not the app's environment.

## Fresh-checkout prerequisite

Complete the [monthly rebuild](../../docs/setup.md), followed by the
[household diagnostic reproduction](../household-validation-20261115/README.md).
The apartment script reads split IDs and historical predictions from
`experiments/household-validation-20261115/results/`; these are generated in that
step and are intentionally not part of the upload. Then run the commands in the
results report using a new output directory.
