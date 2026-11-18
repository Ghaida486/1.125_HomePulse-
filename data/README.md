# HomePulse data included in the repository

The U.S. residential electricity-sales data used by the state model are included.
These are the frozen study files, not forecasts or illustrative sample data.

| File | Contents |
|---|---|
| [Original EIA Excel workbook](sources/eia_monthly_state_sales.xlsx) | Exact EIA-861M workbook used in the project; includes residential sales and account counts, as well as other sectors present in the original source |
| [Cleaned residential sales CSV](sources/monthly_residential_sales_2010_2026.csv) | All 10,200 cleaned state-month sales observations, January 2010–August 2026; 50 states plus Washington, D.C. |
| [Source manifest](source-manifest.json) | Official source URLs, coverage, file sizes and SHA-256 hashes |

## CSV columns

| Column | Meaning |
|---|---|
| `year` | Observation year |
| `month` | Calendar month, 1–12 |
| `state` | Two-letter state code or `DC` |
| `source_status` | EIA's Final/Preliminary status for the observation |
| `sales_mwh` | Residential electricity sold, measured in megawatt-hours; this is quantity, not sales revenue |
| `date` | Observation month represented by its first day |

The CSV is an unchanged copy of the prepared table produced by the original
experiment. The preparation code removes workbook headers/footer text and validates
rows, dates and units; it retains all 10,200 observations. Customer counts are in the
Excel workbook and are read by the app-database builder. The 408 observations for
2026 are preliminary in this snapshot.

Official source: [EIA historical state electricity data](https://www.eia.gov/electricity/data/state/).
The precise [workbook URL](https://www.eia.gov/electricity/data/state/xls/861m/HS861M%202010-.xlsx)
may later return a revised release; the included copy preserves the studied version.

## Reproduction

Run `python scripts/download_monthly_sources.py` from the repository root. It verifies
and copies the included workbook into the experiment's expected raw-data location.
It also downloads and checks the RECS household CSV if that file is not already
available. With the bundled workbook present, state-source installation needs no
internet connection.

The full RECS 2020 household CSV is **not bundled**. Its download/checksum procedure
is included, together with the [RECS codebook](../docs/references/recs2020_codebook_v7.xlsx).
The public app's aggregate household profiles are included in
[its JSON snapshot](../web-app-20261116/dist/assets/homepulse-data.json).
Generated SQLite databases and fitted model binaries are rebuilt using the
[setup instructions](../docs/setup.md).
