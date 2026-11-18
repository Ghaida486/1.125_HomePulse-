import hashlib
import json
import math
from datetime import datetime, timezone
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor
from .config import ROOT, MODEL, REPORTS, FEATURES, NUMERIC, CATEGORIES, TARGET, SEED, RAW
from .data import load_data


def partition(df):
    def split(frame, fraction):
        strata = frame.TYPEHUQ + " / " + frame.REGIONC
        return train_test_split(frame, test_size=fraction, random_state=SEED, stratify=strata)
    development, test = split(df, .2)
    fitting, calibration = split(development, .125)
    train, validation = split(fitting, 1 / 7)
    parts = {"train": train, "validation": validation, "calibration": calibration, "test": test}
    sets = [set(p.DOEID) for p in parts.values()]
    assert sum(map(len, sets)) == len(set.union(*sets)) == len(df)
    return parts


def make_pipeline(settings):
    transform = ColumnTransformer([
        ("numeric", SimpleImputer(strategy="median"), list(NUMERIC)),
        ("category", Pipeline([
            ("missing", SimpleImputer(strategy="constant", fill_value="Unknown")),
            ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), list(CATEGORIES)),
    ])
    model = XGBRegressor(objective="reg:squarederror", tree_method="hist", n_jobs=2,
                         random_state=SEED, subsample=.9, colsample_bytree=.9, **settings)
    return Pipeline([("preprocess", transform), ("model", model)])


def metrics(y, prediction, weights=None):
    return {"mae_kwh": float(mean_absolute_error(y, prediction, sample_weight=weights)),
            "rmse_kwh": float(np.sqrt(mean_squared_error(y, prediction, sample_weight=weights))),
            "r2": float(r2_score(y, prediction, sample_weight=weights))}


def conformal_radius(residuals, coverage=.8):
    residuals = np.asarray(residuals)
    if len(residuals) == 0:
        raise ValueError("Calibration records required")
    rank = min(len(residuals), math.ceil((len(residuals) + 1) * coverage))
    return float(np.sort(residuals)[rank - 1])


def train():
    if MODEL.exists():
        raise FileExistsError("A model already exists. Preserve this experiment and its test results before starting a new run.")
    df = load_data()
    parts = partition(df)
    REPORTS.mkdir(exist_ok=True)
    MODEL.parent.mkdir(exist_ok=True)
    manifest = pd.concat([p[["DOEID"]].assign(split=name) for name, p in parts.items()])
    manifest.sort_values("DOEID").to_csv(REPORTS / "split-manifest.csv", index=False)
    fitting, valid = parts["train"], parts["validation"]
    candidates = [dict(n_estimators=300, max_depth=3, learning_rate=.05),
                  dict(n_estimators=450, max_depth=4, learning_rate=.05),
                  dict(n_estimators=350, max_depth=5, learning_rate=.05)]
    scores = []
    for settings in candidates:
        pipe = make_pipeline(settings)
        pipe.fit(fitting[FEATURES], fitting[TARGET])
        prediction = np.maximum(0, pipe.predict(valid[FEATURES]))
        score = mean_absolute_error(valid[TARGET], prediction)
        scores.append({**settings, "validation_mae_kwh": float(score)})
        print("Validation:", scores[-1], flush=True)
    choice = int(np.argmin([v["validation_mae_kwh"] for v in scores]))
    pipe = make_pipeline(candidates[choice])
    final_fit = pd.concat([fitting, valid])
    pipe.fit(final_fit[FEATURES], final_fit[TARGET])
    baseline = DummyRegressor(strategy="median").fit(final_fit[FEATURES], final_fit[TARGET])
    calibration, test = parts["calibration"], parts["test"]
    calibration_predictions = np.maximum(0, pipe.predict(calibration[FEATURES]))
    radius = conformal_radius(np.abs(calibration[TARGET] - calibration_predictions))
    # Test targets first enter model evaluation here, after settings and radius are fixed.
    pred = np.maximum(0, pipe.predict(test[FEATURES]))
    base = baseline.predict(test[FEATURES])
    model_scores, baseline_scores = metrics(test[TARGET], pred), metrics(test[TARGET], base)
    improvement = 1 - model_scores["mae_kwh"] / baseline_scores["mae_kwh"]
    lower, upper = np.maximum(0, pred - radius), pred + radius
    covered = (test[TARGET].to_numpy() >= lower) & (test[TARGET].to_numpy() <= upper)
    scored = test[["DOEID", "TYPEHUQ", "REGIONC", TARGET, "NWEIGHT"]].copy()
    scored["prediction_kwh"], scored["baseline_kwh"] = pred, base
    scored["lower_80_kwh"], scored["upper_80_kwh"], scored["covered"] = lower, upper, covered
    scored.to_csv(REPORTS / "test-predictions.csv", index=False)
    groups = []
    for field in ["TYPEHUQ", "REGIONC"]:
        for label, g in scored.groupby(field):
            m = metrics(g[TARGET], g.prediction_kwh)
            b = metrics(g[TARGET], g.baseline_kwh)
            groups.append({"dimension": field, "group": label, "n": len(g), **m,
                           "baseline_mae_kwh": b["mae_kwh"], "mae_improvement": 1 - m["mae_kwh"] / b["mae_kwh"],
                           "interval_coverage": float(g.covered.mean()), "low_support": len(g) < 50})
    pd.DataFrame(groups).to_csv(REPORTS / "subgroup-errors.csv", index=False)
    # Explanations use validation records, never choose features using final test importance.
    importance = permutation_importance(pipe, valid[FEATURES], valid[TARGET], scoring="neg_mean_absolute_error", n_repeats=3, random_state=SEED, n_jobs=1)
    pd.DataFrame({"feature": FEATURES, "importance_kwh": importance.importances_mean,
                  "std_kwh": importance.importances_std}).sort_values("importance_kwh", ascending=False).to_csv(REPORTS / "feature-importance.csv", index=False)
    result = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "source_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
        "split_counts": {k: len(v) for k, v in parts.items()}, "seed": SEED, "features": FEATURES,
        "candidate_settings": scores, "selected_settings": candidates[choice],
        "baseline": baseline_scores, "xgboost": model_scores,
        "weighted_baseline": metrics(test[TARGET], base, test.NWEIGHT),
        "weighted_xgboost": metrics(test[TARGET], pred, test.NWEIGHT),
        "mae_improvement": improvement, "provisional_improvement_target": .15,
        "target_met": bool(improvement >= .15), "nominal_coverage": .8,
        "test_interval_coverage": float(covered.mean()), "mean_interval_width_kwh": float(np.mean(upper - lower)),
        "interval_radius_kwh": radius,
        "importance_note": "Permutation importance computed on refit development records; descriptive, not independent or causal evidence.",
    }
    bundle = {"pipeline": pipe, "radius": radius, "features": FEATURES, "metrics": result,
              "ranges": {c: [float(final_fit[c].min()), float(final_fit[c].max())] for c in NUMERIC}}
    joblib.dump(bundle, MODEL)
    (REPORTS / "model-results.json").write_text(json.dumps(result, indent=2))
    return result
