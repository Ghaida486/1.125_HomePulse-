# HomePulse — proposed household validation protocol

Prepared November 14, 2026, before a new household validation run. This is a concrete evaluation plan, not a completed test or a claim of household accuracy. The current app and models are unchanged.

## What we can test with the existing files

The local RECS 2020 v7 CSV has 18,496 households and 799 columns. Its `KWH` variable is total 2020 household electricity use, including self-generation of solar power. It does not contain individual monthly KWH columns. There are 60 replicate weights in addition to `NWEIGHT`.

RECS consumption records are based on supplier data with annualization and imputation; they should be described as EIA household consumption estimates/reference values, not as an error-free meter reading for every home. EIA's monthly published tables are aggregate statistics, not individual monthly labels in our file.

The first feasible test is therefore **predicted annual household kWh versus RECS annual household KWH for the same year**. Do not compare a November 2026 estimate with annual 2020 consumption. Do not divide annual KWH by 12 and label it observed consumption for a particular month.

## Leakage that the new protocol must prevent

The app's current profile table contains all eligible RECS records. A test home's KWH would therefore influence the profile-group mean and reference mean if we simply queried that table. For household testing, rebuild the profile table from development homes only. Exclude calibration and evaluation households from every fitted ratio, baseline, imputation rule and comparison mean used to predict them.

RECS survey weights are used to form representative comparisons; they are not model input features. The actual KWH of a test home is revealed only for scoring after its estimate is produced.

## Fixed first-run design

1. Preserve the current app, its production models and state-test reports. Run this as a separate historical experiment.
2. Use the app's existing population rules and feature definitions. Document the 645 identified-solar exclusions separately from the full 18,496-household source; apartment solar status is not collected. Keep valid extreme consumption values. Do not filter records or states by prediction error.
3. Split eligible households by DOEID into 60% profile development, 20% uncertainty calibration and 20% evaluation, stratified by Census region and home type, with seed 20261114. Persist IDs and assert disjointness. No test-driven changes to size bands or minimum-support rules.
4. Rebuild the current joint home-type/size weighted profile factors from the 60% development group. Keep state → region → national fallback, minimum raw sample 50 and effective sample 30. No extra appliance inputs or past household bills are introduced.
5. Construct a **historical 2020 version of the full monthly method** and add the 12 monthly home estimates to obtain an annual prediction. Select the state-model settings only using pre-2020 state data: initial training targets January 2013–September 2017, validation January 2018–September 2019, then refit through September 2019. Keep the existing maximum of six candidates and validation criterion. Predict all 12 months of 2020 with fixed coefficients and inputs dated at least three months earlier. Earlier 2020 state observations may become allowed lag inputs for later 2020 target months, but no 2020 target is used to refit coefficients.
6. For each monthly prediction, use the account count from the permitted information cutoff, as the app does. Sum `forecast_MWh × 1,000 / held_accounts × development_profile_factor` over 2020. This tests a historical version of the current architecture, not the current 2026 model artifact against the wrong year's consumption.
7. As a diagnostic, also calculate the annual household adjustment using observed 2020 state per-account averages. Label this clearly as a **component test with state values supplied**. It shows whether the household adjustment works when state forecast error is removed; it is not an end-to-end forecasting score.
8. Predict calibration homes, construct the interval once, then score all supported evaluation homes once. Report homes for which the estimator declines to produce an output, along with the prediction coverage. Compare methods on the same households and disclose the evaluation denominator.

This 2020 household dataset and related outcomes have already been examined during earlier HomePulse development. This experiment is a transparent historical diagnostic, **not a brand-new independent final test**. The state-model family and profile approach were also chosen during prior exploration. A later household dataset or independently collected meter outcomes are required for a stronger external claim.

## Baselines, measures and the provisional improvement target

