# HomePulse midpoint video script

Ghaida Aljuhani · MIT 1.125 · November 18, 2026

Target: **4 minutes 50 seconds**, including a **65-second live app demo**. Rehearse to check your speaking pace. Read only the narration aloud; recording cues and source notes are for preparation.

- [PowerPoint with speaker notes](HomePulse_Deliverable_2_Final.pptx)
- [Slides-only PDF](HomePulse_Deliverable_2_Final.pdf)
- [Recording checklist](recording-checklist.txt)
- [Open the live app](https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/)

Record three clips: slides 1–9 (2:40), the app (1:05), then slides 11–12 (1:05). Slide 10 is the backup demo slide.

## Slide 1: HomePulse midpoint check-in

**0:00–0:15 (15 seconds)**

### Narration

Hi, I’m Ghaida Aljuhani. HomePulse helps renters and homebuyers across the United States estimate electricity use before moving into a home. Today, I’ll demonstrate the app and explain how its estimates are produced.

### What to show

Clip A. Slide 1. Start recording on the cover. Introduce the United States audience and advance at fifteen seconds.

<details>
<summary>Sources and preparation notes</summary>

Submitted HomePulse proposal cover and current README.

</details>

## Slide 2: Electricity planning before moving

**0:15–0:35 (20 seconds)**

### Narration

Renters and homebuyers need electricity estimates before moving. EIA’s household survey runs roughly every four years, with consumption results released later. HomePulse combines these household patterns with monthly state data to support planning.

### What to show

Clip A. Slide 2. Point to the household survey publication lag and the actual app form. RECS is not an annual survey. EIA’s state electricity-sales data is monthly. The 2024 RECS consumption results are scheduled for spring 2027. Do not imply that all EIA data arrives every four years or that HomePulse replaces official survey statistics.

<details>
<summary>Sources and preparation notes</summary>

EIA RECS FAQs: https://www.eia.gov/consumption/residential/faqs.php (current four-year cycle; historical intervals have varied). 2024 consumption release schedule: https://www.eia.gov/consumption/residential/data/2024/index.php?view=consumption (spring 2027). Monthly state electricity data: https://www.eia.gov/electricity/data/eia861m/ . Verified November 18, 2026. Publication lag does not mean an overdue release. HomePulse uses historical household patterns for planning scenarios; this does not establish current household accuracy.

</details>

## Slide 3: The data behind the estimate

**0:35–0:50 (15 seconds)**

### Narration

Two datasets support this: monthly state residential sales and account counts, plus RECS household characteristics, annual electricity use and survey weights.

### What to show

Clip A. Slide 3. Point to state sales and accounts, then household floor area, annual kWh and weight. These are selected real source rows, not example data.

<details>
<summary>Sources and preparation notes</summary>

data/ and docs/data-and-cleaning.md; https://www.eia.gov/electricity/data/state/ ; https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata .

</details>

## Slide 4: Working system architecture

**0:50–1:05 (15 seconds)**

### Narration

Python prepares both datasets. State forecasts and household records enter SQLite first. The matcher then builds supported household comparisons for JSON export. The website validates this snapshot and calculates the monthly home estimate.

### What to show

Clip A, slide 4. Follow EIA preparation, training and batch forecasts into SQLite. Follow RECS preparation into the same database. Then trace SQLite to SurveyProfileMatcher, JSON export, snapshot validation and the public app. SQLite storage precedes matching; JSON export follows matching. Spend 15 seconds here. Streamlit is the local database-backed prototype; the browser uses only exported aggregate data.

<details>
<summary>Sources and preparation notes</summary>

README.md, Implemented architecture; docs/architecture.md; web-app-20261116/scripts/export_snapshot.py loads the SQLite snapshot before constructing SurveyProfileMatcher. Forecasting saves fitted preprocessing and models and exports evaluation reports. The public app validates aggregate JSON, looks up a state forecast and applies a household factor. State forecast per account × household profile factor = monthly kWh scenario. Inputs are state, month, home type and floor area. The household scenario still requires separate predictive validation.

</details>

## Slide 5: Technologies used in HomePulse

**1:05–1:25 (20 seconds)**

### Narration

These are the tools behind each step. Pandas cleans data, scikit-learn evaluates predictions, and XGBoost forecasts state sales. HTML structures the website, CSS styles it, and JavaScript updates estimates. Plotly creates the clickable map and charts. Streamlit is the local prototype, with code and tests on GitHub.

