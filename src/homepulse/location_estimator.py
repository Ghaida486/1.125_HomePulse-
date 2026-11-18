"""A location picker and model predictions for a user-defined home profile."""
import numpy as np
import pandas as pd
import plotly.express as px

from .home_profile import STATES, FEATURES, validate_profile


def estimate_states(profile, bundle):
    """Use the deployed pipeline, changing only state and its derived region."""
    if bundle.get("features") != FEATURES or bundle.get("schema_version") != "home-profile12-v1":
        raise ValueError("The saved model does not match the 12-question form")
    codes = sorted(STATES, key=lambda code: STATES[code]["name"])
    inputs = pd.concat([validate_profile({**profile, "state_postal": code})
                        for code in codes], ignore_index=True)
    values = np.maximum(0., bundle["pipeline"].predict(inputs))
    radius = bundle["radius"]
    result = pd.DataFrame({"state_postal": codes, "estimate_kwh": values})
    result["state_name"] = [STATES[c]["name"] for c in codes]
    result["region"] = inputs.REGIONC
    result["lower_kwh"] = np.maximum(0., values - radius)
    result["upper_kwh"] = values + radius
    for key in ["TYPEHUQ", "TOTSQFT_EN", "NHSLDMEM", "FUELHEAT", "YEARMADERANGE"]:
        result[key] = profile[key]
    return result


def selected_state(event):
    """Only accept known state codes from a Plotly point selection."""
    points = (event or {}).get("selection", {}).get("points", [])
    for point in reversed(points):
        code = point.get("location")
        if not isinstance(code, str) or code not in STATES:
            custom = point.get("customdata", [])
            code = custom[0] if isinstance(custom, (list, tuple)) and custom else None
        if isinstance(code, str) and code in STATES:
            return code
    return None


def choose_map_state():
    import streamlit as st
    code = selected_state(st.session_state.get("home_location_map"))
    if code:
        # A callback runs before widgets are instantiated on the next rerun.
        st.session_state["profile12_state"] = code


def prediction_map(estimates, current_state):
    fig = px.choropleth(
        estimates, locations="state_postal", locationmode="USA-states", scope="usa",
        color="estimate_kwh", hover_name="state_name", color_continuous_scale="YlGnBu",
        custom_data=["state_postal", "TYPEHUQ", "TOTSQFT_EN", "NHSLDMEM", "FUELHEAT",
                     "YEARMADERANGE", "lower_kwh", "upper_kwh"],
        labels={"estimate_kwh": "Estimated kWh / year"},
    )
    selected = estimates.index[estimates.state_postal == current_state].tolist()
    fig.update_traces(
        marker_line_color="white", marker_line_width=1,
        selectedpoints=selected, selected=dict(marker=dict(opacity=1)),
        unselected=dict(marker=dict(opacity=.85)),
        hovertemplate=("<b>%{hovertext}</b><br><b>%{z:,.0f} kWh / year estimated</b>"
                       "<br>%{customdata[1]} · %{customdata[2]:,.0f} sq ft"
                       "<br>%{customdata[3]} resident(s) · Built %{customdata[5]}"
                       "<br>Heating fuel: %{customdata[4]}"
                       "<br>80% target range: %{customdata[6]:,.0f}–%{customdata[7]:,.0f} kWh"
                       "<br>Click to select this state<extra></extra>"),
    )
    fig.update_geos(projection_type="albers usa", showland=True, landcolor="#E4E9EE",
                    bgcolor="rgba(0,0,0,0)", showlakes=False)
    fig.update_layout(
        clickmode="event+select", dragmode=False, height=410,
        margin=dict(l=0, r=0, t=0, b=55), paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#142F43"), uirevision="home-location-map-v1",
        coloraxis_colorbar=dict(orientation="h", x=.5, xanchor="center", y=-.07,
                               len=.85, thickness=14, tickformat=".2s", tickfont=dict(size=11),
                               title=dict(text="Model estimate · kWh / year", side="top")),
    )
    return fig


