"""Reproducible EIA state forecast feasibility test. Never imports the live app."""
from pathlib import Path
import hashlib
import json
import sqlite3
import sys
import importlib.metadata
import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results"
PLAN = json.loads((ROOT / "experiment-plan.json").read_text())
STATES = "AK AL AR AZ CA CO CT DC DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY".split()
LAGS = [3, 4, 5, 6, 12, 13, 14, 15, 24, 36]

def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def prepare():
    p = ROOT / "raw/eia_monthly_state_sales.xlsx"
    raw = pd.read_excel(p, sheet_name="Monthly-States", header=None)
    assert raw.iloc[0, 4] == "RESIDENTIAL"
    assert raw.iloc[1, 5] == "Sales" and raw.iloc[2, 5] == "Megawatthours"
    body = raw.iloc[3:].copy()
    notes = body.loc[~body[2].isin(STATES)]
    assert len(notes) == 1 and notes[2].isna().all(), "Unexpected rows outside state table"
    d = body.loc[body[2].isin(STATES), [0, 1, 2, 3, 5]].copy()
    d.columns = ["year", "month", "state", "source_status", "sales_mwh"]
    for c in ["year", "month", "sales_mwh"]:
        d[c] = pd.to_numeric(d[c], errors="raise")
    d["date"] = pd.to_datetime(dict(year=d.year, month=d.month, day=1))
    d = d.sort_values(["state", "date"]).reset_index(drop=True)
    assert len(d) == 10200 and set(d.state) == set(STATES)
    assert not d.duplicated(["state", "date"]).any()
    assert d.notna().all().all() and (d.sales_mwh > 0).all()
    expected = pd.date_range("2010-01-01", "2026-08-01", freq="MS")
    for state, g in d.groupby("state"):
        assert list(g.date) == list(expected), state
    d.to_csv(OUT / "monthly-residential-sales.csv", index=False)
    with sqlite3.connect(OUT / "state-electricity.sqlite") as con:
        d.to_sql("monthly_residential_sales", con, index=False, if_exists="replace")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS state_month ON monthly_residential_sales(state,date)")
    dump(OUT / "data-audit.json", {
        "source_sha256": sha(p), "source_url": PLAN["source_download"],
        "source_sheet": "Monthly-States", "source_sales_column": "F",
        "first_month": "2010-01", "last_month": "2026-08", "states_including_dc": 51,
        "months_per_state": 200, "records": len(d), "missing_cells": 0,
        "duplicate_state_months": 0, "missing_state_months": 0,
        "source_status_counts": d.source_status.value_counts().to_dict(),
        "excluded_rows": "Three header rows and one explanatory footer; no observation rows removed",
        "units": "MWh", "missing_or_outlier_imputation": "None",
        "workbook_footer": str(notes.iloc[0, 0])
    })
    return d

def features(d):
    frames = []
    for state, src in d.groupby("state", sort=True):
        g = src.sort_values("date").copy()
        y = g.sales_mwh
        for k in LAGS:
            g[f"lag_{k}"] = y.shift(k)
        g["recent_mean"] = y.shift(3).rolling(12).mean()
        g["prior_mean"] = y.shift(15).rolling(12).mean()
        g["recent_std_ratio"] = y.shift(3).rolling(12).std() / g.recent_mean
        for k in LAGS:
            g[f"relative_lag_{k}"] = g[f"lag_{k}"] / g.recent_mean
        g["annual_growth"] = g.recent_mean / g.prior_mean
        g["recent_3_growth"] = y.shift(3).rolling(3).mean() / y.shift(15).rolling(3).mean()
        g["log_recent_mean"] = np.log(g.recent_mean)
        g["days"] = g.date.dt.days_in_month
        g["month_sin"] = np.sin(2 * np.pi * g.month / 12)
        g["month_cos"] = np.cos(2 * np.pi * g.month / 12)
        g["latest_observation_month"] = g.date - pd.DateOffset(months=3)
        g["same_month_last_year"] = g.lag_12
        g["same_month_three_year_mean"] = (g.lag_12 + g.lag_24 + g.lag_36) / 3
        g["recent_growth_adjusted_last_year"] = g.lag_12 * g.annual_growth.clip(.8, 1.2)
        frames.append(g)
    f = pd.concat(frames).sort_values(["date", "state"]).reset_index(drop=True)
    f = f.loc[f.date >= "2013-01-01"].copy()
    cols = ["state", "month", "year", "days", "month_sin", "month_cos", "log_recent_mean",
            "recent_std_ratio", "annual_growth", "recent_3_growth"] + [f"relative_lag_{k}" for k in LAGS]
    assert f[cols + ["sales_mwh"]].notna().all().all()
    return f, cols