### What to show

Clip A, slide 5. Use 20 seconds to explain the role list. Emphasize that Plotly supplies the clickable US map and charts, while HTML, CSS and JavaScript provide the public website structure, appearance and interactions. These technologies are already used. EIA API integration and GitHub Actions are planned additions on the final next-steps slide.

<details>
<summary>Sources and preparation notes</summary>

Verified current implementation: web-app-20261116/dist/index.html, styles.css, app.js, model.js and evidence-view.js; src/homepulse/; scripts/; experiments/state-forecast-20261113/; app.py; docs/architecture.md. Repository: https://github.com/Ghaida486/1.125_HomePulse- . Plotly choropleth/scattergeo renders the US map, Plotly scatter traces render the electricity outlook, and a Plotly bar trace compares the home scenario with the state account average. JavaScript validates the saved snapshot and calculates the household scenario. XGBoost forecasts are computed offline in Python. The public website does not run Streamlit or retrain XGBoost on user input.

</details>

## Slide 6: Code: forecasting without the target answer

**1:25–1:45 (20 seconds)**

### Narration

First, the forecasting code uses electricity history at least three months before the target. This shift prevents the answer entering the rolling average. Training, validation and testing follow time order. A challenge test changes later data and checks that the earlier prediction inputs stay unchanged.

### What to show

Clip A. Slide 6. Point at shift(3), the timeline and the leakage challenge. These are actual source excerpts, with unrelated lines omitted.

<details>
<summary>Sources and preparation notes</summary>

experiments/state-forecast-20261113/run_experiment.py, features() and fit(); tests/test_monthly.py, test_forecast_rows_and_no_future_input_leakage.

</details>

## Slide 7: Code: selecting a supported household comparison

**1:45–2:05 (20 seconds)**

### Narration

Second, the matching engine tries state, region, then national comparisons. It requires enough records and checks whether a few survey weights dominate. For our apartment example, Massachusetts has only seventeen matches, so the engine selects one hundred forty-nine Northeast homes and saves the reason.

### What to show

Clip A. Slide 7. Point to the two support checks and the Massachusetts-to-Northeast table. Effective count measures support, not predictive accuracy.

<details>
<summary>Sources and preparation notes</summary>

src/homepulse/peer_matching.py: effective_sample_size(), SurveyProfileMatcher.match(). Frozen MA / home type 5 / 1,000–1,499 sq ft profile.

</details>

## Slide 8: Code: validating the public calculation

**2:05–2:25 (20 seconds)**

### Narration

Third, browser checks reject inconsistent forecasts and unsupported profiles. Python and JavaScript agree across three thousand three hundred sixty-six scenarios. Twenty-four deliberately corrupted snapshots are rejected. These are implementation checks. The full functions and tests are available in the GitHub repository.

### What to show

Clip A, slide 8. Stay on the slide and point to the code excerpt and test results. The code explanation is delivered from the slides. A separate GitHub screen recording is not needed.

<details>
<summary>Sources and preparation notes</summary>

docs/code-walkthrough.md; web-app-20261116/scripts/verify.mjs and verify-contracts.mjs. November 18 verification: 23 Python tests, 3,366 parity cases, 24 corrupted snapshots rejected. These checks do not establish household accuracy.

</details>

## Slide 9: Predicted versus actual state sales

**2:25–2:40 (15 seconds)**

### Narration

Across sixteen hundred thirty-two later state-month records, XGBoost’s pooled R-squared is point nine nine zero. The seasonal baseline performs better overall. These results evaluate state electricity sales; individual household accuracy requires separate evaluation. Now I’ll show the working website.

### What to show

Clip A, slide 9. Point to the scatter and both methods in the table. End this clip after saying “Now I’ll show the working website.” Target clip length: 2:40. The website demonstration will be recorded separately and inserted next.

<details>
<summary>Sources and preparation notes</summary>

reports/monthly/test-predictions.csv and test-comparison.csv. Test: Jan 2024–Aug 2026. XGB R² 0.9902358247446271; three-year same-month baseline R² 0.992415697733024. MAE 151,477 versus 133,306 MWh.

</details>

## Slide 10: Live app: estimate and matching evidence

**2:40–3:45 (65 seconds)**

### Narration