def home_illustration(home_type):
    """Small original SVG drawings; these illustrate types, not real properties."""
    window = '<rect x="{x}" y="{y}" width="13" height="14" rx="2" fill="#A5DDD8"/>'
    if home_type == "Detached house":
        drawing = '<path d="M35 53 L80 17 L125 53" fill="#DDF2EE" stroke="#007D80" stroke-width="5" stroke-linejoin="round"/><path d="M44 49 V105 H116 V49" fill="#F1F8F7" stroke="#007D80" stroke-width="4"/><rect x="72" y="72" width="18" height="33" rx="2" fill="#007D80"/>'
        drawing += window.format(x=51, y=66) + window.format(x=98, y=66)
    elif home_type == "Attached house / townhouse":
        drawing = ''
        for x in [15, 57, 99]:
            drawing += f'<path d="M{x} 49 L{x+21} 25 L{x+42} 49 V105 H{x} Z" fill="#EDF7F5" stroke="#007D80" stroke-width="3"/><rect x="{x+16}" y="81" width="12" height="24" fill="#007D80"/>'
            drawing += window.format(x=x+15, y=53)
    elif home_type.startswith("Apartment"):
        large = "5+" in home_type
        top = 14 if large else 48
        drawing = f'<rect x="39" y="{top}" width="82" height="{105-top}" rx="3" fill="#EDF7F5" stroke="#007D80" stroke-width="4"/>'
        for y in ([25, 49, 73] if large else [59]):
            for x in [48, 73, 98]:
                drawing += window.format(x=x, y=y)
        drawing += '<rect x="73" y="87" width="14" height="18" fill="#007D80"/>'
    else:
        drawing = '<path d="M22 59 L38 48 H130 L138 62 V94 H22 Z" fill="#EDF7F5" stroke="#007D80" stroke-width="4"/><circle cx="45" cy="99" r="7" fill="#142F43"/><circle cx="115" cy="99" r="7" fill="#142F43"/><rect x="93" y="65" width="17" height="29" fill="#007D80"/>'
        drawing += window.format(x=40, y=66) + window.format(x=63, y=66)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="120" viewBox="0 0 160 120">'
            '<rect width="160" height="120" rx="15" fill="#F3F9F8"/>' + drawing +
            '<path d="M15 108 H145" stroke="#B7D7D6" stroke-width="2"/></svg>')


def render_location_map(profile, bundle):
    import streamlit as st
    st.subheader("Choose a state for your home")
    st.write("Hover over a state for an estimate. Click it to choose your location, then customise your home below.")
    try:
        estimates = estimate_states(profile, bundle)
    except ValueError as exc:
        st.info(f"Complete a consistent home profile to show map estimates: {exc}")
        return
    map_col, home_col = st.columns([3, 1.25])
    with map_col:
        st.plotly_chart(prediction_map(estimates, profile["state_postal"]), width="stretch",
                        key="home_location_map", on_select=choose_map_state, selection_mode="points",
                        config={"displaylogo": False, "scrollZoom": False, "displayModeBar": False})
    with home_col:
        row = estimates.loc[estimates.state_postal == profile["state_postal"]].iloc[0]
        st.markdown(f"### 📍 {row.state_name}")
        st.image(home_illustration(profile["TYPEHUQ"]), width=160)
        st.markdown(f"**{profile['TYPEHUQ']}**")
        st.caption(f"{profile['TOTSQFT_EN']:,} sq ft · {profile['NHSLDMEM']} resident(s) · {row.region}")
        st.metric("Map profile estimate", f"{row.estimate_kwh:,.0f} kWh/year")
        st.caption(f"80% target range: {row.lower_kwh:,.0f}–{row.upper_kwh:,.0f} kWh/year. Overall coverage target, not a guarantee for this home.")
    st.caption("Colours are model estimates for the same home profile in each state, based on 2020 data. Your details stay fixed; only state and its region change. These are not observed state averages or forecasts of moving-home savings.")
    st.caption("The map does not identify an address or infer a real property's features. Use the State menu below for small states or keyboard access.")
