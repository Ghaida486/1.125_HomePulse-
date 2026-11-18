# HomePulse setup verification — November 14, 2026

**Result:** the current monthly app rebuilt successfully in a clean source copy and
new Python environment. No GitHub upload, commit or remote change was performed.

## What was tested

The clean copy contained source code, the fixed experiment plan, tests, configuration
and dependency lock. It did **not** receive any original model, SQLite database or
saved prediction results. Python 3.12.14 was used on this Apple Silicon Mac.
Dependencies were freshly installed from `requirements-lock.txt`; `pip check`
reported no broken requirements. HomePulse was installed editable as documented.
Package metadata includes the required `states.json` resource.

Both raw sources were freshly downloaded from EIA. Their checksums matched the
original snapshots:

| File | SHA-256 |
|---|---|
| EIA monthly workbook | `c7963ad7c9bd2020cc7472f100a9c5330a4dff97a62be95407137a14b9c4044e` |
| RECS 2020 v7 CSV | `8d5f6d3120d2cbc2535151c7d455e7a536ca9768f773e15edd45932ec38b3592` |

The README's experiment, independent-check and monthly-build commands were then run
in order. The original experiment settings were not changed or retuned.

| Check | Outcome |
|---|---|
| Fixed historical experiment rebuilt | Same selected configuration and test scores |
| Independent evaluation checks | Passed: metrics, source targets, saved-model predictions and future-input mutation checks |
| Every historical test row | All 1,632 records exactly match the original result |
| Production forecast records | All 153 records exactly match the original result |
| SQLite | Integrity `ok`; 10,200 observations, 153 forecasts, 17,851 profiles, 1,632 test rows, 204 state-metric rows |
| Monthly acceptance suite in fresh copy | **6 passed** in 3.75 seconds, including Streamlit input changes and Plotly evidence |
| Full regression suite in existing project | **26 passed** in 9.76 seconds, including preserved annual-workspace fixtures |
| Rebuilt Streamlit server | Started on temporary local port 8502; health and root returned HTTP 200; stopped afterward |
| Existing-database protection | Rebuild refused to overwrite it; checksum stayed unchanged |
| Demo calculation | MA / Nov 2026 / detached / 1,800 sq ft = 514.859995 kWh, displayed as 515 |

The six monthly tests are a subset of the full suite, not 32 different tests.
The fresh copy does not build the legacy annual artifacts; those additional tests
were run against the existing complete project. The existing app on port 8501 was
not replaced by this check.

## Setup corrections made

- Replaced annual-workspace README instructions with the tested monthly build sequence.
- Added a fixed-source downloader with checksum verification and an explicit cache option.
- Added `--checks-only` so independent verification does not require optional static
  chart dependencies. The Plotly app remains fully supported by the pinned packages.
- Made static experiment PNGs optional in the monthly build; numerical verification
  remains required. Added a guard against replacing an existing app database.
- Declared the direct NumPy dependency and included `states.json` in package metadata.
- Expanded ignore rules for generated experiment sources/models and local credentials.
- Reconciled architecture, midpoint status, walkthrough and speaker notes with the
  app's offline forecast build and interactive SQLite lookup.

## Limits of this check

This is a reproducibility check on the current machine, not cross-platform testing.
The machine already supplies an OpenMP runtime needed by XGBoost. Installation and
source downloads need internet access. EIA may revise its workbook: a future changed
checksum will stop this fixed build. Preserve a versioned source snapshot before
relying on long-term external reproduction.

Reproducing previously inspected test results does not create a new independent test.
The state model's pooled R² is not household accuracy. The seasonal baseline still
performs better overall, and the household profile calculation remains unvalidated.

## Evidence and next step

Machine-readable records and compact logs are in [compact rebuild record](setup-check-20261114/rebuild-verification.json).
The source-copy workspace used for this check is separate from the user's Desktop
project; the tested source/documentation corrections are copied back without replacing
its data or model artifacts.

Before uploading, review the exact submission contents and instructor destination.
The local repository is still uncommitted; no submission is implied by these checks.
Current implementation, data and setup instructions are described in the root README.
