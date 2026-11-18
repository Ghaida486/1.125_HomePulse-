"""Render every saved state-month test prediction; never train or filter results."""
from pathlib import Path
import argparse
import hashlib
import json
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    database = args.project / "data/homepulse_monthly.sqlite"
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as con:
        rows = pd.read_sql_query("SELECT * FROM test_predictions ORDER BY state,date", con)
        manifest = json.loads(con.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])
    assert len(rows) == 1632 and rows.state.nunique() == 51
    assert not rows.duplicated(["state", "date"]).any()
    assert rows.groupby("state").size().eq(32).all()
    actual = rows.sales_mwh.to_numpy(float)
    predicted = rows.xgboost.to_numpy(float)
    baseline = rows.same_month_three_year_mean.to_numpy(float)
    assert np.isfinite(np.column_stack([actual, predicted, baseline])).all()
    def score(values):
        return {"r2": float(1 - np.square(values-actual).sum()/np.square(actual-actual.mean()).sum()),
                "mae_mwh": float(np.abs(values-actual).mean()),
                "wape": float(np.abs(values-actual).sum()/actual.sum())}
    result = score(predicted)
    reference = score(baseline)
    assert abs(result["r2"]-manifest["historical_test"]["xgboost"]["pooled_r2"]) < 1e-12
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12,
                         "text.color": "#143247", "axes.labelcolor": "#143247"})
    fig, ax = plt.subplots(figsize=(11.8, 8.5), facecolor="white")
    fig.subplots_adjust(left=.11, right=.96, bottom=.21, top=.76)
    fig.text(.06,.95,"HomePulse | Overall XGBoost results",fontsize=23,weight="bold")
    fig.text(.06,.91,"Predicted vs actual monthly residential electricity sales",fontsize=15)
    fig.text(.06,.872,"50 states + Washington, D.C.  |  Jan 2024-Aug 2026",fontsize=12,color="#536F80")
    fig.text(.06,.81,f"Pooled R²  {result['r2']:.3f}     |     Absolute-error rate  {result['wape']:.2%}     |     1,632 test records",fontsize=14,weight="bold")
    dots = ax.scatter(actual/1e6,predicted/1e6,s=23,c="#00868B",alpha=.43,
                      edgecolors="none",label="XGBoost: one state and month",zorder=3)
    limit=max(actual.max(),predicted.max())/1e6*1.045
    ax.plot([0,limit],[0,limit],"--",c="#D44840",lw=2,label="Perfect prediction",zorder=2)
    ax.set(xlim=(0,limit),ylim=(0,limit),xlabel="Actual EIA sales (million MWh)",
           ylabel="XGBoost prediction (million MWh)")
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.yaxis.set_major_locator(MultipleLocator(5))
    ax.grid(color="#E2E9EC",lw=.8,zorder=0)
    ax.spines[["top","right"]].set_visible(False)
    ax.spines[["left","bottom"]].set_color("#A8BAC3")
    ax.legend(loc="upper left",frameon=True,facecolor="white",edgecolor="#E2E9EC",fontsize=11)
    assert len(dots.get_offsets()) == len(rows)
    fig.text(.06,.13,f"Seasonal benchmark: R² {reference['r2']:.3f} | absolute-error rate {reference['wape']:.2%} (better overall).",fontsize=11)
    fig.text(.06,.092,"The pooled score includes differences in state size; it does not measure individual-home accuracy.",fontsize=10.5,color="#536F80")
    fig.text(.06,.057,"Source: EIA-861M. All test rows shown. Predictors use sales dated at least three months earlier.",fontsize=10,color="#536F80")
    fig.text(.06,.026,"Retrospective test using current revised data; historical publication vintages were not reconstructed.",fontsize=9.5,color="#536F80")
    fig.savefig(args.output/"overall-xgboost-predicted-vs-actual.png",dpi=180)
    fig.savefig(args.output/"overall-xgboost-predicted-vs-actual.svg")
    plt.close(fig)
    verification={"source_database":str(database),"database_sha256":hashlib.sha256(database.read_bytes()).hexdigest(),
        "points_plotted":len(rows),"states_including_dc":int(rows.state.nunique()),"months_per_state":32,
        "test_rows_removed":0,"xgboost":result,"seasonal_benchmark":reference,
        "model_retrained":False,"matches_saved_evaluation":True}
    (args.output/"graph-verification.json").write_text(json.dumps(verification,indent=2)+"\n")
    print(json.dumps(verification,indent=2))


if __name__ == "__main__":
    main()
