# HomePulse midpoint video — slides and speaker notes

Ghaida Aljuhani · MIT 1.125 · November 18, 2026

The recorded video runs **4 minutes 57 seconds**. These are the supporting speaker
notes from the recording deck, with superseded preparation references removed.
They are not a verbatim audio transcript. The 4:50 timings below are rehearsal cues;
the recorded transitions and speaking pace differ.

- [PowerPoint with speaker notes](HomePulse_Deliverable_2_Final.pptx)
- [Slides-only PDF](HomePulse_Deliverable_2_Final.pdf)
- [Recording checklist](recording-checklist.txt)
- [Open the app](https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/)

The sequence follows the instructors' requested introduction, pitch, technology,
code, demonstration, risks and next steps. Slides 6–8 explain actual implementation
excerpts; slide 10 supports the app demonstration.

Slide 11 covers **data freshness** and **source availability**, with a planned
response to each. Slide 12 shows **Compare two homes**, **EIA API integration**,
**Stronger evaluation** and **Tested uncertainty ranges**. The closing narration
prioritizes the first three and treats prediction ranges as time permitting.

## Slide 1: HomePulse midpoint check-in

**Rehearsal guide: 0:00–0:10 (10 seconds)**

### Speaker notes

Hi, I’m Ghaida Aljuhani. I’m building HomePulse to help U.S. renters and homebuyers explore electricity use before moving into a home.

### Demonstration / preparation cues

Clip A. Begin on the original cover slide. Introduce yourself and the U.S. audience. Speak directly to the viewer, then advance.

<details>
<summary>Sources and context</summary>

Submitted HomePulse proposal cover and current README.
Repository: https://github.com/Ghaida486/1.125_HomePulse-
Code version: 608ea3bee773d9b31e8bcb2a5191d709a94c94c9
Live app: https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/
Cover illustration reused from the submitted proposal; original notes credit OpenAI image generation. EIA logo: https://www.eia.gov/global/images/logos/eia_logo_print.png .

</details>

## Slide 2: Electricity planning before moving

**Rehearsal guide: 0:10–0:35 (25 seconds)**

### Speaker notes

Before signing a lease, you know the rent, location and size. Electricity use often remains unknown. HomePulse turns familiar home details into a monthly planning estimate. Household surveys arrive less frequently than monthly state electricity data, so the challenge is connecting these sources while making the calculation and its limits clear.

### Demonstration / preparation cues

Point to the renter/homebuyer audience, then the app form. Pause briefly after the opening situation. The publication gap refers to RECS household data, not all EIA data. The app supports electricity planning and does not replace official statistics.

<details>
<summary>Sources and context</summary>

README sections 1–2. The household output is a planning scenario.
Repository: https://github.com/Ghaida486/1.125_HomePulse-
Code version: 608ea3bee773d9b31e8bcb2a5191d709a94c94c9
Live app: https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/
EIA RECS FAQs: https://www.eia.gov/consumption/residential/faqs.php (four-year cycle; historical intervals vary). 2024 consumption release: https://www.eia.gov/consumption/residential/data/2024/index.php?view=consumption (spring 2027). State electricity data is monthly: https://www.eia.gov/electricity/data/eia861m/ . Verified November 18, 2026. Publication lag does not mean the release is overdue.

</details>

## Slide 3: The data behind the estimate

**Rehearsal guide: 0:35–0:55 (20 seconds)**

### Speaker notes

HomePulse uses two sources of data. Monthly state data shows residential electricity sales and customer account counts. The household survey shows how electricity use differs by home type and size. I use pandas to check the data, exclude solar homes from the comparison, and calculate averages using the survey’s population weights

### Demonstration / preparation cues

Point to sales and account counts in the upper table, then home type, size, annual kWh and weight in the lower table. The source has 18,496 homes; the profile calculation retains 17,851 after excluding 645 identified solar homes. This is a documented analysis filter, not deletion of the raw source. Do not read every row or number.

<details>
<summary>Sources and context</summary>

data/ and docs/data-and-cleaning.md; https://www.eia.gov/electricity/data/state/ ; https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata .
Repository: https://github.com/Ghaida486/1.125_HomePulse-
Code version: 608ea3bee773d9b31e8bcb2a5191d709a94c94c9
Live app: https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/
RECS type 2 = detached; type 5 = apartment in a building with 5+ apartments. Annual kWh and weights shown rounded. The source rows do not directly link individual homes to state accounts.