def period(f, key):
    start, end = PLAN[key]
    return f.loc[f.date.between(pd.Timestamp(start), pd.Timestamp(end))].copy()

def metric_rows(df, prediction, model, split):
    p = np.asarray(prediction, dtype=float)
    y = df.sales_mwh.to_numpy(dtype=float)
    by_state = []
    temp = df[["date", "state", "sales_mwh"]].copy()
    temp["prediction_mwh"] = p
    for st, g in temp.groupby("state"):
        actual, pred = g.sales_mwh, g.prediction_mwh
        by_state.append(dict(model=model, split=split, state=st, n=len(g),
            r2=float(r2_score(actual, pred)), mae_mwh=float(mean_absolute_error(actual, pred)),
            rmse_mwh=float(np.sqrt(mean_squared_error(actual, pred))),
            wape=float(np.abs(actual - pred).sum() / actual.sum())))
    per = pd.DataFrame(by_state)
    pooled = dict(model=model, split=split, n=len(df),
        pooled_r2=float(r2_score(y, p)), mae_mwh=float(mean_absolute_error(y, p)),
        rmse_mwh=float(np.sqrt(mean_squared_error(y, p))), wape=float(np.abs(y-p).sum()/y.sum()),
        mean_state_wape=float(per.wape.mean()), median_state_r2=float(per.r2.median()),
        mean_state_r2=float(per.r2.mean()), states_r2_at_least_09=int((per.r2 >= .9).sum()),
        worst_state_r2=float(per.r2.min()))
    return pooled, per

def fit(df, cols, mode, settings):
    prep = ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["state", "month"]),
        ("numerical", "passthrough", [c for c in cols if c not in ["state", "month"]])
    ])
    pipe = Pipeline([("prepare", prep), ("regressor", XGBRegressor(**PLAN["common_settings"], **settings))])
    denominator = df.lag_12 if mode == "log_ratio_to_last_year" else df.recent_mean
    target = np.log(df.sales_mwh / denominator)
    pipe.fit(df[cols], target)
    return dict(pipeline=pipe, mode=mode, columns=cols, horizon_months=3)

def predict(bundle, df):
    base = df.lag_12 if bundle["mode"] == "log_ratio_to_last_year" else df.recent_mean
    return np.asarray(base) * np.exp(bundle["pipeline"].predict(df[bundle["columns"]]))

