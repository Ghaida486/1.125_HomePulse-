"""Run from this folder: streamlit run app.py"""
import json
import sqlite3
import joblib
import pandas as pd
import plotly.express as px
import streamlit as st
from homepulse.config import ROOT, MODEL, DATABASE, REPORTS, NUMERIC, CATEGORIES, FIELD_LABELS
from homepulse.data import load_data, weighted_comparison
from homepulse.prediction import predict
from homepulse import practical, home_profile
from homepulse.practical_ui import render_profile
from homepulse.geography import render_map

profile_schema = practical
USE_PROFILE12 = (home_profile.MODEL.exists() and home_profile.DATABASE.exists()
                 and (home_profile.REPORTS / "model-results.json").exists()
                 and json.loads((home_profile.REPORTS / "model-results.json").read_text())["activate_in_app"])

USE_PRACTICAL = (practical.MODEL.exists() and practical.DATABASE.exists()
                 and (practical.REPORTS / "model-results.json").exists()
                 and json.loads((practical.REPORTS / "model-results.json").read_text())["activate_in_app"])
if USE_PRACTICAL:
    MODEL, DATABASE, REPORTS = practical.MODEL, practical.DATABASE, practical.REPORTS
    predict = practical.predict

if USE_PROFILE12:
    from homepulse.home_profile_ui import render_profile
    USE_PRACTICAL = True
    profile_schema = home_profile
    MODEL, DATABASE, REPORTS = home_profile.MODEL, home_profile.DATABASE, home_profile.REPORTS
    predict = home_profile.predict

st.set_page_config(page_title="HomePulse", page_icon="🏠", layout="wide")
st.title("HomePulse")
st.write("Household electricity prediction and comparison")
st.caption("Research prototype • U.S. RECS 2020 • Annual electricity in kWh")
if not DATABASE.exists() or not MODEL.exists():
    st.info("Prepare the data and train the model first: `homepulse prepare`, then `homepulse train`.")
    st.stop()


@st.cache_data
def records(path, modified):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        return pd.read_sql_query("SELECT * FROM households ORDER BY DOEID", conn)


@st.cache_resource
def artifact(path, modified):
    return joblib.load(path)


df, bundle = records(str(DATABASE), DATABASE.stat().st_mtime_ns), artifact(str(MODEL), MODEL.stat().st_mtime_ns)
tabs = st.tabs(["Estimate a home", "Explore and compare", "Model evidence", "Data and limitations"])

with tabs[0]:
    st.subheader("Describe the home")
    st.write("Use household characteristics and location. No electricity bill is required.")
    if USE_PROFILE12:
        profile, submitted = render_profile(bundle)
    elif USE_PRACTICAL:
        profile, submitted = render_profile()
    else:
        st.caption("Floor area includes energy-consuming basements and conditioned attics/garages. Seven residents means seven or more. Construction periods end in 2020.")
        with st.form("home_profile"):
            left, right = st.columns(2)
            profile = {}
            defaults = {"TOTSQFT_EN": 1800, "NHSLDMEM": 3, "NUMFRIG": 1, "NUMFREEZ": 0}
            with left:
                for key, (label, low, high) in NUMERIC.items():
                    profile[key] = st.number_input(label, min_value=low, max_value=high, value=defaults[key], step=10 if key == "TOTSQFT_EN" else 1)
                for key in ["TYPEHUQ", "YEARMADERANGE", "REGIONC"]:
                    options = list(CATEGORIES[key].values())
                    default = {"TYPEHUQ": "Detached house", "YEARMADERANGE": "2000-2009", "REGIONC": "Midwest"}[key]
                    profile[key] = st.selectbox(FIELD_LABELS[key], options, index=options.index(default))
            with right:
                for key in ["BA_climate", "EQUIPM", "FUELHEAT", "ACEQUIPM_PUB"]:
                    profile[key] = st.selectbox(FIELD_LABELS[key], list(CATEGORIES[key].values()))
                st.info("Choose the actual region and local climate. This model does not support street addresses or neighborhood-level estimates.")
            submitted = st.form_submit_button("Estimate annual electricity", type="primary")
    if submitted:
        try:
            result = predict(profile, bundle)
        except ValueError as exc:
            st.error(str(exc))
        else:
            c1, c2 = st.columns(2)
            c1.metric("Estimated annual electricity", f"{result['estimate_kwh']:,.0f} kWh")
            c2.metric("Estimated range (80% target coverage)", f"{result['lower_kwh']:,.0f}–{result['upper_kwh']:,.0f} kWh")
            st.caption("We set this range using prediction errors from a separate group of survey homes, aiming to cover 80% of homes overall. Coverage varies by home type and region; this is not a guarantee for your home. It does not account for changes since 2020.")
            if USE_PRACTICAL and any(v is None or v == profile_schema.UNKNOWN for v in profile.values()):
                st.warning("Some details are unknown. The model uses its missing-value preprocessing; accuracy and range coverage for incomplete profiles have not been separately established.")
            location_field = "state_postal" if USE_PRACTICAL else "REGIONC"
            location_name = "state" if USE_PRACTICAL else "region"
            peers = df[(df.TYPEHUQ == profile["TYPEHUQ"]) & (df[location_field] == profile[location_field])]
            peers = peers[peers.TOTSQFT_EN.between(profile["TOTSQFT_EN"] * .75, profile["TOTSQFT_EN"] * 1.25)]
            if len(peers) < 30:
                st.warning(f"Only {len(peers)} survey homes match the type, {location_name} and floor area within ±25%. This profile has limited comparison support.")
            else:
                average = (peers.KWH * peers.NWEIGHT).sum() / peers.NWEIGHT.sum()
                st.write(f"For context, **{len(peers):,} survey homes** match the type, {location_name} and floor area within ±25%. Their survey-weighted mean is **{average:,.0f} kWh/year**. Other characteristics may differ.")
    st.info("Estimates describe relationships in 2020 U.S. survey data. Changing an input does not establish retrofit savings or predict a future year's consumption.")

