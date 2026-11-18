"""Independently check saved errors and create the experiment report/figure."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--results",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    a=ap.parse_args()
    p,r=a.results,a.report
    r.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(p/"evaluation-predictions-with-labels.csv")
    metrics=pd.read_csv(p/"metrics.csv")
    groups=pd.read_csv(p/"subgroup-metrics.csv")
    summary=json.loads((p/"summary.json").read_text())
    candidates=pd.read_csv(p/"validation-candidates.csv")
    selected=json.loads((p/"selection-before-evaluation.json").read_text())
    checked=0
    for row in metrics.itertuples():
        f=d if row.cohort=="all_apartments" else d.loc[d.supported]
        y=f.KWH.to_numpy(); pred=f[row.method].to_numpy()
        w=f.NWEIGHT.to_numpy() if row.weighting=="survey_weighted_sensitivity" else np.ones(len(f))
        err=pred-y
        mae=np.average(np.abs(err),weights=w)
        rmse=np.sqrt(np.average(err**2,weights=w))
        r2=1-np.sum(w*err**2)/np.sum(w*(y-np.average(y,weights=w))**2)
        within=100*np.average(np.abs(err)<=.2*y,weights=w)
        np.testing.assert_allclose([mae,rmse,r2,within],[row.mae_kwh,row.rmse_kwh,row.r2,row.within_20_pct],rtol=1e-10)
        assert len(f)==row.n
        checked+=1
    for variant,entry in selected["variants"].items():
        best=candidates.loc[candidates.variant==variant].sort_values(["mae_kwh","configuration"]).iloc[0]
        assert int(best.configuration)==entry["configuration"]
    assert selected["winner_by_validation"]==min(selected["variants"],key=lambda k:(selected["variants"][k]["validation"]["mae_kwh"],k))
    assert len(d)==690 and int(d.supported.sum())==659
    integrity=json.loads((p/"integrity-checks.json").read_text())
    assert integrity["production_unchanged"] and integrity["target_excluded_from_features"]
    verification=dict(metric_rows_recomputed_independently=checked,all_metrics_match=True,
        selections_match_validation_mae=True,evaluation_count=690,paired_count=659,
        no_live_app_changes=True)
    (r/"verification.json").write_text(json.dumps(verification,indent=2)+"\n")
    b=metrics.loc[(metrics.cohort=="paired_supported")&(metrics.weighting=="unweighted")].set_index("method")
    methods=["current_method","core","bedrooms","building_age","heating_fuel","all_three"]
    names=["Current method","XGBoost · existing inputs","+ Bedrooms only","+ Building age only","+ Heating fuel only","+ All three"]
    colors=["#98A8B9","#5A8DEE","#5A8DEE","#5A8DEE","#218F95","#096D74"]
    fig,axes=plt.subplots(1,2,figsize=(13.4,6.8),gridspec_kw={"wspace":.22})
    fig.patch.set_facecolor("#F7FAFC")
    y=np.arange(len(methods))
    for ax in axes:
        ax.set_facecolor("#F7FAFC")
        ax.spines[["top","right","left"]].set_visible(False)
        ax.spines["bottom"].set_color("#AEBBC7")
        ax.tick_params(axis="y",length=0,labelsize=11,pad=12)
        ax.tick_params(axis="x",colors="#526775")
        ax.set_axisbelow(True);ax.grid(axis="x",alpha=.14)
        ax.invert_yaxis()
    axes[0].barh(y,[b.loc[m,"r2"] for m in methods],height=.56,color=colors)
    axes[0].set_yticks(y,names)
    axes[0].set_xlim(0,.40);axes[0].set_xticks([0,.1,.2,.3,.4])
    axes[0].set_title("R² · higher is better",loc="left",fontsize=14,pad=18,fontweight="bold",color="#17334A")
    for i,m in enumerate(methods):
        axes[0].text(b.loc[m,"r2"]+.009,i,f"{b.loc[m,'r2']:.3f}",va="center",fontsize=11,color="#17334A")
    axes[1].barh(y,[b.loc[m,"mae_kwh"] for m in methods],height=.56,color=colors)
    axes[1].set_yticks(y,[""]*len(y));axes[1].set_xlim(0,3250)
    axes[1].set_title("Annual MAE · lower is better",loc="left",fontsize=14,pad=18,fontweight="bold",color="#17334A")
    axes[1].set_xlabel("kWh per apartment per year",fontsize=11,color="#526775",labelpad=10)
    for i,m in enumerate(methods):
        axes[1].text(b.loc[m,"mae_kwh"]+45,i,f"{b.loc[m,'mae_kwh']:,.0f}",va="center",fontsize=11,color="#17334A")
    fig.suptitle("Do three extra home details help?",x=.065,y=.96,ha="left",fontsize=24,fontweight="bold",color="#17334A")
    fig.text(.065,.884,"Same 659 evaluation apartments · RECS 2020 annual household electricity",fontsize=12,color="#526775")
    fig.text(.065,.10,"Heating fuel provides the largest improvement. All three reduce MAE by about 10% versus core XGBoost.",fontsize=11,color="#17334A")
    fig.text(.065,.056,"Historical diagnostic; previously explored data. These are household scores, not the state forecast R². App unchanged.",fontsize=10,color="#526775")
    fig.subplots_adjust(left=.245,right=.96,top=.78,bottom=.22)
    fig.savefig(r/"apartment-input-comparison.png",dpi=180,facecolor=fig.get_facecolor())
    fig.savefig(r/"apartment-input-comparison.pdf",facecolor=fig.get_facecolor())
    plt.close(fig)

    def table(frame,rows):
        s="| Method | R² | MAE (kWh/year) | Within ±20% |\n|---|---:|---:|---:|\n"
        for m in rows:
            x=frame.loc[m]
            s+=f"| {x.label} | {x.r2:.3f} | {x.mae_kwh:,.0f} | {x.within_20_pct:.1f}% |\n"
        return s
    core,allthree=b.loc["core"],b.loc["all_three"]
    sub=groups[(groups.cohort=="paired_supported")&(groups.dimension=="TYPEHUQ")&(groups.weighting=="unweighted")].copy()
    subgroup="| Building category | Test apartments | Core R² → all three | Core MAE → all three (kWh/year) |\n|---|---:|---:|---:|\n"
    for code,label in [("4","2–4 apartments"),("5","5+ apartments")]:
        s=sub[sub.group.astype(str)==code].set_index("method")
        c,n=s.loc["core"],s.loc["all_three"]
        subgroup+=f"| {label} | {int(n.n)} | {c.r2:.3f} → {n.r2:.3f} | {c.mae_kwh:,.0f} → {n.mae_kwh:,.0f} |\n"
    full=metrics[(metrics.cohort=="all_apartments")&(metrics.weighting=="unweighted")].set_index("method")
    weighted=metrics[(metrics.cohort=="paired_supported")&(metrics.weighting=="survey_weighted_sensitivity")].set_index("method")
    text=f"""# HomePulse apartment input experiment — 16 November 2026