| Item | Fixed proposal for the next run |
|---|---|
| Primary simple baseline | Median annual KWH of development households in the same Census region; national development median only if a region has no support. Use the unweighted median for the primary unweighted MAE comparison. |
| Architecture baseline | Sum of the same 12 monthly state per-account forecasts with **no home-type/size adjustment**. |
| Primary error | Mean absolute error (MAE), kWh per household per year. |
| Supporting errors | RMSE, R², signed bias, median absolute percentage error and fractions within ±10% and ±20% of reference KWH. |
| Provisional project benchmark | At least 15% lower MAE than the regional-median baseline, and no higher MAE than the unadjusted state/account baseline, on the same supported evaluation homes. |
| Practical usefulness | Report the absolute kWh error as well as relative improvement. Agree with intended users on an acceptable kWh error/interval width before claiming suitability for budgeting or decisions. The 15% benchmark is a project target, not an established user requirement. |
| Failure or limited coverage | Report it unchanged. Do not move the threshold, drop hard homes or retune on evaluation outcomes. |

## Errors by group

For every home type and each of the four Census regions, report:

- Number of evaluation homes; number and share receiving predictions.
- MAE, bias, R² where defined, and improvement over both baselines.
- Sample-weighted sensitivity results alongside the primary unweighted metrics.
- Interval coverage and width where sample support permits.

Show state results only where the test sample supports interpretation. Mark groups with fewer than 50 evaluation records as low support; do not hide them or claim reliable comparisons. Overall performance does not establish equal accuracy for detached homes, apartments or every region.

## Survey weights and uncertainty are different jobs

- **Survey comparisons:** use `NWEIGHT` for development profile means. It represents how many population households each sampled record stands for.
- **Evaluation:** report ordinary household MAE/RMSE/R² and NWEIGHT-weighted versions. Weighted results are a population-oriented sensitivity analysis; account for the split when making inference, rather than treating the split sample as the entire original survey.
- **Uncertainty in group averages:** use EIA's 60 replicate weights and jackknife procedure for appropriate survey summaries. If estimating uncertainty for a fitted ratio, refit that ratio under the replicate weights. Survey standard errors are not individual-home prediction intervals.
- **Uncertainty for one prediction:** use only the separate calibration homes' absolute prediction errors to construct an 80% nominal residual band. Apply nonnegative clipping to its lower endpoint. On evaluation homes, report observed coverage and mean/median width, overall and by supported groups. Treat this as an empirical survey-sample interval; do not claim per-home, national-population or future-year guarantees from it. The current annual model's old interval cannot be reused for this different hybrid method.

## What is needed to validate the actual monthly app output

Obtain matching **monthly household kWh outcomes** together with state, month, home type and the correct floor-area definition. These may be a compatible public dataset or a consented validation pilot. Bills/meter readings are the hidden outcome for evaluation; users need not enter them as a prediction input in the app.

Freeze the method and predictions before looking at the validation outcomes. Match calendar periods and distinguish grid imports from total consumption for solar homes. A small volunteer pilot can expose problems and demonstrate the process, but it cannot establish national accuracy. If collecting multiple months per home, keep entire homes together when separating development and evaluation, and account for repeated observations when estimating uncertainty.

## What we can say at Deliverable 2

The state forecasting stage has been evaluated against actual state records. Household validation now has a defined target, leakage-safe comparison procedure, named baselines, error measures, subgroup reporting and uncertainty plan. A household accuracy result will be reported only after running that test. An annual 2020 test does not validate monthly 2026 performance.

## Sources checked

- EIA RECS 2020 microdata and codebook: https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata
- EIA microdata weighting guide: https://www.eia.gov/consumption/residential/data/2020/pdf/microdata-guide.pdf
- EIA consumption methodology: https://www.eia.gov/consumption/residential/data/2020/pdf/2020%20RECS%20CE%20Methodology%20-%20Monthly%20Appendix%20-%20Final.pdf
- EIA published monthly aggregate tables: https://www.eia.gov/consumption/residential/data/2020/index.php?view=consumption
- Local `data/raw/recs2020_public_v7.csv` and `recs2020_codebook_v7.xlsx`: target, columns and weight availability verified.
- Local `scripts/build_monthly.py`, `src/homepulse/monthly.py`, and current architecture documentation: current profile construction and inference rules verified.
- Abel and John feedback supplied by the user.