with tabs[1]:
    if "state_postal" in df.columns:
        render_map(df)
        st.divider()
    st.subheader("Compare home types and regions")
    region = st.selectbox("Filter region", ["All regions", *sorted(df.REGIONC.unique())])
    filtered = df if region == "All regions" else df[df.REGIONC == region]
    dimension = st.radio("Compare by", ["Home type", "Region", "Climate"] + (["State"] if USE_PRACTICAL else []), horizontal=True)
    field = {"Home type": "TYPEHUQ", "Region": "REGIONC", "Climate": "BA_climate", "State": "state_postal"}[dimension]
    summary = weighted_comparison(filtered, field)
    fig = px.bar(summary, x="group", y="mean_kwh", color="group", labels={"group": dimension, "mean_kwh": "Weighted mean annual electricity (kWh)"}, color_discrete_sequence=px.colors.qualitative.Safe)
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(summary.rename(columns={"group": dimension, "sample_households": "Survey homes", "represented_households": "Households represented", "mean_kwh": "Average electricity (kWh/year)", "standard_error": "Sampling standard error (kWh)", "rse_percent": "Relative standard error (%)", "low_support": "Limited comparison support"}).round(2), hide_index=True, width="stretch")
    st.caption("Means use NWEIGHT. Standard errors and relative standard errors (RSE) use 60 EIA jackknife replicate weights. Low support flags n<50 or RSE>30%. Group differences are descriptive and may reflect size, climate, occupancy and other factors.")

