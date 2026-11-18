# HomePulse web app

A responsive web interface for the existing HomePulse monthly electricity planner. The underlying Python/SQLite training project is retained separately; this app uses a verified export of its aggregate snapshot. It does not train a model on each page visit or call an external AI service.

## Run and verify

Requires Python 3 to preview and Node.js 18+ for verification. No JavaScript dependency installation is needed.

```sh
python3 -m http.server 8767 --directory dist
node scripts/verify.mjs
```

Open `http://127.0.0.1:8767/`. Deployable static files are in `dist/`. Hosting-specific identity files are excluded from this repository; this package can be served by a static web host.

## What works

- Clickable U.S. state map and equivalent accessible dropdown, including Alaska, Hawaii and D.C.
- Four inputs: state/district, saved estimate month, home type, own unit floor area.
- Monthly home-profile planning estimate with a state-account comparison, supporting survey count and disclosed geographic fallback.
- State electricity outlook and home-versus-state Plotly comparisons.
- Model scores and actual-versus-predicted evaluation graphs are kept in the repository and presentation, outside the user interface.
- Downloadable estimate report, official source links and a plain-language explanation of the estimate.
- Responsive desktop/phone layout, input checks and unsupported-profile handling.

## Data and calculation

Snapshot generated 2026-11-16 from the current project's `data/homepulse_monthly.sqlite`. EIA observations end August 2026. Available saved forecasts are September–November 2026. This is a frozen research snapshot; there is no automatic data refresh.

Formula: state forecast MWh × 1,000 ÷ assumed residential accounts × RECS profile factor. The factor is a survey-weighted home-type/size-band mean divided by the geographic reference mean. State support falls back to region and then nation, requiring at least 50 survey records and an effective sample of 30. Unsupported profiles return no result.

The export contains 153 state/month forecasts, 1,530 aggregate profile groups (1,122 supported), the latest 24 observation months per state, with model evaluation records stored separately in `evidence/model-results.json`. No individual RECS survey records are published. User form entries are processed in the browser; no app analytics or form-submission endpoint is implemented.

## Validation and interpretation

`scripts/verify.mjs` checks all 3,366 supported state/month/type/size-band cases against Python-generated reference outputs, all 408 unsupported profile groups, boundary cases and the pooled R² recalculated from the exported predictions. The Massachusetts November 2026 1,000-sq-ft apartment in a 5+ unit building reproduces 338 kWh.

Historical state test (Jan 2024–Aug 2026): XGBoost pooled R² 0.990236 and WAPE 6.0859%; seasonal baseline R² 0.992416 and WAPE 5.3558%. The baseline is stronger overall. These aggregate scores **do not validate individual household accuracy**. Household output is an unvalidated planning scenario. Annual 2020 profile differences are assumed to apply to each forecast month; electricity accounts and RECS households are not identical populations. No household prediction interval is available. Revised EIA historical records were used rather than reconstructed publication vintages.

Bedrooms, building age and heating type remain offline experiments and are not published inputs. This web work does not change model scores, training data or the Streamlit production implementation.

## Updating the snapshot

Run using the original project's Python environment, which contains pandas and Plotly:

```sh
/path/to/HomePulse/.venv/bin/python scripts/export_snapshot.py --project /path/to/HomePulse
node scripts/verify.mjs
```

Review the app's fixed date labels and UI after any data refresh. Do not relabel state-level accuracy as household accuracy.

## File guide

- `dist/index.html` / `styles.css`: interface and responsive theme.
- `dist/app.js`: form, map, outlook and household comparison views.
- `dist/model.js`: pure validated estimate calculation.
- `dist/assets/homepulse-data.json`: aggregate production snapshot with provenance hashes.
- `scripts/export_snapshot.py`: reproducible SQLite-to-JSON export and Python parity fixtures.
- `evidence/model-results.json`: technical model scores and 1,632 historical test records; not deployed to the app.
- `scripts/verify.mjs`: calculation parity, support rules, boundaries and metric checks.

## Sources and libraries

- [EIA monthly state electricity data](https://www.eia.gov/electricity/data/state/)
- [EIA RECS 2020 microdata](https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata)
- Plotly.js, bundled from the existing Python Plotly installation; retains its MIT license header.
- U.S. boundary asset: `https://cdn.plot.ly/usa_110m.json`, bundled locally for the map.

HomePulse is a student research project by Ghaida Aljuhani for MIT 1.125, not an EIA product.
