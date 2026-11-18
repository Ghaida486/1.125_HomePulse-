"""Bounded state/profile experiment; original app artifacts are never overwritten."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

from .config import ROOT, RAW, CODEBOOK, REPORTS as ORIGINAL_REPORTS, MODEL as ORIGINAL_MODEL, DATABASE as ORIGINAL_DATABASE
from .practical import FEATURES, USER_FIELDS, EXTRA_FIELDS, NUMERIC, MODEL, DATABASE, REPORTS, clean_practical_records
from .training import partition, metrics, conformal_radius

SETTINGS = [
    dict(n_estimators=300, max_depth=3, learning_rate=.05),
    dict(n_estimators=700, max_depth=3, learning_rate=.03, min_child_weight=10, reg_lambda=10),
    dict(n_estimators=600, max_depth=4, learning_rate=.03, min_child_weight=10, reg_lambda=10),
    dict(n_estimators=500, max_depth=6, learning_rate=.03, min_child_weight=20, reg_lambda=20),
]
GROUPS = {
    "core_with_state": [f for f in FEATURES if f not in EXTRA_FIELDS],
    "practical_without_state": [f for f in FEATURES if f != "state_postal"],
    "practical_with_state": FEATURES,
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name, value):
    (REPORTS / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def make_pipeline(fields, settings):
    numbers = [f for f in fields if f in NUMERIC]
    categories = [f for f in fields if f not in NUMERIC]
    prep = ColumnTransformer([
        ("numeric", SimpleImputer(strategy="median", add_indicator=True), numbers),
        ("category", Pipeline([
            ("missing", SimpleImputer(strategy="constant", fill_value="Unknown")),
            ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), categories),
    ])
    return Pipeline([("preprocess", prep), ("model", XGBRegressor(
        objective="reg:squarederror", tree_method="hist", n_jobs=2, random_state=42,
        subsample=.9, colsample_bytree=.9, **settings))])


def train_practical():
    if MODEL.exists() or REPORTS.exists() or DATABASE.exists():
        raise FileExistsError("State-model outputs already exist. Preserve this run before starting another experiment.")
    REPORTS.mkdir(parents=True)
    MODEL.parent.mkdir(exist_ok=True)
    protected = [ORIGINAL_MODEL, ORIGINAL_DATABASE, ORIGINAL_REPORTS / "model-results.json",
                 ORIGINAL_REPORTS / "test-predictions.csv", ORIGINAL_REPORTS / "split-manifest.csv"]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    plan = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "question": "Does state plus 17 answerable household details improve annual KWH prediction?",
        "source_sha256": sha(RAW), "codebook_sha256": sha(CODEBOOK),
        "predictors": FEATURES, "user_questions": USER_FIELDS, "groups": GROUPS,
        "settings": SETTINGS, "fits": 12,
        "selection": "Among practical_with_state candidates, lowest validation RMSE with validation MAE <= original model validation MAE. If none, choose lowest RMSE but do not activate in the app.",
        "ablation": "Same four settings on core+state and practical-without-state; report validation scores only. State is categorical; region is derived automatically.",
        "activation": "Validation MAE guardrail, then lower R2 loss (higher R2) and lower MAE than original on the same existing benchmark. No retuning after benchmark inspection.",
        "cohort": "Same households, same split memberships and original row ordering; no new resplit, no trimming high users.",
        "evaluation": "Select on validation, freeze settings, refit on train+validation, calibrate on calibration, evaluate existing test once. This test has been inspected in previous experiments and is a reused benchmark, not fresh external evidence.",
        "features_excluded": "Climate-zone question, observed annual weather, bills, energy components, IDs, survey weights and imputation flags.",
        "protected_hashes": hashes,
    }
    write_json("experiment-plan.json", plan)
    raw = pd.read_csv(RAW, low_memory=False)
    clean = clean_practical_records(raw).sort_values("DOEID").reset_index(drop=True)
    book = pd.read_excel(CODEBOOK, sheet_name="codebook", header=1).fillna("")
    dictionary = book[book.Variable.isin([*FEATURES, "KWH", "NWEIGHT"])].copy()
    dictionary.to_csv(REPORTS / "input-codebook.csv", index=False)
    with sqlite3.connect(DATABASE) as conn:
        clean.to_sql("households", conn, index=False)
        conn.execute("CREATE UNIQUE INDEX household_id ON households(DOEID)")
        dictionary.to_sql("input_dictionary", conn, index=False)
        pd.DataFrame([{"key": "source_sha256", "value": plan["source_sha256"]},
                      {"key": "model_inputs", "value": json.dumps(FEATURES)},
                      {"key": "data_year", "value": "2020"}]).to_sql("dataset_metadata", conn, index=False)
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        data = pd.read_sql_query("SELECT * FROM households ORDER BY DOEID", conn)
    write_json("cleaning-audit.json", {
        "raw_rows": len(raw), "clean_rows": len(data), "removed_rows": len(raw) - len(data),
        "model_columns": len(FEATURES), "user_questions": len(USER_FIELDS),
        "missing": data[FEATURES].isna().sum().to_dict(),
        "state_count": int(data.state_postal.nunique()),
        "rules": ["State validated against official state dictionary; region derived from state and checked against source.",
                  "Dryer -2 maps to no dryer and zero loads; pool -2 maps to no private pool.",
                  "Thermostat -2 becomes missing; numerical imputation learned only during fitting.",
                  "All valid high-use households retained; no energy or expenditure predictor columns.",
                  "BA_climate retained as descriptive database context only, not used in model or form."],
    })
    parts = partition(data)
    manifest = pd.read_csv(ORIGINAL_REPORTS / "split-manifest.csv")
    assert data.DOEID.is_unique
    for label, frame in parts.items():
        assert set(frame.DOEID) == set(manifest.loc[manifest.split == label, "DOEID"])
    manifest.to_csv(REPORTS / "split-manifest.csv", index=False)
    train, val = parts["train"], parts["validation"]
    old = json.loads((ORIGINAL_REPORTS / "model-results.json").read_text())
    guardrail = min(x["validation_mae_kwh"] for x in old["candidate_settings"])
    candidates, fitted = [], {}
    for group, fields in GROUPS.items():
        for index, settings in enumerate(SETTINGS):
            pipe = make_pipeline(fields, settings)
            pipe.fit(train[fields], train.KWH)
            record = {"group": group, "configuration": index, "settings": settings,
                      "validation": metrics(val.KWH, np.maximum(0, pipe.predict(val[fields]))),
                      "training": metrics(train.KWH, np.maximum(0, pipe.predict(train[fields])))}
            candidates.append(record)
            fitted[(group, index)] = pipe
            write_json("candidate-results.json", candidates)
            print(json.dumps(record), flush=True)
    eligible = [r for r in candidates if r["group"] == "practical_with_state" and r["validation"]["mae_kwh"] <= guardrail]
    best = min(eligible or [r for r in candidates if r["group"] == "practical_with_state"], key=lambda r: r["validation"]["rmse_kwh"])
    write_json("frozen-selection.json", {"selected": best, "validation_guardrail_passed": bool(eligible),
                                         "frozen_utc": datetime.now(timezone.utc).isoformat()})
    frozen_hash = sha(REPORTS / "frozen-selection.json")
    # Importance is measured on validation BEFORE refitting on those records.
    selected = fitted[(best["group"], best["configuration"])]
    importance = permutation_importance(selected, val[FEATURES], val.KWH, scoring="neg_mean_absolute_error",
                                        n_repeats=3, random_state=42, n_jobs=1)
    pd.DataFrame({"feature": FEATURES, "importance_kwh": importance.importances_mean,
                  "std_kwh": importance.importances_std}).to_csv(REPORTS / "feature-importance.csv", index=False)
    pipe = make_pipeline(FEATURES, best["settings"])
    development = pd.concat([train, val])
    pipe.fit(development[FEATURES], development.KWH)
    calibration, test = parts["calibration"], parts["test"]
    radius = conformal_radius(np.abs(calibration.KWH.to_numpy() - np.maximum(0, pipe.predict(calibration[FEATURES]))))
    prediction = np.maximum(0, pipe.predict(test[FEATURES]))
    baseline = np.full(len(test), float(development.KWH.median()))
    original = pd.read_csv(ORIGINAL_REPORTS / "test-predictions.csv").set_index("DOEID").loc[test.DOEID]
    assert np.allclose(original.KWH, test.KWH)
    original_metrics = metrics(test.KWH, original.prediction_kwh)
    new_metrics = metrics(test.KWH, prediction)
    baseline_metrics = metrics(test.KWH, baseline)
    lower, upper = np.maximum(0, prediction - radius), prediction + radius
    covered = (test.KWH.to_numpy() >= lower) & (test.KWH.to_numpy() <= upper)
    scored = test[["DOEID", "state_postal", "TYPEHUQ", "REGIONC", "KWH", "NWEIGHT"]].copy()
    scored["prediction_kwh"], scored["original_kwh"], scored["baseline_kwh"] = prediction, original.prediction_kwh.to_numpy(), baseline
    scored["lower_80_kwh"], scored["upper_80_kwh"], scored["covered"] = lower, upper, covered
    scored.to_csv(REPORTS / "test-predictions.csv", index=False)
    groups = []
    for field in ["TYPEHUQ", "REGIONC", "state_postal"]:
        for name, g in scored.groupby(field):
            m, b = metrics(g.KWH, g.prediction_kwh), metrics(g.KWH, g.baseline_kwh)
            groups.append({"dimension": field, "group": name, "n": len(g), **m,
                           "baseline_mae_kwh": b["mae_kwh"], "mae_improvement": 1 - m["mae_kwh"] / b["mae_kwh"],
                           "interval_coverage": float(g.covered.mean()), "low_support": len(g) < 50})
    pd.DataFrame(groups).to_csv(REPORTS / "subgroup-errors.csv", index=False)
    by_group = {g: min((r for r in candidates if r["group"] == g), key=lambda r: r["validation"]["rmse_kwh"]) for g in GROUPS}
    improvement = 1 - new_metrics["mae_kwh"] / baseline_metrics["mae_kwh"]
    result = {"model_version": "practical-state-v1", "created_utc": datetime.now(timezone.utc).isoformat(),
              "features": FEATURES, "user_questions": USER_FIELDS, "split_counts": {k: len(v) for k, v in parts.items()},
              "selected_settings": best["settings"], "selected_validation": best["validation"], "validation_ablation": by_group,
              "original": original_metrics, "xgboost": new_metrics, "baseline": baseline_metrics,
              "weighted_xgboost": metrics(test.KWH, prediction, test.NWEIGHT),
              "mae_improvement": improvement, "mae_improvement_vs_original": 1 - new_metrics["mae_kwh"] / original_metrics["mae_kwh"],
              "target_met": improvement >= .15, "nominal_coverage": .8, "test_interval_coverage": float(covered.mean()),
              "interval_radius_kwh": radius, "source_sha256": plan["source_sha256"], "frozen_selection_sha256": frozen_hash,
              "activate_in_app": bool(eligible and new_metrics["r2"] > original_metrics["r2"] and new_metrics["mae_kwh"] < original_metrics["mae_kwh"]),
              "evaluation_note": plan["evaluation"],
              "limitations": ["Test and validation reused from earlier development; not fresh independent confirmation.",
                              "Annual household estimate from 2020 records, not current-year or future-year validated accuracy.",
                              "Not-sure answers are supported through missing-value preprocessing, but are not separately calibrated.",
                              "Original 2015 validation does not validate this revised model."]}
    bundle = {"pipeline": pipe, "features": FEATURES, "radius": radius, "metrics": result, "schema_version": "practical-state-v1"}
    joblib.dump(bundle, MODEL)
    restored = joblib.load(MODEL)
    assert np.allclose(np.maximum(0, restored["pipeline"].predict(test[FEATURES])), prediction)
    assert sha(REPORTS / "frozen-selection.json") == frozen_hash
    for path in protected:
        assert sha(path) == hashes[str(path.relative_to(ROOT))], path
    write_json("model-results.json", result)
    summary = ["HomePulse — practical household inputs + state", "",
               f"Original 11-input model: R² {original_metrics['r2']:.4f}; MAE {original_metrics['mae_kwh']:,.0f} kWh/year.",
               f"New 17-question model: R² {new_metrics['r2']:.4f}; MAE {new_metrics['mae_kwh']:,.0f} kWh/year.",
               f"MAE reduction vs original: {result['mae_improvement_vs_original']:.1%}.",
               f"Same {len(test):,} test households, all valid high-use records retained.",
               f"80% nominal interval observed coverage: {covered.mean():.1%}.", "",
               "Validation comparisons (model selection data, not independent test results):"]
    for name, r in by_group.items():
        summary.append(f"{name}: R² {r['validation']['r2']:.4f}; MAE {r['validation']['mae_kwh']:,.0f}.")
    summary += ["", "One national model with state as an input; not 51 separate state models.",
                "17 user fields + automatically derived region = 18 model inputs.",
                "Original app artifacts and prior 2015 results remain unchanged.",
                "The app can use this model only if activate_in_app is true.", "", *result["limitations"], ""]
    (REPORTS / "summary.txt").write_text("\n".join(summary))
    print(json.dumps(result, indent=2), flush=True)
    return result


if __name__ == "__main__":
    train_practical()
