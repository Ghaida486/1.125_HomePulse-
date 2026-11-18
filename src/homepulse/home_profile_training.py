"""Four prespecified XGBoost candidates for the agreed twelve-question profile."""
import json
import sqlite3
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from . import home_profile as h, practical
from .config import ROOT, RAW, CODEBOOK, REPORTS as ORIGINAL_REPORTS
from .practical_training import make_pipeline, SETTINGS, sha
from .training import partition, metrics, conformal_radius


def train():
    if h.MODEL.exists() or h.DATABASE.exists() or h.REPORTS.exists():
        raise FileExistsError("Preserve this completed experiment before retraining")
    h.REPORTS.mkdir(parents=True)
    h.MODEL.parent.mkdir(exist_ok=True)
    def write(name, value):
        (h.REPORTS / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    protected = [practical.MODEL, practical.DATABASE, practical.REPORTS / "model-results.json",
                 practical.REPORTS / "test-predictions.csv", ORIGINAL_REPORTS / "split-manifest.csv",
                 ROOT / "models/pipeline.joblib", ROOT / "data/homepulse.sqlite"]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    plan = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "question": "How well does XGBoost predict annual 2020 household electricity using the agreed 12 questions without appliances?",
        "user_questions": h.USER_FIELDS, "predictors": h.FEATURES, "removed": sorted(h.REMOVED),
        "data": "RECS 2020 v7 only. 2015 excluded from this run.",
        "source_sha256": sha(RAW), "codebook_sha256": sha(CODEBOOK),
        "settings": SETTINGS, "selection": "Lowest validation RMSE, tie broken by validation MAE; four prespecified candidates only.",
        "fitting": "11,096 train for candidate selection, then 12,946 train+validation for final fit. 1,850 calibration and 3,700 test excluded from fitting.",
        "cohort": "Preserve all 18,496 households and existing split memberships/order; no outcome-based exclusions or resplitting.",
        "evaluation_note": "Same reused 2020 test benchmark, already inspected in earlier development; not fresh independent confirmation. No tuning after this test result.",
        "requested_r2_target": h.REQUESTED_R2_TARGET,
        "activation": "Adopt the user's agreed 12-input scope after functional checks, irrespective of whether it improves over the 17-input model. Report performance honestly.",
        "graph": "Use the same 50 test household IDs as the previous chart, selected before training. Full test metrics shown separately from displayed sample.",
        "protected_hashes": hashes,
    }
    write("experiment-plan.json", plan)
    sample_path = practical.REPORTS / "app-vs-actual-2020-sample.csv"
    if sample_path.exists():
        sample_ids = pd.read_csv(sample_path).DOEID.tolist()
    else:
        previous_manifest = pd.read_csv(ORIGINAL_REPORTS / "split-manifest.csv")
        test_ids = sorted(previous_manifest.loc[previous_manifest.split == "test", "DOEID"])
        sample_ids = pd.Series(test_ids).sample(n=50, random_state=42).tolist()
    write("chart-households.json", {"seed": 42, "DOEID": sample_ids, "selection": "Same fixed random 50-household sample as the previous app graph"})
    raw = pd.read_csv(RAW, low_memory=False)
    clean = h.clean_records(raw).sort_values("DOEID").reset_index(drop=True)
    assert len(clean) == 18496 and clean.DOEID.is_unique
    dictionary = pd.read_excel(CODEBOOK, sheet_name="codebook", header=1).fillna("")
    dictionary = dictionary[dictionary.Variable.isin([*h.FEATURES, "KWH", "NWEIGHT"])]
    dictionary.to_csv(h.REPORTS / "input-codebook.csv", index=False)
    with sqlite3.connect(h.DATABASE) as conn:
        clean.to_sql("households", conn, index=False)
        conn.execute("CREATE UNIQUE INDEX household_id ON households(DOEID)")
        dictionary.to_sql("input_dictionary", conn, index=False)
        pd.DataFrame([{"key": "source_sha256", "value": plan["source_sha256"]},
                      {"key": "model_inputs", "value": json.dumps(h.FEATURES)},
                      {"key": "data_year", "value": "2020"}]).to_sql("dataset_metadata", conn, index=False)
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    data = h.load_data()
    parts = partition(data)
    manifest = pd.read_csv(ORIGINAL_REPORTS / "split-manifest.csv")
    for split, frame in parts.items():
        assert set(frame.DOEID) == set(manifest.loc[manifest.split == split, "DOEID"])
    assert set(sample_ids) <= set(parts["test"].DOEID) and len(sample_ids) == 50
    manifest.to_csv(h.REPORTS / "split-manifest.csv", index=False)
    write("cleaning-audit.json", {"raw_rows": len(raw), "clean_rows": len(data), "removed_rows": 0,
                                 "removed_predictor_columns": sorted(h.REMOVED),
                                 "model_input_columns": len(h.FEATURES), "user_input_count": len(h.USER_FIELDS),
                                 "missing": data[h.FEATURES].isna().sum().to_dict(),
                                 "rules": ["Same official codebook rules and cohort as the previous model.",
                                           "All five appliance fields removed from database and model allowlist.",
                                           "State retained; Census region derived. Thermostat not-applicable codes remain missing.",
                                           "Survey weights used for comparisons/sensitivity metrics, not predictor inputs."]})
    training, validation = parts["train"], parts["validation"]
    candidates, fitted = [], []
    for index, settings in enumerate(SETTINGS):
        pipe = make_pipeline(h.FEATURES, settings)
        pipe.fit(training[h.FEATURES], training.KWH)
        record = {"configuration": index, "settings": settings,
                  "validation": metrics(validation.KWH, np.maximum(0, pipe.predict(validation[h.FEATURES]))),
                  "training": metrics(training.KWH, np.maximum(0, pipe.predict(training[h.FEATURES])))}
        candidates.append(record)
        fitted.append(pipe)
        write("candidate-results.json", candidates)
        print(json.dumps(record), flush=True)
    best = min(candidates, key=lambda r: (r["validation"]["rmse_kwh"], r["validation"]["mae_kwh"]))
    write("frozen-selection.json", {"selected": best, "frozen_utc": datetime.now(timezone.utc).isoformat()})
    frozen_hash = sha(h.REPORTS / "frozen-selection.json")
    importance = permutation_importance(fitted[best["configuration"]], validation[h.FEATURES], validation.KWH,
                                        scoring="neg_mean_absolute_error", n_repeats=3, random_state=42, n_jobs=1)
    pd.DataFrame({"feature": h.FEATURES, "importance_kwh": importance.importances_mean,
                  "std_kwh": importance.importances_std}).to_csv(h.REPORTS / "feature-importance.csv", index=False)
    development = pd.concat([training, validation])
    pipe = make_pipeline(h.FEATURES, best["settings"])
    pipe.fit(development[h.FEATURES], development.KWH)
    assert list(pipe.feature_names_in_) == h.FEATURES
    assert not set(pipe.feature_names_in_) & h.REMOVED
    calibration, test = parts["calibration"], parts["test"]
    radius = conformal_radius(np.abs(calibration.KWH.to_numpy() - np.maximum(0, pipe.predict(calibration[h.FEATURES]))))
    prediction = np.maximum(0, pipe.predict(test[h.FEATURES]))
    baseline = np.full(len(test), float(development.KWH.median()))
    previous = pd.read_csv(practical.REPORTS / "test-predictions.csv").set_index("DOEID").loc[test.DOEID]
    original = pd.read_csv(ORIGINAL_REPORTS / "test-predictions.csv").set_index("DOEID").loc[test.DOEID]
    assert np.allclose(previous.KWH, test.KWH) and np.allclose(original.KWH, test.KWH)
    score, base_score = metrics(test.KWH, prediction), metrics(test.KWH, baseline)
    previous_score = metrics(test.KWH, previous.prediction_kwh)
    lower, upper = np.maximum(0, prediction - radius), prediction + radius
    covered = (test.KWH.to_numpy() >= lower) & (test.KWH.to_numpy() <= upper)
    scored = test[["DOEID", "state_postal", "TYPEHUQ", "REGIONC", "KWH", "NWEIGHT"]].copy()
    scored["prediction_kwh"], scored["previous_17_kwh"], scored["baseline_kwh"] = prediction, previous.prediction_kwh.to_numpy(), baseline
    scored["lower_80_kwh"], scored["upper_80_kwh"], scored["covered"] = lower, upper, covered
    scored.to_csv(h.REPORTS / "test-predictions.csv", index=False)
    paired = scored.set_index("DOEID")[["state_postal", "TYPEHUQ", "KWH", "prediction_kwh"]].rename(
        columns={"KWH": "recorded_2020_kwh", "prediction_kwh": "app_prediction_kwh"})
    paired["residual_kwh"] = paired.app_prediction_kwh - paired.recorded_2020_kwh
    paired.to_csv(h.REPORTS / "app-vs-actual-2020-all.csv")
    sample = paired.loc[sample_ids].copy()
    sample.insert(0, "display_index", np.arange(1, 51))
    sample.to_csv(h.REPORTS / "app-vs-actual-2020-sample.csv")
    groups = []
    for field in ["TYPEHUQ", "REGIONC", "state_postal"]:
        for name, group in scored.groupby(field):
            m, b = metrics(group.KWH, group.prediction_kwh), metrics(group.KWH, group.baseline_kwh)
            groups.append({"dimension": field, "group": name, "n": len(group), **m,
                           "baseline_mae_kwh": b["mae_kwh"], "mae_improvement": 1 - m["mae_kwh"] / b["mae_kwh"],
                           "interval_coverage": float(group.covered.mean()), "low_support": len(group) < 50})
    pd.DataFrame(groups).to_csv(h.REPORTS / "subgroup-errors.csv", index=False)
    improvement = 1 - score["mae_kwh"] / base_score["mae_kwh"]
    result = {"model_version": "home-profile12-v1", "created_utc": datetime.now(timezone.utc).isoformat(),
              "features": h.FEATURES, "user_questions": h.USER_FIELDS, "removed_inputs": sorted(h.REMOVED),
              "split_counts": {k: len(v) for k, v in parts.items()}, "selected_settings": best["settings"],
              "selected_validation": best["validation"], "xgboost": score, "baseline": base_score,
              "previous": previous_score, "original": metrics(test.KWH, original.prediction_kwh),
              "weighted_xgboost": metrics(test.KWH, prediction, test.NWEIGHT),
              "mae_improvement": improvement, "mae_improvement_vs_previous": 1 - score["mae_kwh"] / previous_score["mae_kwh"],
              "target_met": improvement >= .15, "requested_r2_target": h.REQUESTED_R2_TARGET, "requested_r2_target_met": score["r2"] >= h.REQUESTED_R2_TARGET,
              "nominal_coverage": .8, "test_interval_coverage": float(covered.mean()), "interval_radius_kwh": radius,
              "source_sha256": plan["source_sha256"], "frozen_selection_sha256": frozen_hash,
              "activate_in_app": True, "activation_reason": "User-approved 12-input scope; not a claim of improvement over 17 inputs.",
              "evaluation_note": plan["evaluation_note"],
              "limitations": ["Reused benchmark rather than a fresh independent test.",
                              "Annual estimates based on 2020 records, not validated future forecasts.",
                              "Accuracy with Not sure responses is not separately established."]}
    bundle = {"pipeline": pipe, "features": h.FEATURES, "radius": radius, "metrics": result,
              "schema_version": "home-profile12-v1"}
    joblib.dump(bundle, h.MODEL)
    reloaded = joblib.load(h.MODEL)
    assert np.allclose(reloaded["pipeline"].predict(test[h.FEATURES]), pipe.predict(test[h.FEATURES]))
    assert sha(h.REPORTS / "frozen-selection.json") == frozen_hash
    for path in protected:
        assert sha(path) == hashes[str(path.relative_to(ROOT))]
    write("model-results.json", result)
    lines = ["HomePulse — agreed 12 inputs, no appliance questions", "",
             f"2020 household records retained: {len(data):,}.",
             f"Training {len(training):,}; validation {len(validation):,}; calibration {len(calibration):,}; test {len(test):,}.",
             f"Previous 17-input app: R2 {previous_score['r2']:.4f}; MAE {previous_score['mae_kwh']:,.0f} kWh/year.",
             f"New 12-input app: R2 {score['r2']:.4f}; MAE {score['mae_kwh']:,.0f} kWh/year; RMSE {score['rmse_kwh']:,.0f} kWh/year.",
             f"Requested R2 >={h.REQUESTED_R2_TARGET:.2f} reached: {result['requested_r2_target_met']}.",
             f"80% nominal interval benchmark coverage: {covered.mean():.1%}.", "",
             "Selected four candidate settings on validation only. Saved fitted preprocessing with XGBoost.",
             "12 user-entered answers + automatically derived region = 13 model columns.",
             "No appliance fields in form, new database or predictor allowlist. Historical datasets/models preserved.",
             "2015 not used in this experiment.", plan["evaluation_note"], ""]
    (h.REPORTS / "summary.txt").write_text("\n".join(lines))
    print(json.dumps(result, indent=2), flush=True)
    return result


if __name__ == "__main__":
    train()