Adding bedrooms, building age and main heating fuel improves this historical apartment model, but does not establish precise individual-home or future-month accuracy. The live app, production model and database were not changed.

## What was tested

The question is whether adding three answerable home details improves prediction of one apartment's annual electricity use. Target: RECS 2020 `KWH`, annual household electricity in kWh. No past electricity bill, electricity spending, target-derived end-use consumption or actual test KWH is an input.

| App question represented | Dataset field | Handling |
|---|---|---|
| State | `state_postal` | Category |
| Apartment building category | `TYPEHUQ` | 2–4 or 5+ apartments; category |
| Your own apartment size | `TOTSQFT_EN` | Numeric square feet, not total building area |
| Number of bedrooms | `BEDROOMS` | Numeric 0–6; 6 is top-coded |
| When the building/home was built | `YEARMADERANGE` | Nine year ranges, not an exact year |
| Main heating fuel | `FUELHEAT` | Electricity, natural gas, propane, oil, wood, other, or Not applicable |

Here heating type means **fuel**, not heating equipment (furnace versus heat pump). The `-2` fuel code is an explicit Not applicable category, not a negative number or an automatically missing answer. All 3,452 apartment records have values for these fields. Survey values may include EIA imputations. No valid extreme-consumption records were removed. Exact building apartment counts are still unavailable: this experiment does not distinguish a 5-apartment building from a 100-apartment building on that attribute.

## Fair comparison and model selection

- Reused the prior household IDs: **2,071 development apartments**, **691 validation apartments**, **690 evaluation apartments**.
- The prior experiment's calibration partition is repurposed for validation here. It is not used to claim a calibrated prediction interval.
- Trained five XGBoost feature sets: core, each new field individually, and all three together. Four fixed settings each; **20 fits total**. Settings are in `protocol-before-training.json` and every validation result is saved.
- Primary selection metric: **unweighted validation MAE**. The all-three variant was also best on validation (MAE 2,417 kWh/year). No tuning or feature selection followed inspection of evaluation results; no refit on validation.
- One-hot categorical preprocessing and XGBoost were fitted on development apartments only and saved together. Numeric values pass through. Predictions are clipped at zero consistently.
- Predictions were saved before evaluation KWH was joined. An explicit input allowlist and a poisoned-target check verify that the answer cannot enter inference. Saved-pipeline reload reproduces predictions.
- The current app's method is represented by its existing historical annual diagnostic: pre-2020 state forecasts and development-only RECS profile adjustments. Its 31 unsupported evaluation apartments remain documented, not silently dropped. Paired comparisons use the **same 659 supported apartments**; full-cohort scores are also below.

## Results on the same 659 apartments

{table(b,["current_method","regional_median","core","bedrooms","building_age","heating_fuel","all_three"])}

