"""One prespecified historical household check; does not modify the live app.

Uses the protocol saved on 2026-11-14. RECS 2020 has already been explored,
so this is a historical diagnostic, not fresh independent external validation.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import importlib.metadata
import json
import math
import shutil
import sqlite3
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

SEED = 20261114
ALPHA = .2


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def score(actual, prediction, weights=None):
    y, p = np.asarray(actual, float), np.asarray(prediction, float)
    w = np.ones(len(y)) if weights is None else np.asarray(weights, float)
    assert len(y) and np.isfinite(y).all() and (y > 0).all()
    assert np.isfinite(p).all() and np.isfinite(w).all() and (w > 0).all()
    err = p - y
    ape = np.abs(err) / y
    order = np.argsort(ape, kind="stable")
    weighted_median = float(ape[order][np.searchsorted(np.cumsum(w[order]), .5*w.sum())])
    return dict(n=len(y), mae_kwh=float(mean_absolute_error(y, p, sample_weight=w)),
                rmse_kwh=float(np.sqrt(mean_squared_error(y, p, sample_weight=w))),
                r2=float(r2_score(y, p, sample_weight=w)) if len(y)>1 and np.var(y)>0 else None,
                bias_kwh=float(np.average(err, weights=w)),
                median_ape_pct=float(np.median(ape)*100) if weights is None else weighted_median*100,
                within_10_pct=float(np.average(ape <= .1, weights=w)*100),
                within_20_pct=float(np.average(ape <= .2, weights=w)*100))


def interval_summary(df, q, weights=None):
    lo = np.maximum(0, df.hybrid_kwh.to_numpy()-q)
    hi = df.hybrid_kwh.to_numpy()+q
    y = df.actual_kwh.to_numpy()
    width = hi-lo
    return dict(nominal_coverage_pct=80., observed_coverage_pct=float(np.average((y>=lo)&(y<=hi), weights=weights)*100),
                mean_width_kwh=float(np.average(width, weights=weights)), median_width_kwh=float(np.median(width)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    project, out = args.project.resolve(), args.out.resolve()
    if out.exists():
        raise SystemExit("Output exists; preserve the first inspected run and use a new directory.")
    out.mkdir(parents=True)
    sys.path.insert(0, str(project/"src"))
    from homepulse.monthly import make_features, profile_adjustment, size_band, SIZE_EDGES, SIZE_LABELS, HOME_TYPES
    study_dir = project/"experiments/state-forecast-20261113"
    spec = importlib.util.spec_from_file_location("state_study", study_dir/"run_experiment.py")
    study = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(study)
    protocol = project/"docs/household-validation-plan-20261114.md"
    raw_path = project/"data/raw/recs2020_public_v7.csv"
    db_path = project/"data/homepulse_monthly.sqlite"
    preserved = [project/"app.py", project/"src/homepulse/monthly.py", project/"src/homepulse/monthly_ui.py", db_path]
    before = {str(p.relative_to(project)):sha(p) for p in preserved}
    manifest = dict(experiment="Household annual 2020 diagnostic", run_date="2026-11-15", protocol_date="2026-11-14",
        script_sha256=sha(__file__), protocol_sha256=sha(protocol), recs_sha256=sha(raw_path),
        database_sha256=sha(db_path), source_code_sha256=sha(project/"src/homepulse/monthly.py"),
        state_study_sha256=sha(study_dir/"run_experiment.py"), state_plan_sha256=sha(study_dir/"experiment-plan.json"),
        seed=SEED, target="RECS KWH: annual household electricity, 2020", new_external_validation=False,
        packages={x:importlib.metadata.version(x) for x in ["pandas","numpy","scikit-learn","xgboost","joblib"]},
        python=sys.version, protected_files_before=before,
        rules=dict(profile_split="60% development / 20% calibration / 20% evaluation; region x home type strata",
            state_train=["2013-01","2017-09"], state_validation=["2018-01","2019-09"],
            state_refit=["2013-01","2019-09"], state_prediction=["2020-01","2020-12"],
            state_information_lag_months=3, max_state_candidates=6, primary_measure="unweighted annual household MAE",
            required_improvement_over_regional_median_pct=15, require_no_worse_than_unadjusted_state=True,
            profile_min_n=50, profile_min_effective_n=30, fixed_size_edges=SIZE_EDGES,
            nominal_interval_coverage=.8, remove_valid_outliers=False))
    dump(out/"run-manifest-before-results.json", manifest)
    shutil.copy2(protocol, out/"protocol-before-results.md")

    # Save household split before using any held-out outcome for evaluation.
    recs = pd.read_csv(raw_path, usecols=["DOEID","state_postal","REGIONC","TYPEHUQ","TOTSQFT_EN","NWEIGHT","KWH","SOLAR"])
    assert len(recs)==18496 and not recs.DOEID.duplicated().any()
    eligible = recs.loc[recs.SOLAR != 1].copy().rename(columns={"DOEID":"survey_id","state_postal":"state", "REGIONC":"region",
        "TYPEHUQ":"home_type", "TOTSQFT_EN":"area_sqft", "NWEIGHT":"weight", "KWH":"kwh", "SOLAR":"solar_code"})
    eligible["region"] = eligible.region.str.title()
    eligible["size_band"] = pd.cut(eligible.area_sqft, bins=SIZE_EDGES, labels=SIZE_LABELS, right=False).astype(str)
    assert len(eligible)==17851 and eligible.size_band.isin(SIZE_LABELS).all()
    assert (eligible.kwh > 0).all() and (eligible.weight > 0).all()
    strata = eligible.region + ":" + eligible.home_type.astype(str)
    dev_idx, held_idx = train_test_split(eligible.index, test_size=.4, random_state=SEED, stratify=strata)
    cal_idx, eval_idx = train_test_split(held_idx, test_size=.5, random_state=SEED, stratify=strata.loc[held_idx])
    dev = eligible.loc[dev_idx].sort_values("survey_id").copy()
    cal = eligible.loc[cal_idx].sort_values("survey_id").copy()
    evaluation = eligible.loc[eval_idx].sort_values("survey_id").copy()
    id_sets = [set(d.survey_id) for d in [dev, cal, evaluation]]
    assert not id_sets[0]&id_sets[1] and not id_sets[0]&id_sets[2] and not id_sets[1]&id_sets[2]
    splits = pd.concat([d[["survey_id","state","region","home_type"]].assign(split=label) for d,label in
                        [(dev,"development"),(cal,"calibration"),(evaluation,"evaluation")]])
    splits.sort_values("survey_id").to_csv(out/"household-split-ids.csv",index=False)
    split_audit = dict(source_households=len(recs), known_solar_excluded=int((recs.SOLAR==1).sum()), eligible=len(eligible),
        development=len(dev), calibration=len(cal), evaluation=len(evaluation), removed_for_error_or_outlier=0,
        no_duplicate_ids=True, splits_disjoint=True, development_ids_sha256=hashlib.sha256(
            ",".join(map(str,dev.survey_id)).encode()).hexdigest())
    dump(out/"split-audit.json",split_audit)
    print("Household groups:", json.dumps(split_audit),flush=True)

    # Historical state model selection is isolated from 2020 state outcomes.
    with sqlite3.connect(f"file:{db_path}?mode=ro",uri=True) as con:
        obs = pd.read_sql_query("SELECT * FROM monthly_observations",con)
    obs["date"] = pd.to_datetime(obs.date)
    obs = obs.loc[obs.date <= "2020-12-01"].copy()
    feat, cols = make_features(obs)
    train = feat.loc[feat.date.between("2013-01-01","2017-09-01")]
    val = feat.loc[feat.date.between("2018-01-01","2019-09-01")]
    refit = feat.loc[feat.date.between("2013-01-01","2019-09-01")]
    targets = feat.loc[feat.date.between("2020-01-01","2020-12-01")].copy()
    assert len(targets)==612 and refit.date.max()<targets.latest_observation_month.min()
    assert train.date.max()<val.latest_observation_month.min()
    forbidden = {"sales_mwh","customers","source_status"}
    assert not forbidden.intersection(cols)
    prediction_cols = list(dict.fromkeys(cols + ["lag_12","recent_mean"]))
    candidates, rows = {}, []
    for mode in study.PLAN["xgboost_targets"]:
        for settings in study.PLAN["xgboost_settings"]:
            name = f"xgb_{mode}_depth{settings['max_depth']}"
            bundle = study.fit(train,cols,mode,settings)
            p = study.predict(bundle,val[prediction_cols])
            metrics,_ = study.metric_rows(val,p,name,"validation_pre2020")
            rows.append(metrics); candidates[name]=(mode,settings)
            print("Pre-2020 selection:",name,"mean state WAPE",round(metrics["mean_state_wape"],5),flush=True)
    board = pd.DataFrame(rows)
    board.to_csv(out/"state-pre2020-validation.csv",index=False)
    winner = board.sort_values(["mean_state_wape","model"]).iloc[0].model
    mode, settings = candidates[winner]
    dump(out/"state-selection-before-2020.json",dict(model=winner,mode=mode,settings=settings,
        criterion="Lowest mean-state WAPE on 2018-01 through 2019-09 only",candidate_count=len(candidates)))
    bundle = study.fit(refit,cols,mode,settings)
    bundle.update(training_target_end="2019-09",test_year=2020)
    joblib.dump(bundle,out/"historical-state-pipeline.joblib")
    target_predictions = study.predict(bundle,targets[prediction_cols])
    np.testing.assert_allclose(target_predictions,study.predict(joblib.load(out/"historical-state-pipeline.joblib"),targets[prediction_cols]),rtol=1e-12)

    # Independently hide all state outcomes after each target's information cutoff.
    for date in sorted(targets.date.unique()):
        cutoff = date-pd.DateOffset(months=3)
        hidden = obs.copy()
        hidden.loc[hidden.date > cutoff,["sales_mwh","customers"]] = np.nan
        h, same_cols = make_features(hidden)
        h = h.loc[h.date==date]
        original = targets.loc[targets.date==date]
        assert same_cols==cols and h.sales_mwh.isna().all()
        pd.testing.assert_frame_equal(h[prediction_cols].reset_index(drop=True),original[prediction_cols].reset_index(drop=True))
        np.testing.assert_allclose(study.predict(bundle,h[prediction_cols]),study.predict(bundle,original[prediction_cols]),rtol=1e-12)
    forecasts = targets[["state","date","latest_observation_month"]].copy()
    forecasts["forecast_mwh"] = target_predictions
    counts = obs.set_index(["state","date"]).customers
    forecasts["held_accounts"] = [float(counts.loc[(r.state,r.latest_observation_month)]) for r in forecasts.itertuples()]
    forecasts["base_kwh"] = forecasts.forecast_mwh*1000/forecasts.held_accounts
    assert (forecasts.held_accounts>0).all()
    forecasts.to_csv(out/"historical-state-month-predictions.csv",index=False)
    state_annual = forecasts.groupby("state").base_kwh.sum()
    observed = obs.loc[obs.date.dt.year==2020].copy()
    observed["account_kwh"] = observed.sales_mwh*1000/observed.customers
    observed_annual = observed.groupby("state").account_kwh.sum()
    pd.DataFrame({"forecast_annual_account_kwh":state_annual,"observed_annual_account_kwh":observed_annual}).to_csv(out/"historical-state-annual-account-kwh.csv")

    # Prediction accepts app inputs and development profiles only. No test KWH/weight.
    medians = dev.groupby("region").kwh.median().to_dict()
    national_median = float(dev.kwh.median())
    cache = {}
    def predict_homes(inputs):
        assert set(inputs.columns)=={"survey_id","state","region","home_type","area_sqft"}
        result = []
        for r in inputs.itertuples():
            item = dict(survey_id=int(r.survey_id),state=r.state,region=r.region,home_type=int(r.home_type),area_sqft=float(r.area_sqft))
            key = (r.state,int(r.home_type),size_band(r.area_sqft))
            if key not in cache:
                try:
                    cache[key] = profile_adjustment(dev,r.state,int(r.home_type),r.area_sqft)
                except ValueError as error:
                    cache[key] = {"unsupported_reason":str(error)}
            adj = cache[key]
            item.update(regional_median_kwh=float(medians.get(r.region,national_median)),state_only_kwh=float(state_annual[r.state]))
            if "unsupported_reason" in adj:
                item.update(supported=False,unsupported_reason=adj["unsupported_reason"])
            else:
                item.update(supported=True,hybrid_kwh=float(state_annual[r.state]*adj["factor"]),
                    observed_state_component_kwh=float(observed_annual[r.state]*adj["factor"]),
                    factor=adj["factor"],profile_n=adj["sample_n"],profile_effective_n=adj["effective_n"],
                    fallback_level=adj["level"],profile_geography=adj["geography"],size_band=adj["size_band"])
            result.append(item)
        return pd.DataFrame(result)

    input_cols = ["survey_id","state","region","home_type","area_sqft"]
    cal_pred = predict_homes(cal[input_cols])
    eval_pred = predict_homes(evaluation[input_cols])
    cal_pred.to_csv(out/"calibration-predictions-before-labels.csv",index=False)
    eval_pred.to_csv(out/"evaluation-predictions-before-labels.csv",index=False)
    assert "kwh" not in cal_pred and "actual_kwh" not in eval_pred
    # Actual household outcomes enter here, only after predictions have been saved.
    labels = eligible[["survey_id","kwh","weight"]].rename(columns={"kwh":"actual_kwh"})
    cal_scored = cal_pred.merge(labels,on="survey_id",validate="one_to_one")
    eval_scored = eval_pred.merge(labels,on="survey_id",validate="one_to_one")
    cs = cal_scored.loc[cal_scored.supported].copy()
    es = eval_scored.loc[eval_scored.supported].copy()
    errors = np.abs(cs.hybrid_kwh-cs.actual_kwh).to_numpy()
    rank = min(len(errors),math.ceil((len(errors)+1)*(1-ALPHA)))
    q = float(np.sort(errors)[rank-1])
    dump(out/"calibration-before-evaluation.json",dict(n=len(errors),rank=rank,absolute_residual_quantile_kwh=q,
        nominal_coverage_pct=80,method="Ceiling rank ceil((n+1)*0.8) from calibration absolute errors, lower bound clipped at zero"))
    for frame in [cal_scored,eval_scored]:
        frame["lower_kwh"] = np.maximum(0,frame.hybrid_kwh-q)
        frame["upper_kwh"] = frame.hybrid_kwh+q
        frame["signed_error_kwh"] = frame.hybrid_kwh-frame.actual_kwh
        frame["absolute_error_kwh"] = frame.signed_error_kwh.abs()
    cal_scored.to_csv(out/"calibration-predictions-with-labels.csv",index=False)
    eval_scored.to_csv(out/"evaluation-predictions-with-labels.csv",index=False)

    methods = {"hybrid_kwh":"Historical household method", "regional_median_kwh":"Regional median baseline",
               "state_only_kwh":"Unadjusted state/account baseline", "observed_state_component_kwh":"Component diagnostic: observed state values"}
    metrics = []
    for field,label in methods.items():
        for weighting,w in [("unweighted",None),("survey_weighted_sensitivity",es.weight.to_numpy())]:
            metrics.append(dict(method=field,label=label,weighting=weighting,**score(es.actual_kwh,es[field],w)))
    pd.DataFrame(metrics).to_csv(out/"overall-household-metrics.csv",index=False)
    groups = []
    for dim in ["home_type","region","state"]:
        for group, frame in eval_scored.groupby(dim):
            supported = frame.loc[frame.supported]
            item = dict(dimension=dim,group=str(group),group_label=HOME_TYPES[int(group)] if dim=="home_type" else str(group),
                total_n=len(frame),supported_n=len(supported),prediction_coverage_pct=100*len(supported)/len(frame),low_support=len(supported)<50)
            for field in methods:
                for weighting,w in [("unweighted",None),("survey_weighted_sensitivity",supported.weight.to_numpy())]:
                    row = dict(**item,method=field,weighting=weighting)
                    if len(supported):
                        row.update(score(supported.actual_kwh,supported[field],w))
                        if field=="hybrid_kwh":
                            row.update(interval_summary(supported,q,w))
                            baseline_mae = mean_absolute_error(supported.actual_kwh,supported.regional_median_kwh,sample_weight=w)
                            row["improvement_over_regional_median_pct"] = 100*(1-row["mae_kwh"]/baseline_mae)
                    groups.append(row)
    pd.DataFrame(groups).to_csv(out/"subgroup-household-metrics.csv",index=False)
    board = {r["method"]:r for r in metrics if r["weighting"]=="unweighted"}
    hybrid,median,unadjusted = [board[x] for x in ["hybrid_kwh","regional_median_kwh","state_only_kwh"]]
    improvement = 100*(1-hybrid["mae_kwh"]/median["mae_kwh"])
    state_metrics,_ = study.metric_rows(targets,target_predictions,"xgboost","historical2020")
    summary = dict(status="Completed first prespecified household historical diagnostic; no post-evaluation tuning",
        target="2020 annual household kWh", split=split_audit,evaluation_n_total=len(evaluation),
        evaluation_n_supported=len(es),evaluation_n_unsupported=int((~eval_scored.supported).sum()),
        prediction_coverage_pct=100*len(es)/len(evaluation),calibration_n_supported=len(cs),
        household_metrics=metrics,improvement_over_regional_median_pct=improvement,
        improvement_over_unadjusted_state_pct=100*(1-hybrid["mae_kwh"]/unadjusted["mae_kwh"]),
        provisional_benchmark_met=bool(improvement>=15 and hybrid["mae_kwh"]<=unadjusted["mae_kwh"]),
        interval=interval_summary(es,q),survey_weighted_interval_sensitivity=interval_summary(es,q,es.weight.to_numpy()),
        interval_half_width_kwh=q,profile_geography_counts=es.fallback_level.value_counts().to_dict(),
        historical_state_metrics=state_metrics,selected_state_model=winner,
        no_fresh_external_test=True,monthly_household_accuracy_validated=False,present_day_household_accuracy_validated=False,
        caveats=["2020 data and architecture were explored previously; this is a diagnostic holdout, not untouched external validation.",
                 "Annual household test does not validate individual months or current/future-year accuracy.",
                 "RECS primary residences differ from utility account population; known solar excluded but apartment solar unmeasured.",
                 "2020 values are EIA annualized/imputed reference consumption, not perfect raw meter readings.",
                 "Revised state data used, not reconstructed publication vintages.",
                 "Calibration intervals describe sample coverage, not guarantees for a particular household or future year.",
                 "Replicate-weight population confidence intervals are not calculated; weighted errors are sensitivity results."])
    dump(out/"summary.json",summary)
    after = {str(p.relative_to(project)):sha(p) for p in preserved}
    assert before == after
    audit = dict(production_files_unchanged=True,household_ids_disjoint=True,
        no_actual_household_kwh_in_prediction_input=True,profile_numerators_and_denominators_development_only=True,
        state_actuals_hidden_for_all_12_months=True,state_prediction_rows_checked=612,
        state_saved_pipeline_predictions_match=True,state_fit_targets_end="2019-09",no_evaluation_based_tuning=True,
        calibration_excluded_from_profile_fit=True,evaluation_excluded_from_calibration=True,
        all_eligible_extreme_consumption_values_retained=True,predictions_written_before_labels_joined=True,
        source_and_code_hashes_recorded=True,protected_files_after=after)
    dump(out/"integrity-checks.json",audit)
    print("HOUSEHOLD RESULT",json.dumps({k:summary[k] for k in ["evaluation_n_supported","evaluation_n_unsupported","improvement_over_regional_median_pct","provisional_benchmark_met","interval"]}),flush=True)
    print(pd.DataFrame(metrics).loc[lambda d:d.weighting=="unweighted",["label","mae_kwh","r2","within_20_pct"]].to_string(index=False),flush=True)


if __name__=="__main__":
    main()