with tabs[2]:
    st.subheader("Model performance")
    result = bundle["metrics"]
    if USE_PRACTICAL:
        st.caption("The revised model was selected using validation data, then checked on the same 3,700 test households as the original. This benchmark has been inspected in earlier experiments; it is not a fresh independent test.")
        old, new = result.get("previous", result["original"]), result["xgboost"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Previous 17-input R²" if USE_PROFILE12 else "Original R²", f"{old['r2']:.3f}")
        c2.metric("Current 12-input R²" if USE_PROFILE12 else "State + household details R²", f"{new['r2']:.3f}")
        if USE_PROFILE12:
            change = new['mae_kwh'] - old['mae_kwh']
            c3.metric("MAE change vs previous", f"{change:+,.0f} kWh/year")
            st.caption("A positive MAE change means more error. The simplified model follows the agreed input list; it is not necessarily more accurate.")
        else:
            c3.metric("Lower error vs original", f"{result['mae_improvement_vs_original']:.1%}")
        st.write(f"{len(profile_schema.USER_FIELDS)} household questions, including state; region is derived automatically. One national model serves all states.")
        if USE_PROFILE12:
            goal = home_profile.REQUESTED_R2_TARGET
            st.write(f"Requested R² target: {goal:.3f}. **{'Met' if new['r2'] >= goal else 'Not met'}.**")
    cols = st.columns(3)
    cols[0].metric("XGBoost test MAE", f"{result['xgboost']['mae_kwh']:,.0f} kWh/year")
    cols[1].metric("Median baseline test MAE", f"{result['baseline']['mae_kwh']:,.0f} kWh/year")
    cols[2].metric("MAE improvement", f"{result['mae_improvement']:.1%}")
    st.caption("MAE means average absolute error: how far predictions are from recorded annual electricity use, on average. Lower is better; individual errors can be larger.")
    st.write(f"Provisional target: at least 15% lower MAE than the baseline. **{'Met' if result['target_met'] else 'Not met'}.** This is an engineering benchmark, not proof of user usefulness.")
    st.caption(f"80% nominal range: observed test coverage {result['test_interval_coverage']:.1%}. Split counts: {result['split_counts']}.")
    metric_keys = ["mae_kwh", "rmse_kwh", "r2"]
    table = {"Metric": ["MAE (kWh)", "RMSE (kWh)", "R²"], "Baseline": [result["baseline"][k] for k in metric_keys], "XGBoost": [result["xgboost"][k] for k in metric_keys]}
    if USE_PRACTICAL:
        table["Previous 17-input model" if USE_PROFILE12 else "Original model"] = [result.get("previous", result["original"])[k] for k in metric_keys]
    st.dataframe(pd.DataFrame(table), hide_index=True)
    if USE_PROFILE12:
        st.markdown("**Predicted versus recorded electricity — 50 test homes**")
        sample = pd.read_csv(REPORTS / "app-vs-actual-2020-sample.csv")
        chart = px.line(sample, x="display_index", y=["recorded_2020_kwh", "app_prediction_kwh"],
                        labels={"display_index": "Household index (not time)", "value": "Annual electricity (kWh)", "variable": ""})
        chart.for_each_trace(lambda t: t.update(
            name="Recorded 2020 electricity" if t.name == "recorded_2020_kwh" else "HomePulse app prediction",
            line=dict(color="#D93932" if t.name == "recorded_2020_kwh" else "#278541",
                      dash="solid" if t.name == "recorded_2020_kwh" else "dash")))
        st.plotly_chart(chart, width="stretch")
        st.caption("Same fixed random sample as the previous model's chart. R² and MAE above use all 3,700 test households, not just these 50.")
    if USE_PRACTICAL:
        with st.expander("Recorded vs predicted electricity — all test households"):
            predictions = pd.read_csv(REPORTS / "test-predictions.csv")
            fig = px.scatter(predictions, x="KWH", y="prediction_kwh", opacity=.35,
                             labels={"KWH": "Recorded annual electricity (kWh)", "prediction_kwh": "Predicted annual electricity (kWh)"})
            maximum = max(predictions.KWH.max(), predictions.prediction_kwh.max())
            fig.add_shape(type="line", x0=0, y0=0, x1=maximum, y1=maximum, line=dict(dash="dash", color="#008b8b"))
            fig.update_xaxes(range=[0, maximum * 1.02])
            fig.update_yaxes(range=[0, maximum * 1.02])
            st.plotly_chart(fig, width="stretch")
            st.caption("The dashed line is perfect agreement. Every test household is included; high-consumption homes have not been removed.")
    st.write("Errors by home type, region and state" if USE_PRACTICAL else "Errors by home type and region")
    subgroups = pd.read_csv(REPORTS / "subgroup-errors.csv")
    st.dataframe(subgroups.assign(dimension=subgroups["dimension"].replace({"TYPEHUQ": "Home type", "REGIONC": "Region"})).rename(columns={"dimension": "Comparison", "group": "Group", "n": "Test homes", "mae_kwh": "Average absolute error (kWh)", "rmse_kwh": "RMSE (kWh)", "r2": "R²", "baseline_mae_kwh": "Baseline average error (kWh)", "mae_improvement": "Error reduction (fraction)", "interval_coverage": "Range coverage (fraction)", "low_support": "Limited sample"}).round(3), hide_index=True, width="stretch")
    st.write("What inputs does the fitted model use?")
    imp = pd.read_csv(REPORTS / "feature-importance.csv")
    if USE_PRACTICAL:
        imp["feature"] = imp.feature.map(profile_schema.LABELS)
    st.plotly_chart(px.bar(imp.sort_values("importance_kwh"), x="importance_kwh", y="feature", orientation="h", labels={"importance_kwh": "Increase in MAE when shuffled (kWh)", "feature": "Input"}), width="stretch")
    st.caption("Global permutation importance on development records, not household-specific attribution or causal effects. Correlated inputs can share or hide importance.")
    with st.expander("Detailed metrics and experiment settings"):
        st.json(result)

with tabs[3]:
    st.subheader("Know what the estimate means")
    st.markdown("""
    - **Data:** EIA RECS 2020 public microdata, version 7. Annual KWH includes solar self-generation.
    - **Scope:** occupied U.S. primary residences represented by the survey, not commercial buildings or worldwide housing.
    - **Time:** the model has no evidence of current-year accuracy. Occupancy, weather and equipment have changed since 2020.
    - **Quality:** EIA includes imputed values, top-coding and survey responses. We do not know true consumption without error.
    - **Fair testing:** survey IDs, weights, bills, expenditure and end-use consumption never enter the predictor allowlist.
    - **Weights:** comparison means describe represented households. Unweighted test metrics describe held-out survey records; weighted sensitivity metrics are also available.
    - **Uncertainty:** prediction ranges and survey-estimate standard errors describe different sources of uncertainty.
    """)
    st.link_button("Official EIA data and codebook", "https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata")
    st.link_button("EIA survey-weight methodology", "https://www.eia.gov/consumption/residential/data/2020/pdf/microdata-guide.pdf")