Let’s try the app. I’ll select Massachusetts and November, then an apartment in a building with five or more apartments. I’ll enter one thousand square feet for my apartment. The app updates to about three hundred thirty-eight kilowatt-hours, compared with four hundred seventy-nine for the state account average. I can open the calculation to see the profile factor and why the comparison uses Northeast homes. The dashed line shows where the forecast begins. I can download the calculation and supporting details. I’ll return to the slides to explain the remaining risks and next steps.

### What to show

Clip B: record only the actual website for about 1:05. Slide 10 is a backup screenshot and notes page, not an extra narrated slide. Before recording, open the app, let it load, and choose a different starting profile so the changes are visible. 0–12 seconds: select Massachusetts using the map or dropdown and November 2026. 12–25 seconds: choose an apartment in a building with 5+ apartments and enter 1,000 sq ft. The app updates as fields change; use Update my estimate if needed. 25–35 seconds: point to 338 kWh and the 479 kWh state account average. 35–50 seconds: expand the calculation and matching evidence, showing factor 0.707 and the 17 Massachusetts / 149 Northeast matching records. 50–60 seconds: scroll to the dashed forecast boundary and point to the download control. 60–65 seconds: say the transition back to the slides. Keep estimates in their actual screen order; no staged reveal is required. The merged video reaches 3:45 here.

<details>
<summary>Sources and preparation notes</summary>

https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/ ; saved Sep–Nov 2026 snapshot. The displayed estimates round to 338 and 479 kWh. This is a household planning scenario, not a validated monthly prediction.

</details>

## Slide 11: Remaining risks

**3:45–4:10 (25 seconds)**

### Narration

The main uncertainty is the household step. It transfers annual patterns from twenty-twenty into a monthly scenario. Actual use also depends on occupancy, equipment and weather. Survey support checks improve the evidence behind comparisons, but do not prove accuracy. The stronger seasonal baseline is another finding we need to address.

### What to show

Clip C, slide 11. Begin this separate recording on the risks slide, immediately after the website clip in the final edit. Explain the three limitations for about 25 seconds. Keep the household accuracy distinction clear.

<details>
<summary>Sources and preparation notes</summary>

docs/evaluation.md; README sections 6–7. The existing annual household diagnostic is not a validation of the public monthly output.

</details>

## Slide 12: Next steps before the final submission

**4:10–4:50 (40 seconds)**

### Narration

For the final project, I’ll add a Compare Two Homes mode, with side-by-side profiles, linked charts and a downloadable report. I’ll automate EIA updates with validation and a safe fallback. I’ll strengthen evaluation against the baseline and examine household errors by type and region. I’ll test state forecast uncertainty separately from household uncertainty, then automate checks through GitHub Actions, verify a fresh installation and test usability. These are the next development milestones.

### What to show

Clip C, slide 12. Use about 12 seconds to describe the planned Compare Two Homes feature: two independently selected locations and home profiles, comparison charts and an exportable report. Use the remaining 28 seconds for the supporting coding work: API updates, stronger evaluation, tested uncertainty ranges and automated checks. All five are planned additions. Existing tests already run locally, while GitHub Actions automation is future work. End this clip after the slide. The combined target is 4:50, including the 1:05 live demo. Leave no extra narrated demo slide or long transitions.

<details>
<summary>Sources and preparation notes</summary>

The user approved Compare Two Homes as a planned final-project feature on November 18, 2026. It will compare planning scenarios by state, selected forecast month, home type and floor area. The planned feature includes two independent profiles, linked charts and a downloadable comparison report. Do not imply measured savings, causal effects or validated individual-home accuracy. User-approved final-development plan and Abel/John feedback. EIA API documentation: https://www.eia.gov/opendata/documentation.php . API integration, expanded evaluation, tested state-forecast intervals and GitHub Actions are planned additions, not completed capabilities. API updates must validate incoming data, retain dated source snapshots and preserve the previous working snapshot on failure. Define the baseline, metrics and useful error thresholds before further model selection. Use a predeclared later period or compatible independent data when available. Previously inspected test results remain exploratory for later tuning. Measure interval coverage on data separate from interval calibration. State forecast intervals do not establish uncertainty coverage for the household scenario. Household evaluation must account for survey weights and distinguish annual diagnostics from validation of monthly app estimates. Existing code tests will be reused in automated checks. API integration does not bypass EIA publication timing or by itself improve model accuracy.

</details>
