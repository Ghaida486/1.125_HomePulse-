"""Four-input HomePulse monthly outlook and state-model evidence."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from .monthly import (DATABASE, STATES, HOME_TYPES, load_store, estimate_home,
                      evidence_chart, outlook_chart, overall_metrics, overall_evidence_chart)
from .location_estimator import home_illustration
from .monthly_map import render_state_picker
from .dashboard_theme import (inject_theme, render_header, section_label,
                              dark_home_illustration, style_chart)


HOME_TYPE_DESCRIPTIONS = {
    2: "A standalone house with no shared walls with neighbouring homes.",
    3: "A house that shares at least one side wall with another home, such as a townhouse or row house.",
    4: "The building contains 2–4 separate apartments. This is the number of apartments in the whole building, not the number of bedrooms in yours.",
    5: "Includes buildings with 5, 50, 100 or more apartments. Count apartments in the building, not bedrooms in yours.",
    1: "A mobile or manufactured home, even if permanently installed on a site.",
}

@st.cache_data
def cached_store(path, modified):
    return load_store(path)


def month_label(month):
    return pd.Timestamp(month).strftime("%B %Y")


def render_monthly():
    inject_theme()
    render_header()
    if not DATABASE.exists():
        st.error("The monthly data snapshot has not been prepared. Run scripts/build_monthly.py first.")
        return
    store = cached_store(str(DATABASE), DATABASE.stat().st_mtime_ns)
    meta = store["metadata"]
    states = sorted(STATES, key=lambda code: STATES[code]["name"])
    months = meta["estimate_months"]
    controls, content = st.columns([1, 3.15], gap="large")
    with controls:
        with st.container(key="hp-control-panel"):
            section_label("MAKE IT YOURS", "Your home profile", "Four details. A monthly planning estimate.")
            state = st.selectbox("State", states, index=states.index("MA"),
                format_func=lambda code: STATES[code]["name"], key="monthly_state")
            month = st.selectbox("Estimate month", months, index=len(months)-1,
                format_func=month_label, key="monthly_month")
            home_type = st.selectbox("House type", [2, 3, 4, 5, 1],
                format_func=lambda t: HOME_TYPES[t], key="monthly_type",
                help="Detached houses have no shared walls. Attached houses, such as townhouses, share a side wall. For apartments, choose the total number of apartments in the building, not the number of bedrooms in your apartment.")
            st.caption(f"**{HOME_TYPES[home_type]}:** {HOME_TYPE_DESCRIPTIONS[home_type]}")
            is_apartment = home_type in (4, 5)
            area_label = "Your apartment size (sq ft)" if is_apartment else "Home size (sq ft)"
            area = st.number_input(area_label, min_value=200, max_value=15000,
                value=1800, step=50, key="monthly_area",
                help="For apartments, enter your own unit's area. RECS uses energy-consuming floor area, including relevant basements and conditioned attics/garages.")
            if is_apartment:
                st.caption("**For your apartment only:** enter its floor area, not the whole building. Example: an 800 sq ft apartment in a 100-apartment building → enter 800.")
            st.caption("Change any detail to update the estimate. Example home details are prefilled.")
        st.caption(f"EIA observations through {month_label(meta['latest_eia_observation'])}. Outcomes for the estimate months are not yet in this data snapshot.")
    with content:
        home_tab, results_tab, method_tab = st.tabs(["Home estimate", "Overall results", "How it works"])
        with home_tab:
            _render_home(store, state, month, home_type, area)
        with results_tab:
            _render_results(store, meta, state)
        with method_tab:
            _render_method(meta)
    st.markdown('<div class="hp-footer"><span>HomePulse · MIT 1.125 · Ghaida Aljuhani</span>'
                '<span>Built on EIA electricity data and RECS household profiles</span></div>', unsafe_allow_html=True)


def _render_home(store, state, month, home_type, area):
    render_state_picker(state)
    try:
        result = estimate_home(store, state, month, home_type, area)
    except ValueError as error:
        st.info(str(error))
    else:
        with st.container(key="hp-estimate-card"):
            image_col, output_col = st.columns([1, 4])
            with image_col:
                st.image(dark_home_illustration(home_illustration(HOME_TYPES[home_type])), width=125)
            with output_col:
                st.markdown(f"**{STATES[state]['name']} · {month_label(month)}**")
                st.metric("Estimated monthly electricity", f"{result['estimate_kwh']:,.0f} kWh")
                if home_type in (4, 5):
                    st.caption("**Electricity estimate for your apartment only.**")
                st.caption(f"{HOME_TYPES[home_type]} · {area:,} sq ft · XGBoost with a survey-based home adjustment")
            st.info("Planning estimate: household-level accuracy has not yet been validated for these future months. The state model's R² does not measure accuracy for your home.")
        section_label("THE COMPARISON", "Put your estimate in context")
        a, b = st.columns(2)
        a.metric("State average per account (estimated)", f"{result['account_kwh']:,.0f} kWh")
        b.metric("Home estimate using seasonal benchmark", f"{result['seasonal_estimate_kwh']:,.0f} kWh")
        st.caption("The seasonal-average method had lower errors than XGBoost in the historical state-level test. Both estimates above use the same customer-count assumption and home adjustment.")
        fig = go.Figure(go.Bar(x=["State account average", "Your home profile"],
            y=[result["account_kwh"], result["estimate_kwh"]], marker_color=["#7DB7FF", "#67E8C4"],
            text=[f"{result['account_kwh']:,.0f}", f"{result['estimate_kwh']:,.0f}"],textposition="outside",
            hovertemplate="%{x}<br>%{y:,.0f} kWh / month<extra></extra>"))
        fig.update_layout(template="plotly_white",height=300,yaxis_title="Estimated kWh for the selected month",
            margin=dict(t=30,b=30,l=20,r=20),yaxis_range=[0,max(result["account_kwh"],result["estimate_kwh"])*1.25])
        st.plotly_chart(style_chart(fig),width="stretch",key="home_month_comparison",config={"displaylogo":False})
        with st.expander("Where this home estimate comes from"):
            st.write(f"The home adjustment is **{result['factor']:.2f}×**, calculated from **{result['sample_n']:,} survey homes** in **{result['geography']}** with the same house type and size band ({result['size_band']}).")
            if result["level"] != "State":
                st.write("The state group was too small, so this estimate uses a broader geographic comparison with the same house type and size band.")
            st.write(f"State electricity estimate: **{result['state_sales_mwh']:,.0f} MWh**. Residential account count: **{result['customer_count_assumption']:,}**, held constant from **{month_label(result['latest_observation_month'])}**.")
            st.code(f"{result['state_sales_mwh']:,.0f} MWh × 1,000 ÷ {result['customer_count_assumption']:,} accounts × {result['factor']:.4f}\n≈ {result['estimate_kwh']:,.0f} kWh for the selected month",language=None)
            st.caption("Type and size are matched jointly. Annual 2020 survey differences are assumed to apply to the selected month. Occupancy, equipment and weather for your own home are not specified. No household prediction range has been calibrated.")
        export={**result,"household_accuracy_validated":False,"method":"State XGBoost forecast / assumed customer count × RECS profile ratio"}
        st.download_button("Download this estimate",pd.DataFrame([export]).to_csv(index=False),
            file_name=f"homepulse-{state}-{month}.csv",mime="text/csv")
    section_label("THE BIGGER PICTURE", f"Electricity outlook for {STATES[state]['name']}")
    st.plotly_chart(style_chart(outlook_chart(store["monthly_observations"],store["forecasts"],state)),
        width="stretch",key="state_outlook",config={"displaylogo":False})
    st.caption("This chart shows statewide residential sales in MWh. Forecasts use information dated three months before each target month. The household estimate above is in kWh.")


def _render_results(store, meta, state):
    section_label("TESTED ON LATER MONTHS", "Overall XGBoost performance")
    st.write("**50 states + Washington, D.C. · January 2024–August 2026**")
    st.caption("All 1,632 later-period state-month predictions. These scores measure statewide residential electricity sales, not individual homes or a single U.S. total.")
    predictions = store["test_predictions"]
    overall = overall_metrics(predictions)
    overall_baseline = overall_metrics(predictions, "same_month_three_year_mean")
    a,b,c=st.columns(3)
    a.metric("All states combined: XGBoost R²",f"{overall['pooled_r2']:.3f}")
    b.metric("Overall absolute-error rate (WAPE)",f"{overall['wape']:.1%}")
    c.metric("Test predictions",f"{overall['n']:,}")
    st.plotly_chart(style_chart(overall_evidence_chart(predictions)),width="stretch",key="xgboost_overall_test",
        config={"displaylogo":False,"toImageButtonOptions":{"filename":"HomePulse_overall_XGBoost","scale":2}})
    st.caption("Each dot is one state and month. Dots near the dashed line have predictions close to actual EIA sales. All test observations are shown; home selections do not change this graph.")
    st.dataframe(pd.DataFrame({"Method":["XGBoost","Seasonal-average benchmark"],
        "Overall R²":[overall["pooled_r2"],overall_baseline["pooled_r2"]],
        "Average absolute error (MWh)":[overall["mae_mwh"],overall_baseline["mae_mwh"]],
        "Absolute-error rate (%)":[100*overall["wape"],100*overall_baseline["wape"]]}).round(3),hide_index=True,width="stretch")
    st.caption("The seasonal-average benchmark performed better overall. WAPE is total absolute error divided by total actual sales; R² is not percentage accuracy.")
    st.write(f"The combined R² includes large differences between states. Median within-state XGBoost R² was **{meta['historical_test']['xgboost']['median_state_r2']:.3f}**. The household adjustment remains unvalidated.")
    st.download_button("Download all test predictions",predictions.to_csv(index=False),
        "homepulse-overall-state-backtest.csv","text/csv")
    metrics = store["test_state_metrics"]
    x=metrics.loc[(metrics.state==state)&(metrics.model=="xgboost")].iloc[0]
    baseline=metrics.loc[(metrics.state==state)&(metrics.model=="same_month_three_year_mean")].iloc[0]
    with st.expander(f"State breakdown · {STATES[state]['name']}"):
        a,b=st.columns(2)
        a.metric("Selected-state XGBoost R²",f"{x.r2:.3f}")
        b.metric("Selected-state error rate (WAPE)",f"{x.wape:.1%}")
        st.plotly_chart(style_chart(evidence_chart(predictions,state)),width="stretch",key="xgboost_state_test",
            config={"displaylogo":False,"toImageButtonOptions":{"filename":f"HomePulse_{state}_XGBoost","scale":2}})
        st.caption("Solid blue = EIA actual sales. Dashed mint = XGBoost predictions. Dotted amber = average of the same month in the preceding three years.")
        st.dataframe(pd.DataFrame({"Method":["XGBoost","Seasonal-average benchmark"],
            "State R²":[x.r2,baseline.r2],"Average absolute error (MWh)":[x.mae_mwh,baseline.mae_mwh],
            "Absolute-error rate (%)":[100*x.wape,100*baseline.wape]}).round(3),hide_index=True,width="stretch")
        st.download_button("Download this state's test predictions",predictions.loc[predictions.state==state].to_csv(index=False),f"homepulse-{state}-state-backtest.csv","text/csv")
    st.caption("Historical tests use current revised data and an assumed publication delay, not reconstructed historical releases.")
    with st.expander("Training and testing details"):
        st.markdown("""- Initial training: January 2013–September 2021.
