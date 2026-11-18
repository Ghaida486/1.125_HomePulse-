# HomePulse — data sources and cleaning

## 1. State electricity dataset

Source: [EIA monthly state electricity data](https://www.eia.gov/electricity/data/state/),
monthly EIA-861M workbook. The studied snapshot contains 10,200 observations:
50 states plus D.C., each with 200 months from January 2010 to August 2026.

The preparation code verifies the **residential** column heading and **MWh** units.
It reads year, month, geography, source-status label and residential sales; the app
builder also retains residential customer counts. Electricity sales are a quantity
of delivered electricity, not money.

Implemented checks:

- Convert numeric columns with errors raised for invalid values; construct month dates.
- Sort within each state and check exactly one observation per state/month.
- Verify the complete expected monthly sequence, positive sales and account counts,
  and absence of missing required values.
- Preserve source status and SHA-256 provenance. The 408 observations in 2026 are
  preliminary in this snapshot.
- Exclude header/footer text only. Keep all 10,200 actual observations; no valid
  outlier removal or missing-value imputation is performed.

The [training code](../experiments/state-forecast-20261113/run_experiment.py) saves
prepared state data to an experiment SQLite database. The
[app builder](../scripts/build_monthly.py) creates the final app database after
batch forecasts are prepared.

## 2. Household profile dataset

Source: [RECS 2020 v7](https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata).
The local source contains 18,496 surveyed households. Use the included
[codebook](references/recs2020_codebook_v7.xlsx) for response meanings.

| Field | Role |
|---|---|
| `DOEID` | Household identifier, used for traceability and disjoint evaluation splits |
| `state_postal`, `REGIONC` | State and Census-region matching |
| `TYPEHUQ` | Home type: mobile home, detached, attached, apartment in a 2–4 unit building, or apartment in a 5+ unit building |
| `TOTSQFT_EN` | Home floor-area measure; mapped into the implemented size bands |
| `KWH` | Annual household electricity reference value; used to build development profile means and score household diagnostics |
| `NWEIGHT` | Final survey weight for population-representative profile means |
| `SOLAR` | Identifies the solar-home exclusions used by the current profile method |

The public profile build excludes 645 identified solar homes and retains 17,851
records. This is a documented population rule, not removal based on prediction error.
Solar status is not collected for apartments, so it cannot identify every solar home.
The RECS KWH measure includes self-generation, while state sales describe purchased
electricity; this is one reason the two data sources need careful interpretation.

Survey codes are interpreted by variable; a code such as `-2` is not automatically
treated as a real numerical measurement or as missing everywhere. The separate
apartment experiment, for example, handles `FUELHEAT = -2` as Not applicable.

## 3. Profiles, support and storage

The weighted mean is `sum(KWH × NWEIGHT) / sum(NWEIGHT)`. The profile factor divides
the chosen home-type/size mean by the all-home mean in the same geography. Support
requires at least 50 records and effective sample size 30, calculated as
`sum(weights)^2 / sum(weights^2)`. Matching falls back from state to region to nation.
These support rules are project choices; they are not a guarantee of representativeness.

The final SQLite database stores observations, forecasts, eligible profile records,
test predictions, state metrics and metadata. The public export contains aggregate
profile summaries, not individual household rows.

For household validation, profile factors are rebuilt using development households
only. Evaluation households' actual KWH cannot influence their own predicted profile
means. The complete protocol is in the
[household evaluation plan](household-validation-plan-20261114.md).

## 4. Sources and reproducibility

The downloader checks the studied files against these SHA-256 values:

- State workbook: `c7963ad7c9bd2020cc7472f100a9c5330a4dff97a62be95407137a14b9c4044e`
- RECS CSV: `8d5f6d3120d2cbc2535151c7d455e7a536ca9768f773e15edd45932ec38b3592`

A changed source file stops the fixed-study rebuild. See [setup](setup.md) for the
download sequence and verified-cache option. The original state workbook and cleaned sales CSV are
[included in the data folder](../data/README.md). The RECS CSV is downloaded
separately. The codebook under `references/` is retained as documentation.
