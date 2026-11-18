"""Survey-weighted U.S. map data and Plotly figures, separate from prediction."""
import numpy as np
import pandas as pd
import plotly.express as px

from .data import weighted_comparison
from .practical import STATES


def geographic_summary(records, level="State", home_type="All home types"):
    """Pool household weights within each geography; never average state means."""
    if level not in {"State", "Region"}:
        raise ValueError("Map level must be State or Region")
    data = records if home_type == "All home types" else records[records.TYPEHUQ == home_type]
    if data.empty:
        return pd.DataFrame(), pd.DataFrame(), None
    national = float(np.average(data.KWH, weights=data.NWEIGHT))
    field = "state_postal" if level == "State" else "REGIONC"
    summary = weighted_comparison(data, field)
    summary["difference_percent"] = 100 * (summary.mean_kwh / national - 1)
    summary["support"] = np.where(
        summary.low_support | ~np.isfinite(summary.rse_percent),
        "Limited comparison support", "Meets sample / RSE screen")
    state_rows = pd.DataFrame([
        {"state_postal": code, "state_name": info["name"], "region": info["region"]}
        for code, info in STATES.items()
    ])
    join_field = "state_postal" if level == "State" else "region"
    tiles = state_rows.merge(summary, left_on=join_field, right_on="group", how="left", validate="many_to_one")
    tiles["map_area"] = tiles.state_name if level == "State" else tiles.region
    tiles["support"] = tiles.support.fillna("No survey homes for this selection")
    tiles["rse_label"] = tiles.rse_percent.map(lambda x: f"{x:.1f}%" if np.isfinite(x) else "Unavailable")
    return summary, tiles, national


def electricity_map(tiles, measure="Annual household use (kWh)", level="State"):
    difference = measure == "Difference from U.S. average (%)"
    field = "difference_percent" if difference else "mean_kwh"
    limits = None
    if difference:
        extent = max(1.0, float(tiles[field].abs().max()))
        limits = [-extent, extent]
    fig = px.choropleth(
        tiles.dropna(subset=[field]), locations="state_postal", locationmode="USA-states",
        scope="usa", color=field, hover_name="map_area",
        custom_data=["state_name", "region", "mean_kwh", "difference_percent",
                     "sample_households", "represented_households", "rse_label", "support"],
        color_continuous_scale="RdBu_r" if difference else "YlGnBu",
        range_color=limits,
        labels={field: "Difference from U.S. (%)" if difference else "kWh / household / year"},
    )
    # Region means repeat across member-state shapes purely to draw each region.
    area = "Region" if level == "Region" else "State"
    fig.update_traces(
        marker_line_color="white", marker_line_width=.7,
        hovertemplate=("<b>%{hovertext}</b><br>State: %{customdata[0]}<br>Region: %{customdata[1]}"
                       f"<br>{area} mean: %{{customdata[2]:,.0f}} kWh / household / year"
                       "<br>Difference from U.S.: %{customdata[3]:+.1f}%"
                       f"<br>{area} survey homes: %{{customdata[4]:,.0f}}"
                       "<br>Households represented: %{customdata[5]:,.0f}"
                       "<br>Sampling RSE: %{customdata[6]}<br>%{customdata[7]}<extra></extra>"),
    )
    fig.update_geos(projection_type="albers usa", showland=True, landcolor="#E4E9EE",
                    bgcolor="rgba(0,0,0,0)", showlakes=False)
    fig.update_layout(
        height=510, margin=dict(l=0, r=0, t=10, b=60), font=dict(color="#142F43"),
        paper_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar=dict(orientation="h", x=.5, xanchor="center", y=-.06,
                                 len=.9, thickness=17, tickformat="+.0f" if difference else ".2s",
                                 ticksuffix="%" if difference else "", tickangle=0, tickfont=dict(size=11),
                                 title=dict(text="Difference from U.S. average" if difference else "kWh / household / year", side="top")),
    )
    return fig


def render_map(records):
    import streamlit as st

    st.subheader("U.S. household electricity map")
    st.write("Explore how average annual household electricity use differs across the country.")
    a, b = st.columns(2)
    level = a.radio("Map by", ["State", "Region"], horizontal=True, key="electricity_map_level")
    home_type = b.selectbox("Homes shown on map", ["All home types", *sorted(records.TYPEHUQ.dropna().unique())], key="electricity_map_home_type")
    measure = st.radio("Colour shows", ["Annual household use (kWh)", "Difference from U.S. average (%)"], horizontal=True, key="electricity_map_measure")
    summary, tiles, national = geographic_summary(records, level, home_type)
    if summary.empty:
        st.info("No survey homes match this selection.")
        return
    st.caption(f"U.S. weighted average for this home-type selection: {national:,.0f} kWh per household per year. RECS 2020.")
    st.plotly_chart(electricity_map(tiles, measure, level), width="stretch", key="electricity_map",
                    config={"displaylogo": False, "toImageButtonOptions": {"filename": "HomePulse_US_electricity_map", "scale": 2}})
    st.caption("Hover to inspect values. Use the map toolbar to zoom, reset or download. Alaska and Hawaii appear as insets. Grey areas have no matching survey records.")
    if level == "Region":
        st.caption("Region view pools household survey weights across each Census region. Every state within a region displays the same regional mean.")
    st.caption("Colours show recorded survey averages, not model predictions or total state electricity demand. Differences may reflect home size, heating fuels, climate and occupancy; they do not measure efficiency.")
    limited = int(summary.low_support.sum())
    if limited:
        st.info(f"{limited} mapped group(s) have fewer than 50 survey homes or sampling RSE above 30%. Hover for support details.")
    with st.expander("Map values and survey support"):
        shown = summary.copy()
        if level == "State":
            shown["group"] = shown.group.map(lambda s: STATES[s]["name"])
        st.dataframe(shown.rename(columns={"group": level, "mean_kwh": "Average kWh / household / year",
                      "difference_percent": "Difference from U.S. (%)", "sample_households": "Survey homes",
                      "represented_households": "Households represented", "standard_error": "Sampling standard error (kWh)",
                      "rse_percent": "Sampling RSE (%)", "low_support": "Limited support", "support": "Support"}).round(2),
                     hide_index=True, width="stretch")
        st.download_button("Download map data (CSV)", shown.to_csv(index=False), "homepulse-map-data.csv", "text/csv")
        st.caption("NWEIGHT determines the means. Sampling errors use the 60 EIA jackknife replicate weights.")
    st.link_button("About the RECS 2020 data", "https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata")
