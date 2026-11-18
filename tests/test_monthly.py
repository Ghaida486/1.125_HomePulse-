from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from homepulse.monthly import DATABASE, ROOT, load_store, size_band, estimate_home, profile_adjustment, make_features, evidence_chart, overall_metrics, overall_evidence_chart

@pytest.fixture(scope="module")
def store():
    return load_store(DATABASE)

def test_size_boundaries_and_invalid_values():
    assert size_band(999)=="200–999 sq ft"
    assert size_band(1000)=="1,000–1,499 sq ft"
    assert size_band(15000)=="3,500–15,000 sq ft"
    for value in [0,199,15001,float("nan"),float("inf"),True,"bad"]:
        with pytest.raises(ValueError): size_band(value)

def test_estimate_units_and_matching_are_traceable(store):
    r=estimate_home(store,"MA","2026-11",2,1800)
    assert r["estimate_kwh"]==pytest.approx(r["state_sales_mwh"]*1000/r["customer_count_assumption"]*r["factor"])
    assert r["sample_n"]>=50 and r["effective_n"]>=30
    assert r["training_target_end"]=="2026-08"
    assert r["factor"]==pytest.approx(r["profile_mean_annual_kwh"]/r["reference_mean_annual_kwh"])
    p=store["profiles"]
    ref=p if r["level"]=="United States" else p.loc[p.state=="MA"] if r["level"]=="State" else p.loc[p.region==r["geography"]]
    peers=ref.loc[(ref.home_type==2)&(ref.size_band==r["size_band"])]
    assert r["profile_mean_annual_kwh"]==pytest.approx(np.average(peers.kwh,weights=peers.weight))
    with pytest.raises(ValueError): estimate_home(store,"MA","2035-01",2,1800)
    with pytest.raises(ValueError): estimate_home(store,"XX","2026-11",2,1800)
    with pytest.raises(ValueError): profile_adjustment(p.head(5),"MA",2,1800)

def test_forecast_rows_and_no_future_input_leakage(store):
    f=store["forecasts"]
    assert len(f)==153 and not f.duplicated(["state","month"]).any()
    assert (f[["xgboost_mwh","seasonal_mean_mwh","customer_count_assumption"]]>0).all().all()
    obs=store["monthly_observations"].copy()
    obs["date"]=pd.to_datetime(obs.date)
    first,cols=make_features(obs)
    target=pd.Timestamp("2025-01-01")
    changed=obs.copy(); changed.loc[changed.date>target-pd.DateOffset(months=3),"sales_mwh"]*=5
    second,_=make_features(changed)
    pd.testing.assert_frame_equal(first.loc[first.date==target,cols],second.loc[second.date==target,cols])
    for _,r in f.iterrows():
        cutoff=pd.Timestamp(r.month)-pd.DateOffset(months=3)
        assert pd.Timestamp(r.latest_observation_month)==cutoff
        count=int(obs.loc[(obs.state==r.state)&(obs.date==cutoff),"customers"].iloc[0])
        assert r.customer_count_assumption==count

def test_xgboost_graph_uses_all_state_test_months(store):
    source=store["test_predictions"]
    fig=evidence_chart(source,"MA")
    assert len(fig.data)==3
    assert all(len(trace.x)==32 for trace in fig.data)
    rows=source.loc[source.state=="MA"].sort_values("date")
    np.testing.assert_allclose(fig.data[0].y,rows.sales_mwh)
    np.testing.assert_allclose(fig.data[1].y,rows.xgboost)
    np.testing.assert_allclose(fig.data[2].y,rows.same_month_three_year_mean)

def test_overall_chart_includes_complete_test_and_correct_metric(store):
    from sklearn.metrics import r2_score, mean_absolute_error
    rows=store["test_predictions"].sort_values(["state","date"])
    fig=overall_evidence_chart(rows)
    assert len(fig.data[0].x)==1632
    assert rows.state.nunique()==51 and not rows.duplicated(["state","date"]).any()
    np.testing.assert_allclose(fig.data[0].x,rows.sales_mwh)
    np.testing.assert_allclose(fig.data[0].y,rows.xgboost)
    assert list(fig.data[0].customdata[:,0])==list(rows.state)
    values=overall_metrics(rows)
    assert values["pooled_r2"]==pytest.approx(r2_score(rows.sales_mwh,rows.xgboost))
    assert values["mae_mwh"]==pytest.approx(mean_absolute_error(rows.sales_mwh,rows.xgboost))
    assert values["pooled_r2"]==pytest.approx(store["metadata"]["historical_test"]["xgboost"]["pooled_r2"])
    assert overall_metrics(rows,"same_month_three_year_mean")["mae_mwh"]<values["mae_mwh"]
    invalid=rows.copy(); invalid.iloc[0,invalid.columns.get_loc("xgboost")]=np.nan
    with pytest.raises(ValueError): overall_metrics(invalid)


def test_four_input_app_updates_without_stale_result(store):
    app=AppTest.from_file(str(ROOT/"app.py")).run(timeout=60)
    assert not app.exception
    assert app.tabs[0].label=="Home estimate"
    assert next(x.value for x in app.metric if x.label=="Test predictions")=="1,632"
    assert {s.key for s in app.selectbox}=={"monthly_state","monthly_month","monthly_type"}
    assert len(app.number_input)==1
    initial=estimate_home(store,"MA","2026-11",2,1800)
    assert next(x.value for x in app.metric if x.label=="Estimated monthly electricity")==f"{initial['estimate_kwh']:,.0f} kWh"
    app.selectbox(key="monthly_state").select("TX")
    app.selectbox(key="monthly_month").select("2026-10")
    app.selectbox(key="monthly_type").select(5)
    app.number_input(key="monthly_area").set_value(1000)
    app.run(timeout=60)
    assert not app.exception and not app.error
    changed=estimate_home(store,"TX","2026-10",5,1000)
    assert next(x.value for x in app.metric if x.label=="Estimated monthly electricity")==f"{changed['estimate_kwh']:,.0f} kWh"
    assert any("household-level accuracy has not yet been validated" in x.value for x in app.info)
    assert next(x.value for x in app.metric if x.label=="All states combined: XGBoost R²")=="0.990"