- Six configurations compared on January 2022–September 2023.
- Chosen by average state error, then refitted through September 2023.
- Fixed model tested on 1,632 later state-months, January 2024–August 2026.
- Each prediction uses sales from at least three months earlier. No future weather, bills or contemporaneous revenue enter the model.
- The displayed upcoming estimates refit the same selected configuration at each month's data cutoff; their actual outcomes are not yet in the snapshot.
- Household adjustments have not been evaluated against future individual-home consumption.""")


def _render_method(meta):
    section_label("FROM DATA TO ESTIMATE", "A transparent path to your estimate")
    st.markdown('''<div class="hp-flow">
    <div class="hp-flow-card"><b>01 / FORECAST</b><h4>Start with the state</h4><p>XGBoost uses calendar patterns and past electricity sales to estimate monthly residential sales in MWh.</p></div>
    <div class="hp-flow-card"><b>02 / CONVERT</b><h4>Find the average</h4><p>Convert MWh to kWh and divide by the last available residential account count, held constant.</p></div>
    <div class="hp-flow-card"><b>03 / PERSONALIZE</b><h4>Apply the home profile</h4><p>A survey-weighted RECS ratio adjusts for house type and size. This step is a calculation, not a second ML model.</p></div>
    </div>''', unsafe_allow_html=True)
    st.code("State forecast (MWh) × 1,000 / assumed accounts × home-profile factor\n= monthly home-profile estimate (kWh)",language=None)
    st.markdown("**What has been tested:** the state forecasts. **What remains to be tested:** future electricity use for individual homes after the profile adjustment.")
    with st.expander("Sources, sample support and assumptions"):
        st.write("EIA-861M: 10,200 state-months, January 2010–August 2026. The 2026 observations are preliminary. All 50 states and D.C. are included.")
        st.write("RECS 2020: 18,496 survey homes. The profile calculation excludes 645 identified on-site solar homes because RECS KWH includes self-generation. Solar status is not collected for apartments; some mismatch remains.")
        st.write("A group needs at least 50 survey homes and an effective weighted sample of 30. We try the state, then Census region, then the U.S. If no group meets this rule, no personalized estimate is returned.")
        st.write("RECS covers occupied primary residences; electricity accounts also cover other residential situations. The adjustment is a planning approximation. It assumes annual type/size differences remain applicable across months and years.")
        st.write("These estimates do not model a particular home's solar system, equipment, occupancy or efficiency improvements.")
    st.link_button("EIA monthly state electricity data",meta["eia_url"])
    st.link_button("RECS household survey data",meta["recs_url"])
    st.caption("Architecture: EIA data → pandas preparation → offline XGBoost training and evaluation → saved forecasts in SQLite. RECS profiles join at the household adjustment; Streamlit and Plotly display the results.")