</details>

## Slide 4: Working system architecture

**Rehearsal guide: 0:55–1:15 (20 seconds)**

### Speaker notes

The architecture separates model development from the public website. Python prepares data, evaluates forecasting models and stores results in SQLite. A matching engine builds household comparisons. A checked JSON snapshot connects this pipeline to the browser, where JavaScript calculates the estimate without retraining the model.

### Demonstration / preparation cues

Trace the upper EIA path through training and batch forecasts into SQLite. Trace RECS into the same database, then follow matching, aggregate JSON export, snapshot validation and the public website. Keep the pointer slow. SQLite precedes matching. The browser reads saved forecasts and group summaries.

<details>
<summary>Sources and context</summary>

README.md, Implemented architecture; docs/architecture.md; web-app-20261116/scripts/export_snapshot.py loads the SQLite snapshot before constructing SurveyProfileMatcher. Forecasting saves fitted preprocessing and models and exports evaluation reports. The public app validates aggregate JSON, looks up a state forecast and applies a household factor. State forecast per account × household profile factor = monthly kWh scenario. Inputs are state, month, home type and floor area. The household scenario still requires separate predictive validation.
Repository: https://github.com/Ghaida486/1.125_HomePulse-
Code version: 608ea3bee773d9b31e8bcb2a5191d709a94c94c9
Live app: https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/

</details>

## Slide 5: Technologies used in HomePulse

**Rehearsal guide: 1:15–1:33 (18 seconds)**

### Speaker notes

Pandas prepares the data, while scikit-learn and XGBoost handle modelling. The public site uses HTML, CSS and JavaScript, with Plotly powering the map and charts. Streamlit supports the local prototype. GitHub contains the implementation and tests. Here are three decisions that matter in the code.

### Demonstration / preparation cues

Follow the technology roles rather than reading the entire table. SQLite was explained on the preceding architecture slide. Transition to the code slides. Streamlit is the local prototype; the published app uses HTML, CSS and JavaScript.

<details>
<summary>Sources and context</summary>

Verified current implementation: web-app-20261116/dist/index.html, styles.css, app.js, model.js and evidence-view.js; src/homepulse/; scripts/; experiments/state-forecast-20261113/; app.py; docs/architecture.md. Repository: https://github.com/Ghaida486/1.125_HomePulse- . Plotly choropleth/scattergeo renders the US map, Plotly scatter traces render the electricity outlook, and a Plotly bar trace compares the home scenario with the state account average. JavaScript validates the saved snapshot and calculates the household scenario. XGBoost forecasts are computed offline in Python. The public website does not run Streamlit or retrain XGBoost on user input.

</details>

## Slide 6: Code: forecasting without the target answer

**Rehearsal guide: 1:33–1:55 (22 seconds)**

### Speaker notes

First, the model must never see the answer it is predicting. This shift uses electricity history at least three months before the target. Training, validation and testing follow time order. I also test this rule by changing later records and checking that earlier prediction inputs stay identical.

### Demonstration / preparation cues

Point to shift(3), then the chronological split and the challenge test. Explain why the shift exists, rather than reading the code line by line. The historical test updates the allowed lag history for each target month; it is not a single forecast made years in advance.

<details>
<summary>Sources and context</summary>

experiments/state-forecast-20261113/run_experiment.py, features() and fit(); tests/test_monthly.py, test_forecast_rows_and_no_future_input_leakage.
Repository: https://github.com/Ghaida486/1.125_HomePulse-
Code version: 608ea3bee773d9b31e8bcb2a5191d709a94c94c9
Live app: https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/

</details>

## Slide 7: Code: selecting a supported household comparison

**Rehearsal guide: 1:55–2:15 (20 seconds)**

### Speaker notes

Secondly, This part of the code chooses comparable homes from the survey. It first searches within the selected state. If there are too few matches, it expands to the region. In this example, Massachusetts has only seventeen matching homes, so the app uses one hundred forty-nine Northeast homes.

### Demonstration / preparation cues

