"""Build an auditable monthly app snapshot from existing official source files."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import sys
import joblib
import numpy as np
import pandas as pd
from homepulse.monthly import STATES, HOME_TYPES, SIZE_EDGES, SIZE_LABELS, make_features

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-project", type=Path, required=True)
    parser.add_argument("--output-project", type=Path, required=True)
    args = parser.parse_args()
    source, dest = args.source_project.resolve(), args.output_project.resolve()
    if (dest / "data/homepulse_monthly.sqlite").exists():
        raise SystemExit("Monthly database already exists. Build into a new folder to preserve the current snapshot.")
    exp = source / "experiments/state-forecast-20261113"
    verification = json.loads((exp / "results/independent-verification.json").read_text())
    if not verification.get("all_checks_passed"):
        raise SystemExit("Run verify_and_report.py --checks-only successfully before building.")
    spec = importlib.util.spec_from_file_location("state_forecast_study", exp / "run_experiment.py")
    study = importlib.util.module_from_spec(spec); spec.loader.exec_module(study)
    workbook = exp / "raw/eia_monthly_state_sales.xlsx"
    raw = pd.read_excel(workbook,sheet_name="Monthly-States",header=None,skiprows=3)
    obs = raw.loc[raw[2].isin(STATES),[0,1,2,3,5,6]].copy()
    obs.columns=["year","month","state","source_status","sales_mwh","customers"]
    for c in ["year","month","sales_mwh","customers"]:
        obs[c]=pd.to_numeric(obs[c],errors="raise")
    obs["date"]=pd.to_datetime(dict(year=obs.year,month=obs.month,day=1))
    obs=obs.sort_values(["state","date"]).reset_index(drop=True)
    assert len(obs)==10200 and not obs.duplicated(["state","date"]).any()
    assert (obs.customers>0).all() and obs.notna().all().all()
    original, original_cols = study.features(obs)
    check, cols = make_features(obs)
    assert cols == original_cols
    pd.testing.assert_frame_equal(original[cols].reset_index(drop=True),check[cols].reset_index(drop=True))
    frozen=joblib.load(exp / "results/selected-backtest-model.joblib")
    test = check.loc[check.date.between("2024-01-01","2026-08-01")]
    old_predictions=pd.read_csv(exp / "results/test-predictions.csv")
    np.testing.assert_allclose(study.predict(frozen,test),old_predictions.xgboost,rtol=1e-12)
    last=obs.date.max()
    future_months=pd.date_range(last+pd.DateOffset(months=1),periods=3,freq="MS")
    future=pd.DataFrame([dict(state=s,date=m,year=m.year,month=m.month,sales_mwh=np.nan) for s in STATES for m in future_months])
    all_features, cols=make_features(pd.concat([obs,future],ignore_index=True))
    settings=json.loads((exp/"results/selection-before-test.json").read_text())
    model_dir=dest/"models/monthly"; model_dir.mkdir(parents=True,exist_ok=True)
    forecast_rows=[]
    for target in future_months:
        cutoff=target-pd.DateOffset(months=3)
        train=all_features.loc[all_features.date<=cutoff]
        x=all_features.loc[all_features.date==target].copy()
        assert train.sales_mwh.notna().all() and x[cols].notna().all().all()
        bundle=study.fit(train,cols,settings["mode"],settings["settings"])
        bundle.update(training_target_end=str(cutoff.date()),target_month=str(target.date()),schema_version="monthly-state-v1")
        joblib.dump(bundle,model_dir/f"state-{target:%Y-%m}.joblib")
        p=study.predict(bundle,x)
        np.testing.assert_allclose(p,study.predict(joblib.load(model_dir/f"state-{target:%Y-%m}.joblib"),x),rtol=1e-12)
        for (_,row), value in zip(x.iterrows(),p):
            count=int(obs.loc[(obs.state==row.state)&(obs.date==cutoff),"customers"].iloc[0])
            forecast_rows.append(dict(state=row.state,month=target.strftime("%Y-%m"),xgboost_mwh=float(value),
                seasonal_mean_mwh=float(row.same_month_three_year_mean),customer_count_assumption=count,
                latest_observation_month=cutoff.strftime("%Y-%m"),training_target_end=cutoff.strftime("%Y-%m")))
        print(f"Built {target:%Y-%m}: {len(train)} training records through {cutoff:%Y-%m}",flush=True)
    forecasts=pd.DataFrame(forecast_rows)
    path=source/"data/raw/recs2020_public_v7.csv"
    recs=pd.read_csv(path,usecols=["DOEID","state_postal","REGIONC","TYPEHUQ","TOTSQFT_EN","NWEIGHT","KWH","SOLAR"])
    # Exclude identified on-site PV homes to reduce the total-use/grid-sales mismatch.
    # Apartment solar status is not collected; the remaining mismatch is documented.
    profiles=recs.loc[recs.SOLAR!=1].copy()
    assert len(recs)==18496 and len(profiles)==17851
    assert (profiles.KWH>0).all() and (profiles.NWEIGHT>0).all()
    profiles=profiles.rename(columns={"DOEID":"survey_id","state_postal":"state","REGIONC":"region", "TYPEHUQ":"home_type",
        "TOTSQFT_EN":"area_sqft","NWEIGHT":"weight","KWH":"kwh","SOLAR":"solar_code"})
    profiles["region"]=profiles.region.str.title()
    profiles["size_band"]=pd.cut(profiles.area_sqft,bins=SIZE_EDGES,labels=SIZE_LABELS,right=False).astype(str)
    assert profiles.size_band.isin(SIZE_LABELS).all()
    manifest={"schema_version":"monthly-home-scenario-v1","latest_eia_observation":last.strftime("%Y-%m"),
        "estimate_months":[m.strftime("%Y-%m") for m in future_months],"state_month_records":len(obs),
        "forecast_rows":len(forecasts),"recs_source_records":len(recs),"profile_records":len(profiles),
        "identified_solar_homes_excluded":645,"eia_source_sha256":sha(workbook),"recs_source_sha256":sha(path),
        "eia_url":"https://www.eia.gov/electricity/data/state/","recs_url":"https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata",
        "selected_model":settings,"historical_test":json.loads((exp/"results/summary.json").read_text()),
        "household_accuracy_validated":False,"customer_count_rule":"Hold residential accounts at the last count available at target month minus three months",
        "profile_rule":"Joint home-type and size-band weighted mean / all-home weighted mean in the same geography; state then region then US. Minimum 50 records and effective sample >=30.",
        "formula":"state_forecast_MWh * 1000 / customer_count_assumption * profile_factor",
        "limits":["Home output is an unvalidated scenario; state R2 does not measure household accuracy.",
            "Annual 2020 profile differences are assumed to hold in every target month.",
            "RECS primary residences and electricity customer accounts are different populations.",
            "Known on-site PV homes excluded; apartment solar not measured and RECS imputation remains.",
            "Latest revised EIA data used. Historical publication vintages not reconstructed.",
            "Original fixed-model test is unchanged; production models refit at each target's t-3 cutoff.",
            "No home-level prediction interval has been calibrated."]}
    report_dir=dest/"reports/monthly"; report_dir.mkdir(parents=True,exist_ok=True)
    (report_dir/"build-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    forecasts.to_csv(report_dir/"state-forecasts.csv",index=False)
    for name in ["test-predictions.csv","test-state-metrics.csv","test-comparison.csv","independent-verification.json"]:
        shutil.copy2(exp/"results"/name,report_dir/name)
    for name in ["forecast-comparison.png", "model-comparison.png"]:
        if (exp / "results" / name).exists():
            shutil.copy2(exp / "results" / name, report_dir / name)
    db=dest/"data/homepulse_monthly.sqlite"; db.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db) as con:
        for name,df in [("monthly_observations",obs),("forecasts",forecasts),("profiles",profiles),
                        ("test_predictions",old_predictions),("test_state_metrics",pd.read_csv(report_dir/"test-state-metrics.csv"))]:
            df.to_sql(name,con,index=False,if_exists="replace")
        pd.DataFrame([{"key":"manifest","value":json.dumps(manifest)}]).to_sql("metadata",con,index=False,if_exists="replace")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS monthly_forecast_key ON forecasts(state,month)")
        assert con.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    print(json.dumps({"database":str(db),"forecast_rows":len(forecasts),"profiles":len(profiles),"old_test_predictions_unchanged":True}))

if __name__=="__main__": main()