def main():
    OUT.mkdir(exist_ok=True)
    if (OUT / "test-predictions.csv").exists():
        raise RuntimeError("Completed test already exists. Do not silently overwrite an inspected evaluation.")
    dump(OUT / "run-manifest.json", {
        "plan_sha256": sha(ROOT / "experiment-plan.json"),
        "script_sha256": sha(__file__), "source_sha256": sha(ROOT / "raw/eia_monthly_state_sales.xlsx"),
        "python": sys.version, "packages": {x: importlib.metadata.version(x) for x in ["pandas", "numpy", "scikit-learn", "xgboost", "joblib"]}
    })
    d = prepare()
    f, cols = features(d)
    f.to_csv(OUT / "features.csv", index=False)
    train, val, refit, test = [period(f, k) for k in ["training_targets", "validation_targets", "refit_targets", "test_targets"]]
    assert train.date.max() < val.latest_observation_month.min()
    assert val.date.max() < test.latest_observation_month.min()
    assert refit.date.max() < test.latest_observation_month.min()
    for label, frame in [("train", train), ("validation", val), ("refit", refit), ("test", test)]:
        print(label, len(frame), str(frame.date.min())[:10], str(frame.date.max())[:10], flush=True)
    comparison, state_scores = [], []
    valpred = val[["date", "state", "sales_mwh", "latest_observation_month"]].copy()
    for name in PLAN["baseline_models"]:
        vals, per = metric_rows(val, val[name], name, "validation")
        comparison.append(vals); state_scores.append(per); valpred[name] = val[name].values
    candidates = {}
    for mode in PLAN["xgboost_targets"]:
        for settings in PLAN["xgboost_settings"]:
            name = f"xgb_{mode}_depth{settings['max_depth']}"
            bundle = fit(train, cols, mode, settings)
            p = predict(bundle, val)
            vals, per = metric_rows(val, p, name, "validation")
            comparison.append(vals); state_scores.append(per); valpred[name] = p
            candidates[name] = (mode, settings)
            print(name, json.dumps(vals), flush=True)
    board = pd.DataFrame(comparison)
    board.to_csv(OUT / "validation-comparison.csv", index=False)
    pd.concat(state_scores).to_csv(OUT / "validation-state-metrics.csv", index=False)
    valpred.to_csv(OUT / "validation-predictions.csv", index=False)
    winner = board.loc[board.model.isin(candidates)].sort_values(["mean_state_wape", "model"]).iloc[0].model
    best_baseline = board.loc[board.model.isin(PLAN["baseline_models"])].sort_values(["mean_state_wape", "model"]).iloc[0].model
    mode, settings = candidates[winner]
    dump(OUT / "selection-before-test.json", {"xgboost": winner, "baseline": best_baseline,
         "criterion": PLAN["selection"], "mode": mode, "settings": settings})
    bundle = fit(refit, cols, mode, settings)
    bundle["training_target_end"] = str(refit.date.max())[:10]
    joblib.dump(bundle, OUT / "selected-backtest-model.joblib")
    predictions = test[["date", "state", "sales_mwh", "source_status", "latest_observation_month"]].copy()
    predictions["xgboost"] = predict(bundle, test)
    all_scores, per_scores = [], []
    for name in ["xgboost"] + PLAN["baseline_models"]:
        if name != "xgboost":
            predictions[name] = test[name].values
        summary, per = metric_rows(test, predictions[name], name, "test")
        all_scores.append(summary); per_scores.append(per)
    predictions.to_csv(OUT / "test-predictions.csv", index=False)
    pd.DataFrame(all_scores).to_csv(OUT / "test-comparison.csv", index=False)
    per = pd.concat(per_scores)
    per.to_csv(OUT / "test-state-metrics.csv", index=False)
    x = per.loc[per.model == "xgboost"].set_index("state")
    b = per.loc[per.model == best_baseline].set_index("state")
    comp = x[["r2", "mae_mwh", "rmse_mwh", "wape"]].add_prefix("xgb_").join(b[["r2", "mae_mwh", "rmse_mwh", "wape"]].add_prefix("baseline_"))
    comp["mae_improvement_pct"] = 100 * (1 - comp.xgb_mae_mwh / comp.baseline_mae_mwh)
    comp.to_csv(OUT / "state-skill.csv")
    totals = pd.DataFrame(all_scores).set_index("model")
    result = dict(selected_xgboost=winner, validation_selected_baseline=best_baseline,
        xgboost=totals.loc["xgboost"].to_dict(), baseline=totals.loc[best_baseline].to_dict(),
        states_with_lower_mae_than_baseline=int((comp.mae_improvement_pct > 0).sum()),
        mean_state_wape_improvement_pct=float(100 * (1-totals.loc["xgboost", "mean_state_wape"] / totals.loc[best_baseline, "mean_state_wape"])),
        pooled_mae_improvement_pct=float(100 * (1-totals.loc["xgboost", "mae_mwh"] / totals.loc[best_baseline, "mae_mwh"])),
        production_app_modified=False)
    dump(OUT / "summary.json", result)
    print("FINAL", json.dumps(result), flush=True)

if __name__ == "__main__":
    main()
