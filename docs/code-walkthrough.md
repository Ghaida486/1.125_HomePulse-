# HomePulse: the engineering behind an estimate

Updated November 18, 2026. This guide points to implemented code and checks.
The November 18 changes strengthen traceability and rejection of invalid data;
they do not retrain XGBoost or establish new household prediction accuracy.

## 1. Construct features that cannot see the target answer

**Code:** [`make_features()`](../src/homepulse/monthly.py),
[`features()`, `fit()` and `predict()`](../experiments/state-forecast-20261113/run_experiment.py).

Each state is sorted by month before lagged sales and growth features are created.
For a target month, the newest sales observation is three months earlier. Shifting
before rolling means the target's answer is never included in a rolling average.
The fitted encoder and XGBoost model are saved together. Model selection uses the
validation period, followed by evaluation on later months and seasonal baselines.

**Challenge test:** `test_forecast_rows_and_no_future_input_leakage` multiplies all
sales after an example cutoff by five. Features for that prediction must remain
identical. This tests the cutoff behavior, rather than just checking a variable name.

## 2. Match survey profiles with both support and weight checks

**Code:** [`SurveyProfileMatcher`](../src/homepulse/peer_matching.py).

The matcher validates its source records, takes its own copy, and caches aggregate
summaries by geography. Repeated exports reuse these summaries instead of filtering
all household records for every forecast month. Individual records stay offline.

It tries **state → region → United States**. At each step it matches home type and
floor-area band jointly, then checks both:

- At least 50 matching records.
- Effective sample size of at least 30: `(sum(weights))² / sum(weights²)`.

The effective count addresses weight concentration. Sixty records with one very
large survey weight can have an effective count below two. A simple row-count check
would incorrectly accept that group. The thresholds are support rules, not evidence
of prediction accuracy or a substitute for survey-design variance estimation.

For the first qualifying geography, the factor is the weighted mean annual kWh of
matching homes divided by the weighted mean of all retained homes in that geography.
The result contains **every attempted geography, its counts, the decision and reasons**.
If none qualifies, `ProfileSupportError` carries the rejected attempts without a factor.
Malformed source data raises a separate error and stops the export.

**Example:** Massachusetts, apartment in a building with 5+ apartments, 1,000 sq ft:

| Attempt | Records | Effective count | Decision |
|---|---:|---:|---|
| Massachusetts | 17 | 16.6 | Both support thresholds fail |
| Northeast | 149 | 131.8 | Selected |

**Challenge tests:** [`test_peer_matching.py`](../tests/test_peer_matching.py) checks
small groups, concentrated weights, national fallback, no supported group, missing or
invalid measurements, duplicate households and accidental mutation by a caller.

## 3. Reject inconsistent snapshots before showing a result

**Code:** [`validateSnapshot()`, `validateSupport()` and `estimate()`](../web-app-20261116/dist/model.js).

The browser checks the snapshot's schema, complete state-month coverage, unique
forecasts, positive finite sales/account counts and the three-month cutoff. It also
checks that each exported profile factor agrees with its two weighted means and
that all geography decisions follow the declared support rules. A duplicate forecast
cannot silently select the first row, and a missing profile cannot silently default
to an average home. The selected calculation is checked again at request time.

**Challenge tests:** [`verify-contracts.mjs`](../web-app-20261116/scripts/verify-contracts.mjs)
intentionally corrupts 24 snapshots: duplicate or missing forecasts, non-finite sales,
invalid account counts, late observations, altered factors, weakened support rules,
inconsistent geography and other failures. Every corrupted snapshot must be rejected.

## 4. Carry the calculation into the interface and download

**Code:** [`export_snapshot.py`](../web-app-20261116/scripts/export_snapshot.py),
[`evidence-view.js`](../web-app-20261116/dist/evidence-view.js),
[`app.js`](../web-app-20261116/dist/app.js).

The exporter separates aggregate public data from repository-only model evidence.
The website displays four calculated steps and the matching decision table. The
JSON download contains those calculation inputs, matching attempts, source links,
snapshot date and database checksum. Invalid form entries clear the old result,
comparison chart and evidence panel and disable the download.

The four calculation steps are:

1. Look up state residential sales forecast in MWh.
2. Multiply by 1,000 and divide by assumed residential accounts for kWh/account.
3. Obtain the weighted home-profile factor and its supporting geography.
4. Multiply the account average by the factor for a monthly planning scenario.

The app uses full precision internally and rounds only for display. Floor area selects
a band; it does not imply continuous scaling within that band.

## Verification performed November 18

- **23 Python tests passed**: 13 new matching tests and the 10 monthly/map tests.
- **3,366 supported scenarios** agree between JavaScript and Python.
- Comparison with the previous committed reference scenarios found **zero numerical change**.
- **408 unsupported groups** still return no estimate.
- **24 corrupted snapshots** are rejected, plus a duplicate lookup check.
- Browser checks: apartment example, expanded calculation/matching evidence, invalid
  floor area clears old results, recovery after correcting the input, and a downloaded
  JSON report containing the matching trail. No browser console errors were reported.

These are implementation and regression checks. The state-model results and the
remaining household validation limitations are unchanged; see [evaluation](evaluation.md).

## Reproduce the checks

After installing the project and building the SQLite snapshot as described in
[setup](setup.md):

```bash
pytest -q tests/test_peer_matching.py tests/test_monthly.py tests/test_monthly_map.py
python web-app-20261116/scripts/export_snapshot.py --project .
node web-app-20261116/scripts/verify.mjs
node web-app-20261116/scripts/verify-contracts.mjs
```

The 13 matching tests use small constructed datasets and need no SQLite file.
The two browser calculation scripts use the included aggregate snapshot and need
no Python installation. Exporting from an existing database is supported with
`--database /path/to/homepulse_monthly.sqlite`.