Point to the two support checks, then the Massachusetts and Northeast rows. The rule requires at least 50 records and an effective count of 30. A broader group supplies more survey support, but that alone does not establish prediction accuracy.

<details>
<summary>Sources and context</summary>

src/homepulse/peer_matching.py: effective_sample_size(), SurveyProfileMatcher.match(). Frozen MA / home type 5 / 1,000–1,499 sq ft profile.
Repository: https://github.com/Ghaida486/1.125_HomePulse-
Code version: 608ea3bee773d9b31e8bcb2a5191d709a94c94c9
Live app: https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/
Excerpt from SurveyProfileMatcher.match(); comment marks omitted lines. Effective n = (sum weights)^2 / sum squared weights. Source normalizes weights first for numerical stability. Thresholds are support rules, not accuracy guarantees.

</details>

## Slide 8: Code: validating the public calculation

**Rehearsal guide: 2:15–2:30 (15 seconds)**

### Speaker notes

Third, I check that the browser calculation matches Python. All three thousand three hundred sixty-six reference scenarios agree, and the validation rejects twenty-four corrupted snapshots. These checks verify implementation consistency. Predictive accuracy needs a different test.

### Demonstration / preparation cues

Point to the calculation, then the agreement count and rejected snapshots. The slide also lists 23 passing Python tests. These are software checks, not a claim that every home estimate is accurate. Advance to the actual-versus-predicted graph.

<details>
<summary>Sources and context</summary>

docs/code-walkthrough.md; web-app-20261116/scripts/verify.mjs and verify-contracts.mjs. November 18 verification: 23 Python tests, 3,366 parity cases, 24 corrupted snapshots rejected. These checks do not establish household accuracy.
Repository: https://github.com/Ghaida486/1.125_HomePulse-
Code version: 608ea3bee773d9b31e8bcb2a5191d709a94c94c9
Live app: https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/
The four code lines are excerpts from estimate() with intervening lookup and conversion lines omitted. Explain the source excerpt from this slide; the full code remains available on GitHub.

</details>

## Slide 9: Predicted versus actual state sales

**Rehearsal guide: 2:30–2:55 (25 seconds)**

### Speaker notes

This graph compares predicted and actual electricity sales for 1,632 monthly state records. XGBoost has an overall R-squared of 0.99. A simple seasonal average performed slightly better. These results apply to whole states. Individual home estimates still need separate testing. Now, I’ll show the app.

### Demonstration / preparation cues

Point to the diagonal: points near it indicate closer predicted and actual values. Then show both methods in the table, including the baseline's lower MAE. Pooled R-squared includes differences in state size; it is not 99 percent household accuracy. End Clip A after the transition to the app.

<details>
<summary>Sources and context</summary>

reports/monthly/test-predictions.csv and test-comparison.csv. Test: Jan 2024–Aug 2026. XGB R² 0.9902358247446271; three-year same-month baseline R² 0.992415697733024. MAE 151,477 versus 133,306 MWh.
Repository: https://github.com/Ghaida486/1.125_HomePulse-
Code version: 608ea3bee773d9b31e8bcb2a5191d709a94c94c9
Live app: https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/
All test records shown. Median within-state XGBoost R²: 0.852. Pooled R² includes variation in state size. Historical release vintages were not reconstructed. Original fixed test results are retained.

</details>

## Slide 10: Live app demo

**Rehearsal guide: 2:55–4:00 (65 seconds)**

### Speaker notes

Suppose I’m considering an apartment in Massachusetts. I select the state and November, choose a building with five or more apartments, and enter one thousand square feet for my own unit.

The estimate is about three hundred thirty-eight kilowatt-hours for the month, compared with four hundred seventy-nine for the state account average.

The calculation multiplies the state average by a home-profile factor from similar survey homes. The matching panel explains why it uses Northeast records.

Below, the solid line shows recorded state sales, and the dashed line marks the forecast. I can also download the estimate and its supporting details.

That is the working prototype. The next question is how much confidence to place in the household number.

### Demonstration / preparation cues

