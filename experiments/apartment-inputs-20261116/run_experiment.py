"""Apartment feature experiment. Writes only to --out; never changes the app.

Reuses the established household split. The previously used calibration part
is validation here, not interval calibration. Previously explored RECS data
make this a historical diagnostic, not a fresh external accuracy claim.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

SEED = 20261116
BASE = ["state_postal", "TYPEHUQ", "TOTSQFT_EN"]
VARIANTS = {
    "core": BASE,
    "bedrooms": BASE + ["BEDROOMS"],
    "building_age": BASE + ["YEARMADERANGE"],
    "heating_fuel": BASE + ["FUELHEAT"],
    "all_three": BASE + ["BEDROOMS", "YEARMADERANGE", "FUELHEAT"],
}
LABELS = {
    "current_method": "Current household method",
    "regional_median": "Apartment regional median",
    "core": "XGBoost: existing inputs",
    "bedrooms": "XGBoost: + bedrooms",
    "building_age": "XGBoost: + building age",
    "heating_fuel": "XGBoost: + heating fuel",
    "all_three": "XGBoost: + all three",
}
SETTINGS = [
    dict(max_depth=2, n_estimators=200, learning_rate=.05, min_child_weight=20, reg_lambda=10),
    dict(max_depth=3, n_estimators=300, learning_rate=.04, min_child_weight=15, reg_lambda=10),
    dict(max_depth=4, n_estimators=300, learning_rate=.04, min_child_weight=10, reg_lambda=10),
    dict(max_depth=3, n_estimators=500, learning_rate=.025, min_child_weight=15, reg_lambda=20),
]
CATEGORICAL = {"state_postal", "TYPEHUQ", "YEARMADERANGE", "FUELHEAT"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def inputs(frame, columns):
    # Explicit allowlist: annual KWH, spending, end-use consumption and IDs
    # cannot enter training/inference through a broad column selector.
    assert set(columns) <= set(VARIANTS["all_three"])
    x = frame[columns].copy()
    for c in columns:
        if c in CATEGORICAL:
            x[c] = x[c].astype("string").fillna("unknown").astype(str)
    return x


def pipeline(columns, settings):
    cats = [c for c in columns if c in CATEGORICAL]
    nums = [c for c in columns if c not in CATEGORICAL]
    prep = ColumnTransformer([
        ("categories", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cats),
        ("numbers", "passthrough", nums),
    ])
    return Pipeline([
        ("preprocessing", prep),
        ("model", XGBRegressor(objective="reg:squarederror", tree_method="hist",
            n_jobs=2, random_state=SEED, subsample=1, colsample_bytree=1, **settings)),
    ])


def predict(model, frame, columns):
    return np.maximum(0, model.predict(inputs(frame, columns)).astype(float))


def score(y, p, w=None):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return dict(n=len(y), r2=float(r2_score(y, p, sample_weight=w)),
        mae_kwh=float(mean_absolute_error(y, p, sample_weight=w)),
        rmse_kwh=float(np.sqrt(mean_squared_error(y, p, sample_weight=w))),
        within_20_pct=float(100 * np.average(np.abs(y-p) <= .2*y, weights=w)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    project, out = args.project.resolve(), args.out.resolve()
    if out.exists():
        raise SystemExit("Output exists; preserve original results.")
    out.mkdir(parents=True)
    raw = project / "data/raw/recs2020_public_v7.csv"
    old = project / "experiments/household-validation-20261115/results"
    protected = ["app.py", "src/homepulse/monthly.py", "src/homepulse/monthly_ui.py",
                 "data/homepulse_monthly.sqlite", "data/raw/recs2020_public_v7.csv"]
    before = {p: sha(project/p) for p in protected}
    protocol = dict(
        experiment="Apartment bedrooms, building age and heating fuel",
        date="2026-11-16", target="Annual RECS 2020 household KWH",
        split_source=str(old / "household-split-ids.csv"),
        split_sha256=sha(old / "household-split-ids.csv"),
        raw_sha256=sha(raw), script_sha256=sha(__file__), seed=SEED,
        variants=VARIANTS, settings=SETTINGS, maximum_fits=20,
        primary_selection="Minimum unweighted validation MAE, before evaluation",
        evaluation="Full apartment evaluation cohort, plus paired supported cohort for current-method comparison",
        retention="All eligible apartments retained; no outlier trimming or error-based exclusions",
        training="Development apartments only; do not refit on validation after selection",
        success_rule="All-three model: at least 10% lower MAE than core XGBoost and higher R2 on paired evaluation; exploratory threshold, not a guarantee of usefulness",
        missing_codes="FUELHEAT -2 is the codebook's Not applicable category, not a negative fuel amount; age and home type categorical",
        weights="Unweighted fitting/primary errors; NWEIGHT-weighted sensitivity evaluation. No population confidence intervals",
        caveats=["RECS data and evaluation results explored before; diagnostic, not fresh external validation",
                 "Former calibration partition is used for model selection here; no prediction interval is calibrated",
                 "Annual apartment scores cannot validate future monthly household estimates",
                 "Heating type here means main heating fuel, not furnace/heat-pump equipment type",
                 "Apartments in buildings with 5+ units remain a broad category; exact building count is unavailable"],
        packages={p:importlib.metadata.version(p) for p in ["pandas","numpy","scikit-learn","xgboost","joblib"]},
        python=sys.version, protected_files_before=before,
    )
    dump(out/"protocol-before-training.json", protocol)

    data = pd.read_csv(raw, usecols=list(dict.fromkeys(
        ["DOEID","REGIONC","KWH","NWEIGHT","SOLAR"]+VARIANTS["all_three"])))
    splits = pd.read_csv(old/"household-split-ids.csv")
    data = data.merge(splits[["survey_id","split"]], left_on="DOEID", right_on="survey_id", validate="one_to_one")
    data = data.loc[data.TYPEHUQ.isin([4,5])].sort_values("DOEID").copy()
    assert len(data)==3452 and not data.DOEID.duplicated().any()
    assert (data.KWH>0).all() and (data.NWEIGHT>0).all()
    assert data.BEDROOMS.between(0,6).all()
    assert data.YEARMADERANGE.between(1,9).all()
    assert data.FUELHEAT.isin([-2,1,2,3,5,7,99]).all()
    assert data.SOLAR.ne(1).all()
    assert not data[VARIANTS["all_three"]].isna().any().any()
    train = data.loc[data.split=="development"].copy()
    val = data.loc[data.split=="calibration"].copy()
    # Held-out KWH is not retained in this inference frame.
    evaluation = data.loc[data.split=="evaluation", ["DOEID","REGIONC","NWEIGHT"]+VARIANTS["all_three"]].copy()
    ids = [set(d.DOEID) for d in [train, val, evaluation]]
    assert not ids[0]&ids[1] and not ids[0]&ids[2] and not ids[1]&ids[2]
    data[["DOEID","TYPEHUQ","split"]].to_csv(out/"split-ids.csv", index=False)
    audit = dict(train=len(train),validation=len(val),evaluation=len(evaluation),
        valid_outliers_removed=0, input_missing_count=0, unique_ids=True, disjoint_splits=True,
        field_counts={c:{str(k):int(v) for k,v in data[c].value_counts().sort_index().items()}
                      for c in ["BEDROOMS","YEARMADERANGE","FUELHEAT"]})
    dump(out/"data-audit.json",audit)
    print("Split:",len(train),len(val),len(evaluation),flush=True)

    boards, models, selection = [], {}, {}
    for variant, columns in VARIANTS.items():
        best = None
        for i, settings in enumerate(SETTINGS):
            model = pipeline(columns, settings)
            model.fit(inputs(train, columns), train.KWH)
            p = predict(model, val, columns)
            s = score(val.KWH, p)
            boards.append(dict(variant=variant,configuration=i,**s))
            key = (s["mae_kwh"],i)
            if best is None or key < best[0]:
                best = (key,model,s,i)
        _, model, s, i = best
        models[variant] = model
        selection[variant] = dict(configuration=i, settings=SETTINGS[i],validation=s,features=columns)
        joblib.dump(dict(pipeline=model,features=columns,target="Annual RECS2020 KWH",variant=variant), out/f"{variant}.joblib")
        print(f"Validation {variant}: MAE {s['mae_kwh']:.1f}, R2 {s['r2']:.3f}",flush=True)
    pd.DataFrame(boards).to_csv(out/"validation-candidates.csv",index=False)
    winner = min(selection, key=lambda v:(selection[v]["validation"]["mae_kwh"],v))
    dump(out/"selection-before-evaluation.json",dict(winner_by_validation=winner, variants=selection))

    # All selection is finished. Save predictions before accessing held-out labels.
    predictions = evaluation[["DOEID","TYPEHUQ","REGIONC","NWEIGHT"]].copy()
    for variant, model in models.items():
        predictions[variant] = predict(model,evaluation,VARIANTS[variant])
        loaded = joblib.load(out/f"{variant}.joblib")
        np.testing.assert_allclose(predictions[variant],predict(loaded["pipeline"],evaluation,loaded["features"]),rtol=1e-12)
        poisoned = evaluation.assign(KWH=-999999, DOLLAREL=999999)
        np.testing.assert_allclose(predictions[variant],predict(model,poisoned,VARIANTS[variant]),rtol=1e-12)
    medians = train.groupby("REGIONC").KWH.median().to_dict()
    predictions["regional_median"] = evaluation.REGIONC.map(medians).fillna(train.KWH.median())
    oldpred = pd.read_csv(old/"evaluation-predictions-before-labels.csv",usecols=["survey_id","supported","hybrid_kwh"])
    predictions = predictions.merge(oldpred,left_on="DOEID",right_on="survey_id",validate="one_to_one").rename(columns={"hybrid_kwh":"current_method"})
    assert "KWH" not in predictions and "actual_kwh" not in predictions
    predictions.to_csv(out/"evaluation-predictions-before-labels.csv",index=False)

    # Labels used only for final diagnostic metrics, never configuration selection.
    scored = predictions.merge(data[["DOEID","KWH"]],on="DOEID",validate="one_to_one")
    scored.to_csv(out/"evaluation-predictions-with-labels.csv",index=False)
    common = scored.loc[scored.supported].copy()
    rows=[]
    for cohort,frame in [("all_apartments",scored),("paired_supported",common)]:
        for method in LABELS:
            if method=="current_method" and cohort=="all_apartments":
                continue
            for weighting,w in [("unweighted",None),("survey_weighted_sensitivity",frame.NWEIGHT.to_numpy())]:
                rows.append(dict(cohort=cohort,method=method,label=LABELS[method],weighting=weighting,
                    **score(frame.KWH,frame[method],w)))
    metrics=pd.DataFrame(rows)
    metrics.to_csv(out/"metrics.csv",index=False)
    groups=[]
    for cohort,frame in [("all_apartments",scored),("paired_supported",common)]:
        for dimension in ["TYPEHUQ","REGIONC"]:
            for group,g in frame.groupby(dimension):
                for method in LABELS:
                    if method=="current_method" and cohort=="all_apartments":
                        continue
                    for weighting,w in [("unweighted",None),("survey_weighted_sensitivity",g.NWEIGHT.to_numpy())]:
                        groups.append(dict(cohort=cohort,dimension=dimension,group=str(group),method=method,
                            weighting=weighting,low_support=len(g)<50,**score(g.KWH,g[method],w)))
    pd.DataFrame(groups).to_csv(out/"subgroup-metrics.csv",index=False)
    board=metrics.loc[(metrics.cohort=="paired_supported") & (metrics.weighting=="unweighted")].set_index("method")
    base,added,current=[board.loc[k] for k in ["core","all_three","current_method"]]
    improvement=100*(1-added.mae_kwh/base.mae_kwh)
    summary=dict(winner_by_validation=winner,primary_comparison_n=len(common),all_evaluation_n=len(scored),
        current_method_unsupported=int((~scored.supported).sum()),
        paired_results=board.reset_index().to_dict(orient="records"),
        all_three_mae_improvement_over_core_pct=float(improvement),
        all_three_r2_change_over_core=float(added.r2-base.r2),
        all_three_mae_improvement_over_current_pct=float(100*(1-added.mae_kwh/current.mae_kwh)),
        provisional_rule_met=bool(improvement>=10 and added.r2>base.r2),
        independent_external_validation=False,monthly_home_accuracy_validated=False,app_changed=False)
    dump(out/"summary.json",summary)
    after={p:sha(project/p) for p in protected}
    assert before==after
    dump(out/"integrity-checks.json",dict(production_unchanged=True,protected_files_after=after,
        target_excluded_from_features=True,poisoned_target_does_not_change_prediction=True,
        saved_pipeline_reproduces_predictions=True,preprocessing_fit_on_development_only=True,
        selection_uses_validation_only=True,no_refit_on_validation=True,no_test_based_tuning=True,
        feature_allowlist=VARIANTS,split_disjoint=True,no_error_based_removal=True))
    print("PAIRED EVALUATION",flush=True)
    print(board[["n","r2","mae_kwh","rmse_kwh","within_20_pct"]].round(3).to_string(),flush=True)
    print("All-three improvement over core:",round(improvement,2),"% MAE",flush=True)


if __name__ == "__main__":
    main()
