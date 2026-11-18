# HomePulse supporting documentation

The [project README](../README.md) is the main explanation of completed work,
technologies, architecture, code, demo, risks and next steps.

| Document | Purpose |
|---|---|
| [Midpoint presentation and video script](midpoint/video-script.md) | Final PPTX with speaker notes, slides-only PDF, 4:50 narration and live-demo recording cues |
| [Visual app walkthrough](../README.md#5-demo--what-currently-works) | Five current app screenshots with explanations of the inputs, estimate, forecast chart and calculation |
| [Code walkthrough](code-walkthrough.md) | Forecast feature safeguards, survey matching, browser contracts and their challenge tests |
| [System architecture](architecture.md) | Offline model development, SQLite storage, export and public/local app execution |
| [Data sources and cleaning](data-and-cleaning.md) | Variables, cleaning checks, exclusions, units, survey weights and source hashes |
| [Model evaluation](evaluation.md) | XGBoost graph, baseline comparisons, test periods, subgroup errors and household limitations |
| [Installation and reproduction](setup.md) | Run the public app, rebuild data/models and execute checks |
| [Response to instructor feedback](feedback-response-20261114.md) | How baseline, leakage, tuning, weights and uncertainty suggestions were addressed |
| [Household validation protocol](household-validation-plan-20261114.md) | Preserved design required to reproduce the historical household investigation |
| [Fresh-build evidence, November 14](setup-verification-20261114.md) | Historical verification of installation and full model/data rebuilding |
| [Selected file manifest](github-upload-files.txt) | Exact files prepared for the implementation repository |

## Data and reference documents

- [Included U.S. electricity-sales data](../data/README.md): original EIA Excel
  workbook, cleaned 10,200-row residential sales CSV and source manifest.
- [RECS 2020 codebook](references/recs2020_codebook_v7.xlsx): unchanged reference
  copy used to interpret household categories, response codes, annual KWH and weights.
- [Official RECS microdata page](https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata).
- [EIA microdata weighting guide](https://www.eia.gov/consumption/residential/data/2020/pdf/microdata-guide.pdf).

The project uses final survey weights for profile means. It does not claim to
implement the guide's full replicate-weight uncertainty procedure.

## Evaluation evidence

- [State forecast report](../reports/monthly/accuracy-check-20261114/accuracy-review.md)
- [Overall XGBoost graph](../reports/monthly/overall-xgboost-predicted-vs-actual.png)
- [Household historical report](../reports/household-validation-20261115/household-validation-report.md)
- [Apartment input experiment](../reports/apartment-inputs-20261116/apartment-input-report.md)

The current midpoint presentation and recording guide are included under `docs/midpoint/`.
Older recording drafts, the course handout and duplicate figure formats are excluded.