Clip B. Record the actual website for 1:05; use it instead of narrating slide 10 again. Open https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/ and let it load before recording. 0–17 seconds: select Massachusetts on the map or dropdown, choose November 2026, choose Apartment — building with 5+ apartments, enter 1,000 sq ft for this apartment, and click Update my estimate. 17–30 seconds: point to about 338 kWh and the 479 kWh forecast state-account average. 30–45 seconds: open the calculation and matching details; show the 0.707 factor and the 17 Massachusetts / 149 Northeast records. 45–57 seconds: scroll to the state outlook, indicate the solid historical line, dashed forecast and forecast-start label, and point to the download control. 57–65 seconds: pause on the result and deliver the transition back to slides. Read the numbers actually shown. Slide 10 remains a backup image.

<details>
<summary>Sources and context</summary>

https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/ ; saved Sep–Nov 2026 snapshot. The displayed estimates round to 338 and 479 kWh. This is a household planning scenario, not a validated monthly prediction.
Repository: https://github.com/Ghaida486/1.125_HomePulse-
Code version: 608ea3bee773d9b31e8bcb2a5191d709a94c94c9
Live app: https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/
This slide is a backup. Prefer the actual live app for this 65-second clip. Screenshot is the verified November 18 release. Do not add a second demo slot.

</details>

## Slide 11: Risks and planned responses

**Rehearsal guide: 4:00–4:20 (20 seconds)**

### Speaker notes

The remaining external risks are data delays and temporary interruptions to EIA’s data service. I’ll refresh the data when new releases are available and keep the last validated dataset if an update fails. Next, I’ll show the improvements planned for the final submission.

### Demonstration / preparation cues

Resume after the demo. Briefly describe the two external dependencies and the planned response to each. API-based updates and fallback handling are planned final-project work. Transition directly to slide 12. The model evaluation, baseline comparison and household validation limits remain on slide 9 and in the final-project evaluation plan.

<details>
<summary>Sources and context</summary>

Based on the project’s EIA data sources and planned EIA API integration on slide 12. Service interruption is a possible future operational risk, not a reported outage. Retaining a validated snapshot is a planned safeguard. This slide focuses on external dependencies; the state-to-household validation limits remain elsewhere in the deck.
Repository: https://github.com/Ghaida486/1.125_HomePulse-

</details>

## Slide 12: Next steps before the final submission

**Rehearsal guide: 4:20–4:50 (30 seconds)**

### Speaker notes

For the final submission, I’ll focus on three improvements.
First, I’ll add Compare Two Homes, so users can compare options side by side and download the results.
Second, I’ll automate EIA data updates, while keeping a working backup.
Third, I’ll strengthen forecast testing by comparing predictions with a simple seasonal baseline and checking errors across states.
If time allows, I’ll also test prediction ranges.
My goal is a useful electricity planning tool for U.S. households. Thank you.

### Demonstration / preparation cues

Close on the planned work. Give Compare Two Homes about 9 seconds, then cover data updates, evaluation and uncertainty. These are planned capabilities. Define practical error thresholds before further model selection; assess household uncertainty separately from state forecast intervals. API updates do not remove publication delays. End the final clip naturally without adding another summary slide.

<details>
<summary>Sources and context</summary>

The user approved Compare Two Homes as a planned final-project feature on November 18, 2026. It will compare planning scenarios by state, selected forecast month, home type and floor area. The planned feature includes two independent profiles, linked charts and a downloadable comparison report. Do not imply measured savings, causal effects or validated individual-home accuracy. User-approved final-development plan and Abel/John feedback. EIA API documentation: https://www.eia.gov/opendata/documentation.php . API integration, expanded evaluation, tested state-forecast intervals are planned additions, not completed capabilities. API updates must validate incoming data, retain dated source snapshots and preserve the previous working snapshot on failure. Define the baseline, metrics and useful error thresholds before further model selection. Use a predeclared later period or compatible independent data when available. Previously inspected test results remain exploratory for later tuning. Measure interval coverage on data separate from interval calibration. State forecast intervals do not establish uncertainty coverage for the household scenario. Household evaluation must account for survey weights and distinguish annual diagnostics from validation of monthly app estimates. Existing implementation tests remain available in the repository. API integration does not bypass EIA publication timing or by itself improve model accuracy.
Repository: https://github.com/Ghaida486/1.125_HomePulse-
Live app: https://homepulse-energy-planner.aljuhanighaida.chatgpt.site/

</details>
