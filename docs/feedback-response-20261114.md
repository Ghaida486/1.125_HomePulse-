# HomePulse — response to Abel and John's proposal feedback

Originally reviewed November 14; updated November 17, 2026 for the current public
web app and completed historical diagnostics. This separates implemented responses
from remaining work.

## John: baseline, leakage and tuning time

“Prevent target leakage” and “time-box XGBoost tuning” are separate requests.
The first means keeping the answer and unavailable future information out of inputs.
The second means limiting model experimentation so the app and evaluation get time.

| Suggestion | Implemented response | Boundary |
|---|---|---|
| Simple baseline | Prior three-year same-month mean on the same 1,632 state test targets | Baseline MAE 133,306 MWh is better than XGBoost's 151,477; both are reported |
| Prevent leakage | Chronological splits, features at least three months old, independent future-input and saved-prediction checks | Revised historical releases were used, not archived real-time vintages |
| Limit tuning | Six prespecified state configurations, chosen on validation before reporting test results | No elapsed-time budget was recorded; do not claim one |
| Manage survey cleaning | Documented RECS codes, survey weights, home categories, size bands and solar exclusions | Annual survey relationships are assumptions when used for a future month |

## Abel: make evaluation and comparisons specific

| Suggestion | Evidence now available | Still unresolved |
|---|---|---|
| Name baseline and error measure | State: seasonal mean, MAE in MWh, WAPE and R². Household: regional median, MAE in annual kWh and R² | The state model's high pooled R² is not household accuracy |
| Define useful improvement | Household diagnostic specified 15% lower MAE than the regional median; observed improvement was 10.7% | Target not met; define a practical monthly household error tolerance with intended users |
| Show errors by groups | All states in state reports; household errors by region and home type; apartment experiment by region and building category | Unequal performance and support counts must remain visible in evidence |
| Explain survey weights | NWEIGHT-weighted profile means; state → region → national fallback; minimum 50 records and effective sample 30; weighted error sensitivity reported | No survey-design population confidence intervals were computed |
| Acknowledge 2020 limitations | Historical annual profiles are distinguished from newer monthly state forecasts | Newer state totals do not update or validate individual-home relationships |
| Explain uncertainty | Separate annual diagnostic: nominal 80% interval, observed coverage 80.2%, about ±6,455 kWh/year | Interval is broad and is not deployed as monthly uncertainty; monthly household accuracy remains unvalidated |

The household diagnostic uses separate development/calibration/evaluation homes,
and hides evaluation KWH during prediction. However, the dataset had already been
explored in earlier work; this is not a fresh independent external test.

The apartment experiment tested answerable extra inputs before changing the app.
Adding bedrooms, age and heating fuel reduced paired annual MAE from 2,640 to 2,377
kWh (9.9721%) and raised R² from 0.210 to 0.325. It narrowly missed its 10% improvement
rule and does not establish monthly accuracy. The four public inputs remain unchanged.

## How the implementation addresses the feedback

The architecture separates offline training from app lookup/calculation. The code
preserves preprocessing with the model and checks historical feature cutoffs.
State results include XGBoost and the stronger seasonal benchmark. Household and
apartment reports retain subgroup errors, uncertainty limits and support counts.
The public app provides four inputs, comparisons and a calculation explanation;
technical scores remain in repository evidence. Household validation remains the
main technical next step.

## Evidence

- [Architecture](architecture.md)
- [State results](../reports/monthly/accuracy-check-20261114/accuracy-review.md)
- [Household validation](../reports/household-validation-20261115/household-validation-report.md)
- [Apartment experiment](../reports/apartment-inputs-20261116/apartment-input-report.md)
- [Code explanation](../README.md#4-code--what-has-been-implemented)
- [Data and cleaning](data-and-cleaning.md)
- [Evaluation guide](evaluation.md)

For future model changes, plan a new evaluation before looking at its outcomes.
Repeating the old test does not make it an untouched final test.