**Controlled input comparison:** core XGBoost → all-three XGBoost raises R² from {core.r2:.3f} to {allthree.r2:.3f} and lowers MAE by {summary['all_three_mae_improvement_over_core_pct']:.2f}%. Relative to the current household method, MAE falls by {summary['all_three_mae_improvement_over_current_pct']:.2f}%. The latter comparison changes both method and features; it does not isolate the effect of the extra questions.

Heating fuel supplies most of the improvement. Bedrooms alone help a little. Building age alone does not improve this run. Because the experiment did not include a bedrooms-plus-heating-only model, it cannot isolate the added value of age after those two are included.

The prespecified exploratory success rule required at least 10% lower paired MAE than core XGBoost and higher R². The actual reduction is **{summary['all_three_mae_improvement_over_core_pct']:.4f}%**, so it narrowly misses that exact threshold; rounding to about 10% must not be presented as passing it. This threshold was a project decision, not a universal definition of accuracy.

## Apartment categories and coverage

{subgroup}

On **all 690 evaluation apartments**, core XGBoost has R² {full.loc['core','r2']:.3f}, MAE {full.loc['core','mae_kwh']:,.0f}; all three has R² {full.loc['all_three','r2']:.3f}, MAE {full.loc['all_three','mae_kwh']:,.0f}. Thus the improvement does not depend on retaining only the current method's supported rows.

Regional paired results for the all-three model vary: R² is about 0.093 in the Northeast, 0.271 in the Midwest, 0.240 in the South and 0.321 in the West. See `subgroup-metrics.csv` for every regional result and sample size. The overall number must not be used to claim equal accuracy everywhere.

## Weights, uncertainty and limits

The primary training and evaluation give each sampled apartment equal weight. Using RECS `NWEIGHT` for evaluation as a sensitivity check yields core R² {weighted.loc['core','r2']:.3f}, MAE {weighted.loc['core','mae_kwh']:,.0f}; all-three R² {weighted.loc['all_three','r2']:.3f}, MAE {weighted.loc['all_three','mae_kwh']:,.0f}. No replicate-weight population confidence intervals were computed. These are not precise national estimates of the model's error.

Only {allthree.within_20_pct:.1f}% of paired all-three predictions fall within ±20% of the recorded annual value. MAE around {allthree.mae_kwh:,.0f} kWh/year is a typical absolute error across the sample, **not an error bound for a particular apartment**. No new prediction interval is claimed.

These RECS records and the earlier evaluation scores were examined in previous project work. This is a controlled historical diagnostic, not a fresh independent external test. RECS annualized/imputed 2020 consumption is the reference, not continuous present-day meter readings. These annual household results cannot validate a future monthly estimate, an adjustment to a state forecast, or the statewide forecast R² around 0.99. The direct annual XGBoost model is a separate experiment and has not been connected to the live monthly application.

## Recommendation

Keep the current app unchanged while reviewing these results. Heating fuel is the strongest candidate if adding only one question. Adding all three improves historical prediction, but the remaining error is substantial. Any future deployment needs a clearly described annual-to-monthly method and separate validation of that output; do not attach the state model's high R² to an individual apartment estimate.

## Reproduction and files

From the HomePulse project root, using the project's existing environment:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python experiments/apartment-inputs-20261116/run_experiment.py --project . --out experiments/apartment-inputs-20261116/results-reproduction
.venv/bin/python -m pip install --target /tmp/homepulse-apartment-plot-deps -r experiments/apartment-inputs-20261116/requirements-plot.txt
PYTHONPATH=/tmp/homepulse-apartment-plot-deps MPLCONFIGDIR=/tmp/homepulse-mpl .venv/bin/python experiments/apartment-inputs-20261116/make_report.py --results experiments/apartment-inputs-20261116/results-reproduction --report reports/apartment-inputs-20261116-reproduction
```

Requires the RECS raw CSV and preserved results from `experiments/household-validation-20261115/results`, especially split IDs and historical predictions. Use a new output directory; the script refuses to overwrite an existing run. Numerical versions and hashes are recorded in the protocol. Training requires no downloading. Optional figure dependencies are installed into a temporary folder, leaving the app environment unchanged.

- `results/protocol-before-training.json`: frozen choices, input allowlist, hashes, dependency versions.
- `results/validation-candidates.csv`: all 20 validation runs.
- `results/selection-before-evaluation.json`: chosen configurations before scoring.
- `results/evaluation-predictions-before-labels.csv` and `evaluation-predictions-with-labels.csv`: household predictions and reference values.
- `results/metrics.csv`, `subgroup-metrics.csv`: full and paired, unweighted and weighted results.
- `results/*.joblib`: preprocessing plus trained experimental models.
- `results/integrity-checks.json`: unchanged production hashes and leakage/serialization checks.
- `verification.json`: {checked} metric rows independently recomputed using direct error formulas.
- `apartment-input-comparison.png` / `.pdf`: comparative results figure.

Data source: [EIA RECS 2020 microdata and codebook](https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata).
"""
    (r/"apartment-input-report.md").write_text(text)
    print(json.dumps(verification))


if __name__=="__main__":
    main()
