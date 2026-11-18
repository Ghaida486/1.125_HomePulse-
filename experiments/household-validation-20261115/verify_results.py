"""Independently recompute household predictions and metrics from saved artifacts."""
from pathlib import Path
import argparse
import json
import math
import sqlite3
import hashlib
import numpy as np
import pandas as pd


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--project',type=Path,required=True)
    p.add_argument('--results',type=Path,required=True)
    a=p.parse_args(); root=a.project; out=a.results
    source=pd.read_csv(root/'data/raw/recs2020_public_v7.csv',usecols=['DOEID','state_postal','REGIONC','TYPEHUQ','TOTSQFT_EN','NWEIGHT','KWH','SOLAR'])
    ids=pd.read_csv(out/'household-split-ids.csv')
    assert len(ids)==17851 and not ids.survey_id.duplicated().any()
    assert set(ids.survey_id)==set(source.loc[source.SOLAR!=1,'DOEID'])
    dev=source.loc[source.DOEID.isin(ids.loc[ids.split=='development','survey_id'])].copy()
    dev['band']=pd.cut(dev.TOTSQFT_EN,[200,1000,1500,2000,2500,3500,15001],right=False,labels=False)
    medians=dev.groupby('REGIONC').KWH.median()
    df=pd.read_csv(out/'evaluation-predictions-with-labels.csv')
    cal=pd.read_csv(out/'calibration-predictions-with-labels.csv')
    assert set(df.survey_id)==set(ids.loc[ids.split=='evaluation','survey_id'])
    assert set(cal.survey_id)==set(ids.loc[ids.split=='calibration','survey_id'])
    mapped=source.set_index('DOEID').loc[df.survey_id]
    np.testing.assert_allclose(df.actual_kwh,mapped.KWH,rtol=1e-12)
    np.testing.assert_allclose(df.weight,mapped.NWEIGHT,rtol=1e-12)
    monthly=pd.read_csv(out/'historical-state-month-predictions.csv',parse_dates=['date','latest_observation_month'])
    with sqlite3.connect(f'file:{root}/data/homepulse_monthly.sqlite?mode=ro',uri=True) as con:
        observations=pd.read_sql_query('select * from monthly_observations',con)
    observations.date=pd.to_datetime(observations.date)
    account_counts=observations.set_index(['state','date']).customers
    for r in monthly.itertuples():
        assert r.latest_observation_month==r.date-pd.DateOffset(months=3)
        assert r.held_accounts==account_counts.loc[(r.state,r.latest_observation_month)]
        np.testing.assert_allclose(r.base_kwh,r.forecast_mwh*1000/r.held_accounts,rtol=1e-12)
    annual=monthly.groupby('state').base_kwh.sum()
    records2020=observations.loc[observations.date.dt.year==2020].copy()
    records2020['kwh']=records2020.sales_mwh*1000/records2020.customers
    observed_annual=records2020.groupby('state').kwh.sum()
    checked=0
    for (state,htype,region),g in df.groupby(['state','home_type','region']):
        for area,g2 in g.groupby(pd.cut(g.area_sqft,[200,1000,1500,2000,2500,3500,15001],right=False,labels=False)):
            factor=None
            for level,ref in [('State',dev.loc[dev.state_postal==state]),('Region',dev.loc[dev.REGIONC==region.upper()]),('United States',dev)]:
                peers=ref.loc[(ref.TYPEHUQ==htype)&(ref.band==area)]
                n=len(peers); w=peers.NWEIGHT.to_numpy()
                neff=w.sum()**2/(w@w) if n else 0
                if n<50 or neff<30: continue
                numerator=(peers.KWH*peers.NWEIGHT).sum()/peers.NWEIGHT.sum()
                denominator=(ref.KWH*ref.NWEIGHT).sum()/ref.NWEIGHT.sum()
                factor=numerator/denominator
                break
            if factor is None:
                assert not g2.supported.any()
                assert g2.hybrid_kwh.isna().all()
            else:
                assert g2.supported.all() and (g2.fallback_level==level).all()
                assert (g2.profile_n==n).all()
                np.testing.assert_allclose(g2.factor,factor,rtol=1e-12)
                np.testing.assert_allclose(g2.hybrid_kwh,annual[state]*factor,rtol=1e-12)
                np.testing.assert_allclose(g2.observed_state_component_kwh,observed_annual[state]*factor,rtol=1e-12)
                checked+=len(g2)
            np.testing.assert_allclose(g2.state_only_kwh,annual[state],rtol=1e-12)
            np.testing.assert_allclose(g2.regional_median_kwh,medians[region.upper()],rtol=1e-12)
    e=df.loc[df.supported]; c=cal.loc[cal.supported]
    errors=np.sort(np.abs(c.hybrid_kwh-c.actual_kwh))
    q=errors[min(len(errors),math.ceil((len(errors)+1)*.8))-1]
    np.testing.assert_allclose(e.lower_kwh,np.maximum(0,e.hybrid_kwh-q),rtol=1e-12)
    np.testing.assert_allclose(e.upper_kwh,e.hybrid_kwh+q,rtol=1e-12)
    metrics=pd.read_csv(out/'overall-household-metrics.csv')
    for r in metrics.itertuples():
        w=np.ones(len(e)) if r.weighting=='unweighted' else e.weight.to_numpy()
        y=e.actual_kwh.to_numpy(); pred=e[r.method].to_numpy(); error=pred-y
        mae=(np.abs(error)*w).sum()/w.sum()
        rmse=np.sqrt((error**2*w).sum()/w.sum())
        r2=1-(error**2*w).sum()/(((y-(y*w).sum()/w.sum())**2)*w).sum()
        np.testing.assert_allclose([r.mae_kwh,r.rmse_kwh,r.r2],[mae,rmse,r2],rtol=1e-12)
    s=json.loads((out/'summary.json').read_text())
    covered=(e.actual_kwh>=e.lower_kwh)&(e.actual_kwh<=e.upper_kwh)
    np.testing.assert_allclose(s['interval']['observed_coverage_pct'],covered.mean()*100,rtol=1e-12)
    assert checked==s['evaluation_n_supported']==3515
    assert (~df.supported).sum()==s['evaluation_n_unsupported']==56
    protected=json.loads((out/'run-manifest-before-results.json').read_text())['protected_files_before']
    assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in protected.items())
    audit=dict(all_checks_passed=True,all_evaluation_predictions_independently_recomputed=checked,
        unsupported_households_accounted_for=56,all_612_monthly_account_counts_verified=True,
        evaluation_reference_values_match_raw_source=True,all_baselines_recomputed=True,
        weighted_and_unweighted_mae_rmse_r2_recomputed=True,calibration_quantile_and_interval_coverage_recomputed=True,
        live_app_database_and_source_unchanged=True)
    (out/'independent-verification.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit,indent=2))


if __name__=='__main__': main()
