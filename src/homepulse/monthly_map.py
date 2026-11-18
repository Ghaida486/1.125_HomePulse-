"""A state picker for the monthly app; map colours describe selection only."""
from collections.abc import Mapping

import plotly.graph_objects as go
import streamlit as st

from .monthly import STATES


MAP_KEY = "monthly_state_map"


def state_from_selection(event):
    """Accept supported codes from either a state polygon or the D.C. marker."""
    if not isinstance(event, Mapping):
        return None
    selection = event.get("selection")
    if not isinstance(selection, Mapping):
        return None
    points = selection.get("points")
    if not isinstance(points, (list, tuple)):
        return None
    for point in reversed(points):
        if not isinstance(point, Mapping):
            continue
        code = point.get("location")
        if isinstance(code, str) and code in STATES:
            return code
        custom = point.get("customdata")
        if isinstance(custom, (list, tuple)) and custom:
            code = custom[0]
            if isinstance(code, str) and code in STATES:
                return code
    return None


def choose_monthly_map_state():
    """Streamlit runs this before the dropdown is recreated on the next rerun.

    Only handle fresh selection events here. Reading old map selections during
    normal rendering would undo later dropdown changes or other home edits.
    """
    code = state_from_selection(st.session_state.get(MAP_KEY))
    if code is not None:
        st.session_state["monthly_state"] = code


def state_picker_figure(current_state):
    if current_state not in STATES:
        raise ValueError("Select a supported U.S. state or Washington, D.C.")
    codes = sorted(STATES)
    fig = go.Figure(go.Choropleth(
        locations=codes, locationmode="USA-states",
        z=[int(code == current_state) for code in codes], zmin=0, zmax=1,
        colorscale=[[0, "#29445B"], [1, "#67E8C4"]], showscale=False,
        customdata=[[code, STATES[code]["name"]] for code in codes],
        marker_line_color="#718CA3", marker_line_width=.8,
        selectedpoints=[codes.index(current_state)],
        selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)),
        hovertemplate="<b>%{customdata[1]}</b><br>Click to select this location<extra></extra>",
        name="Select a state",
    ))
    # D.C. is geographically tiny: this marker provides a larger click target.
    fig.add_trace(go.Scattergeo(
        lon=[-77.0369], lat=[38.9072], mode="markers+text", text=["DC"],
        textposition="bottom right", textfont=dict(color="#D5E6F4", size=11),
        marker=dict(size=10, color="#67E8C4" if current_state == "DC" else "#7DB7FF",
                    line=dict(color="#0B1220", width=1.5)),
        customdata=[["DC", STATES["DC"]["name"]]],
        selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)),
        hovertemplate="<b>Washington, D.C.</b><br>Click to select this location<extra></extra>",
        name="Washington, D.C.", showlegend=False,
    ))
    fig.update_geos(scope="usa", projection_type="albers usa", showland=True,
        landcolor="#172B3D", bgcolor="#111D2C", showlakes=False,
        showsubunits=False, showcountries=False, showcoastlines=False)
    fig.update_layout(template="plotly_dark", height=330,
        margin=dict(l=0, r=0, t=4, b=0), paper_bgcolor="#111D2C",
        font=dict(color="#C3D3E0"), hoverlabel=dict(bgcolor="#22374A", bordercolor="#67E8C4"),
        clickmode="event+select", dragmode=False, showlegend=False,
        uirevision="homepulse-monthly-state-map-v1", selectionrevision=current_state)
    return fig


def render_state_picker(current_state):
    with st.expander("Choose your state on the map", expanded=True):
        st.markdown(f"**Selected: {STATES[current_state]['name']}** · Click a state to update your estimate.")
        st.plotly_chart(state_picker_figure(current_state), width="stretch", theme=None,
            key=MAP_KEY, on_select=choose_monthly_map_state, selection_mode="points",
            config={"displaylogo":False, "displayModeBar":False, "scrollZoom":False})
        st.caption("Mint = selected state. Alaska and Hawaii appear as insets; D.C. has a marker. You can also use the State dropdown. Colours show selection, not electricity use.")
