"""Independent result checks and evidence charts; does not fit or tune models."""
from pathlib import Path
import hashlib
import json
import sqlite3
import numpy as np
import pandas as pd
import joblib
import argparse
from run_experiment import ROOT, OUT, PLAN, features, predict

def dump(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")

def independent_metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    residual = y - p
    return dict(pooled_r2=float(1 - (residual ** 2).sum() / ((y - y.mean()) ** 2).sum()),
        mae_mwh=float(np.abs(residual).mean()), rmse_mwh=float(np.sqrt((residual ** 2).mean())),
        wape=float(np.abs(residual).sum() / y.sum()))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checks-only", action="store_true", help="Verify the saved evaluation without optional static-chart dependencies")
    args = parser.parse_args()
    data = pd.read_csv(OUT / "monthly-residential-sales.csv", parse_dates=["date"])
    pred = pd.read_csv(OUT / "test-predictions.csv", parse_dates=["date", "latest_observation_month"])
    scores = pd.read_csv(OUT / "test-comparison.csv").set_index("model")
    per = pd.read_csv(OUT / "test-state-metrics.csv")
    manifest = json.loads((OUT / "run-manifest.json").read_text())
    assert hashlib.sha256((ROOT / "experiment-plan.json").read_bytes()).hexdigest() == manifest["plan_sha256"]
    assert hashlib.sha256((ROOT / "run_experiment.py").read_bytes()).hexdigest() == manifest["script_sha256"]
    assert hashlib.sha256((ROOT / "raw/eia_monthly_state_sales.xlsx").read_bytes()).hexdigest() == manifest["source_sha256"]
    assert len(pred) == 1632 and pred.state.nunique() == 51
    assert pred.groupby("state").size().eq(32).all()
    joined = pred.merge(data[["state", "date", "sales_mwh"]], on=["state", "date"], validate="one_to_one", suffixes=("", "_source"))
    np.testing.assert_allclose(joined.sales_mwh, joined.sales_mwh_source, rtol=0, atol=0)
    for model in scores.index:
        m = independent_metrics(pred.sales_mwh, pred[model])
        for key, value in m.items():
            np.testing.assert_allclose(value, scores.loc[model, key], rtol=1e-10)
        for state, g in pred.groupby("state"):
            st = independent_metrics(g.sales_mwh, g[model])
            stored = per.loc[(per.model == model) & (per.state == state)].iloc[0]
            np.testing.assert_allclose(st["pooled_r2"], stored.r2, rtol=1e-10)
            np.testing.assert_allclose(st["mae_mwh"], stored.mae_mwh, rtol=1e-10)
    with sqlite3.connect(OUT / "state-electricity.sqlite") as con:
        assert con.execute("SELECT COUNT(*) FROM monthly_residential_sales").fetchone()[0] == 10200
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    f, cols = features(data)
    test = f.loc[f.date.between("2024-01-01", "2026-08-01")]
    bundle = joblib.load(OUT / "selected-backtest-model.joblib")
    assert bundle["training_target_end"] == "2023-09-01"
    np.testing.assert_allclose(predict(bundle, test), pred.xgboost, rtol=1e-12)
    timeline_checks = []
    for date in ["2022-01-01", "2024-01-01", "2026-08-01"]:
        t = pd.Timestamp(date)
        latest = t - pd.DateOffset(months=3)
        changed = data.copy()
        changed.loc[changed.date > latest, "sales_mwh"] *= 1.234567
        f_changed, _ = features(changed)
        original = f.loc[f.date == t, cols].reset_index(drop=True)
        altered = f_changed.loc[f_changed.date == t, cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(original, altered)
        timeline_checks.append({"target_month": date, "latest_allowed_month": str(latest)[:10],
            "changing_later_sales_changes_predictors": False})
    # Independently trace all lag inputs for one state back to exact source months.
    indexed = data.set_index(["state", "date"]).sales_mwh
    for _, row in test.loc[test.state == "MA"].iterrows():
        expected_mean = np.mean([indexed.loc[("MA", row.date-pd.DateOffset(months=k))] for k in range(3,15)])
        np.testing.assert_allclose(expected_mean, row.recent_mean, rtol=1e-12)
        np.testing.assert_allclose(indexed.loc[("MA",row.date-pd.DateOffset(months=12))], row.lag_12, rtol=1e-12)
    dump("independent-verification.json", {"all_checks_passed": True, "source_plan_script_hashes_match": True,
        "test_predictions_recomputed_from_saved_model": True, "independent_numpy_metrics_match": True,
        "all_test_targets_match_source": True, "sqlite_integrity": "ok", "test_rows": len(pred),
        "future_sales_mutation_checks": timeline_checks,
        "limitation": "Latest revised data used, historical publication vintages not reconstructed; this is a retrospective feasibility backtest."})

    if args.checks_only:
        print(json.dumps({"verification": "passed", "test_rows": len(pred), "plots": "not requested"}))
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import plotly.graph_objects as go

    summary = json.loads((OUT / "summary.json").read_text())
    baseline = summary["validation_selected_baseline"]
    names = {"xgboost": "XGBoost", "same_month_last_year": "Same month last year",
        "same_month_three_year_mean": "Same month: prior 3-year average",
        "recent_growth_adjusted_last_year": "Growth-adjusted last year"}
    colors = {"actual": "#143247", "xgboost": "#0B9194", "baseline": "#E29335"}
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10, "axes.spines.top":False,
        "axes.spines.right":False, "axes.labelcolor":"#143247", "text.color":"#143247"})
    fig, axes = plt.subplots(2, 2, figsize=(13.4, 8.0), sharex=True)
    for ax, state in zip(axes.flat, PLAN["example_plot_states_chosen_before_scores"]):
        g = pred.loc[pred.state == state]
        ax.plot(g.date, g.sales_mwh / 1e6, color=colors["actual"], lw=2.0, label="EIA actual")
        ax.plot(g.date, g.xgboost / 1e6, color=colors["xgboost"], lw=1.8, ls="--", label="XGBoost forecast")
        ax.plot(g.date, g[baseline] / 1e6, color=colors["baseline"], lw=1.5, ls=":", label="Prior 3-year seasonal average")
        x = per.loc[(per.state==state)&(per.model=="xgboost")].iloc[0]
        b = per.loc[(per.state==state)&(per.model==baseline)].iloc[0]
        ax.set_title(f"{state}   |   XGBoost R² {x.r2:.3f}   |   Seasonal average R² {b.r2:.3f}", loc="left", fontsize=11)
        ax.set_ylabel("Residential sales (million MWh)")
        ax.grid(axis="y", alpha=.16)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.tick_params(axis="x", rotation=20)
    handles, labels = axes[0,0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.5,.92), ncol=3, frameon=False)
    fig.suptitle("HomePulse: state electricity forecasting feasibility", x=.06, ha="left", y=.99, fontsize=19, fontweight="bold")
    fig.text(.06,.945,"Later-period test: Jan 2024–Aug 2026 · predictors use sales from at least 3 months earlier", fontsize=11)
    fig.text(.06,.025,"States selected before scores were known. Fixed model fit through Sep 2023; inputs refresh each target month.\nSource: EIA-861M monthly state sales, current revised data. These forecasts do not estimate individual homes.", fontsize=9, color="#5B7181")
    fig.tight_layout(rect=[0,.08,1,.87], h_pad=2.5)
    fig.savefig(OUT / "forecast-comparison.png", dpi=170)
    fig.savefig(OUT / "forecast-comparison.pdf")
    plt.close(fig)

    fig, axes = plt.subplots(1,2,figsize=(12,5.3))
    order = ["same_month_last_year", baseline, "xgboost"]
    labels = ["Last year,\nsame month", "Prior 3-year\nseasonal average", "XGBoost"]
    palette = ["#AAB8C2", colors["baseline"], colors["xgboost"]]
    for ax, metric, label, factor, fmt in [(axes[0],"median_state_r2","Median R² across 51 states/DC",1,".3f"),
                                          (axes[1],"mean_state_wape","Mean of state absolute-error rates (%)",100,".2f")]:
        vals = [float(scores.loc[x,metric])*factor for x in order]
        ax.bar(labels, vals, color=palette, width=.6)
        for i,v in enumerate(vals): ax.text(i,v+.015*(max(vals)),format(v,fmt),ha="center",fontweight="bold")
        ax.set_ylim(0,1 if factor==1 else max(vals)*1.22)
        ax.set_title(label, loc="left",fontsize=11)
        ax.grid(axis="y",alpha=.15)
        ax.set_axisbelow(True)
    fig.suptitle("The simpler seasonal average wins this test",x=.06,ha="left",fontweight="bold",fontsize=18)
    fig.text(.06,.88,"Jan 2024–Aug 2026 · all 50 states and Washington, D.C. · no states removed",fontsize=10)
    fig.text(.06,.04,"Error rate per state = sum of absolute errors ÷ sum of actual sales. Lower is better.\nPooled R²: XGBoost 0.990; seasonal average 0.992. Pooled scores partly reflect differences in state size.",fontsize=9,color="#5B7181")
    fig.tight_layout(rect=[0,.12,1,.84])
    fig.savefig(OUT / "model-comparison.png",dpi=170)
    plt.close(fig)

    # Offline Plotly evidence explorer. No web requests or modification of the live Streamlit app.
    fig = go.Figure()
    states = sorted(pred.state.unique())
    for st in states:
        g = pred.loc[pred.state==st]
        for column, label, color, dash in [("sales_mwh","EIA actual",colors["actual"],"solid"),
            ("xgboost","XGBoost",colors["xgboost"],"dash"),
            (baseline,"Prior 3-year seasonal average",colors["baseline"],"dot")]:
            fig.add_trace(go.Scatter(x=g.date,y=g[column],name=label,mode="lines+markers",
                visible=(st=="MA"),line=dict(color=color,dash=dash),marker=dict(size=4),
                hovertemplate="%{x|%b %Y}<br>%{y:,.0f} MWh<extra>%{fullData.name}</extra>"))
    buttons=[]
    for i,st in enumerate(states):
        a=per.loc[(per.model=="xgboost")&(per.state==st)].iloc[0]
        b=per.loc[(per.model==baseline)&(per.state==st)].iloc[0]
        title=f"{st}: monthly residential electricity sales<br><sup>Test Jan 2024–Aug 2026 · XGBoost R² {a.r2:.3f} · Seasonal average R² {b.r2:.3f}</sup>"
        buttons.append(dict(label=st,method="update",args=[{"visible":[j//3==i for j in range(len(states)*3)]},{"title":title}]))
    ma=states.index("MA")
    fig.update_layout(template="plotly_white",height=620,title=buttons[ma]["args"][1]["title"],
        xaxis_title="Target month",yaxis_title="Residential electricity sales (MWh)",
        updatemenus=[dict(buttons=buttons,active=ma,x=1,y=1.22,xanchor="right")],
        legend=dict(orientation="h",y=-.17),margin=dict(t=110,b=115,l=100,r=40),
        annotations=[dict(text="Uses observations t−3 or earlier. Retrospective test with revised EIA data; no household predictions.",
            x=0,y=-.30,xref="paper",yref="paper",showarrow=False,xanchor="left",font=dict(size=11))])
    fig.write_html(OUT / "interactive-state-backtest.html",include_plotlyjs=True,full_html=True)

    x,b=summary["xgboost"],summary["baseline"]
    text=f"""HOMEPULSE STATE FORECASTING: FEASIBILITY EXPERIMENT
Date: 13 November 2026

DECISION
Monthly state forecasting is technically feasible and has usable public data.
This test does NOT establish XGBoost as the best forecasting model. The simple
three-year seasonal average performed better in the later test period. Use it
as the benchmark and a possible first forecast model, then evaluate additions
on future unseen periods. The original HomePulse app has not been changed.

POSSIBLE REVISED PRODUCT
A user selects a state and a forecast month. The app forecasts aggregate monthly
residential electricity sales in MWh and displays historical trends and errors.
Historical sales are backend inputs; users do not enter personal bills.
Audience: energy analysts/planners. Home characteristics would no longer be the
inputs. This is a different prediction task, not evidence that the household
model reached the same accuracy. Keep the scope to a clearly tested horizon.

DATA
Official EIA source: {PLAN['source_page']}
Download: {PLAN['source_download']}
10,200 state-month observations: Jan 2010–Aug 2026, all 50 states plus DC.
Target: residential electricity SALES, MWh, source column F of Monthly-States.
The 408 observations for 2026 are preliminary. No missing months or duplicate
state-months. Only header/footer text excluded; no outliers or states removed.
Sales are not total household energy, grid peak load, or all behind-meter use.
Original workbook retained in raw/; cleaned data and SQLite database in results/.

HOW THE TEST WORKS
For each target month t, only sales dated t-3 or earlier enter predictors.
The calendar and state are known in advance. No actual future weather, current
revenue/price/customer count, or future sales is used. Predictors are lagged
sales, historical annual averages/growth, state and calendar seasonality.
Training targets: Jan 2013–Sep 2021 (5,355 rows).
Validation: Jan 2022–Sep 2023 (1,071 rows). Six XGBoost candidates tested.
Select by mean state WAPE, not by the largest pooled R2. Selection recorded
before accessing test scores. Refit selected model through Sep 2023 (6,579 rows).
Test: Jan 2024–Aug 2026 (1,632 rows), 32 months per state. Fixed model coefficients,
with historical inputs refreshed for each target month. This is a sequence of
three-month-lead forecasts, not a single 32-month-ahead forecast.
The model predicts a log ratio to a past annual mean and converts back to MWh.
This normalization is derived only from past data; evaluation is in original MWh.

RESULTS ON THE LATER TEST PERIOD
                                   XGBoost       Seasonal 3-year average
Pooled R2                          {x['pooled_r2']:.4f}         {b['pooled_r2']:.4f}
Median within-state R2             {x['median_state_r2']:.4f}         {b['median_state_r2']:.4f}
Mean state absolute-error rate     {100*x['mean_state_wape']:.2f}%          {100*b['mean_state_wape']:.2f}%
Mean absolute error, MWh           {x['mae_mwh']:,.0f}        {b['mae_mwh']:,.0f}
States/DC with R2 >= 0.9            {x['states_r2_at_least_09']}/51           {b['states_r2_at_least_09']}/51
XGBoost has lower MAE in {summary['states_with_lower_mae_than_baseline']}/51 states/DC than the validation-selected baseline.
Pooled R2 mixes different state sizes, so 0.99 does not mean 99% accuracy or
R2 >= 0.9 in each state. The simple method is a serious baseline, not a weak
comparison. Its winning test result was not used to retune the XGBoost model.
The baseline averages actual sales from the same calendar month 1, 2 and 3 years
earlier. WAPE = sum of absolute errors / sum of actuals, then averaged by state.

LIMITATIONS AND NEXT STEP
Current revised data were used, not archived releases available at each past
forecast date. The three-month information gap approximates publication delay;
historical release timing/vintages need verification for operational claims.
The test period has now been inspected. Do not keep tuning to these test scores.
No forecast intervals have been calibrated and no live deployment was made.
Before a final pivot: confirm the changed audience/target, add uncertainty,
reserve a future period for confirmation and test relevant weather information
available at forecast time if needed. Do not promise universal R2 above 0.9.

ARCHITECTURE WE CAN REUSE
EIA monthly XLSX -> pandas cleaning -> SQLite -> chronological training and
baseline comparison (scikit-learn / XGBoost) -> saved model -> prediction
service -> Streamlit state/month interface and Plotly charts/map.
Only the dataset, predictors, time-based evaluation and user form change.

EVIDENCE FILES
results/interactive-state-backtest.html: offline chart with a state selector.
results/forecast-comparison.png: four states selected before seeing scores.
results/model-comparison.png: state-level performance and baseline comparison.
results/test-state-metrics.csv: every state's metrics, without omissions.
results/test-predictions.csv: actual and predicted values for every test row.
results/independent-verification.json: independent calculations and leakage checks.
experiment-plan.json: pre-specified splits, candidates, baselines and criteria.
run_experiment.py: data preparation, model selection and test evaluation.
verify_and_report.py: independent checks and reports, no model fitting.

REPRODUCTION
Python packages/versions are recorded in results/run-manifest.json. From a copy
of this folder without results/test-predictions.csv, run run_experiment.py.
The script protects an already evaluated test from silent overwrites. Run
verify_and_report.py with matplotlib and Plotly available to regenerate charts.
The saved model is for this experiment; it is not the live household model.
"""
    (ROOT / "README.txt").write_text(text)
    print(json.dumps({"verification":"passed","plots":"created","baseline":baseline,
        "MA":per.loc[(per.state=="MA")&(per.model.isin(["xgboost",baseline])),["model","r2","wape"]].to_dict("records")}))

if __name__ == "__main__":
    main()
