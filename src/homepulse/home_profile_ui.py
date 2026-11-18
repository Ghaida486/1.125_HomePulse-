"""The agreed twelve-question form; appliance inputs are excluded."""
import streamlit as st
from .home_profile import STATES, CATEGORIES, NUMERIC, LABELS, USER_FIELDS, OPTIONAL, UNKNOWN
from .location_estimator import render_location_map, home_illustration


def select_home_type(home_type):
    st.session_state["profile12_TYPEHUQ"] = home_type


def render_profile(bundle=None):
    st.caption("Example values are prefilled. Change them to describe your home; select ‘Not sure’ or clear an optional number if needed.")
    map_container = st.container()
    p = {}

    def category(key, default):
        options = list(dict.fromkeys(CATEGORIES[key].values()))
        if key in OPTIONAL:
            options.append(UNKNOWN)
        p[key] = st.selectbox(LABELS[key], options, index=options.index(default), key="profile12_" + key)

    def number(key, default, disabled=False, help=None):
        label, low, high = NUMERIC[key]
        p[key] = st.number_input(label, min_value=low, max_value=high, value=default,
                                 step=10 if key == "TOTSQFT_EN" else 1, key="profile12_" + key,
                                 disabled=disabled, placeholder="Not sure", help=help)

    st.markdown("**1 · Choose your home type**")
    choices = ["Detached house", "Attached house / townhouse", "Apartment (2-4 units)",
               "Apartment (5+ units)", "Mobile home"]
    short_names = ["Detached", "Townhouse", "2–4 unit building", "5+ unit building", "Mobile home"]
    selected = st.session_state.get("profile12_TYPEHUQ", "Detached house")
    for column, home_type, title in zip(st.columns(5), choices, short_names):
        with column:
            st.image(home_illustration(home_type), width=120)
            st.button(title, key="home_card_" + str(choices.index(home_type)),
                      type="primary" if home_type == selected else "secondary", width="stretch",
                      on_click=select_home_type, args=(home_type,))
    st.caption("Choose the building type. For apartments, floor area and residents refer to your own unit.")
    st.markdown("**2 · Home and location**")
    left, right = st.columns(2)
    with left:
        states = sorted(STATES, key=lambda k: STATES[k]["name"])
        p["state_postal"] = st.selectbox("State", states, index=states.index("MA"),
                                        format_func=lambda k: STATES[k]["name"], key="profile12_state")
        category("TYPEHUQ", "Detached house")
        number("TOTSQFT_EN", 1800, help="Energy-consuming floor area, including basements and conditioned attics/garages where applicable.")
    with right:
        category("YEARMADERANGE", "2000-2009")
        number("NHSLDMEM", 3, help="7 means seven or more residents.")
        st.caption("Location is taken from your state. No climate-zone lookup is needed. The training data covers homes built through 2020.")

    st.markdown("**3 · Heating and cooling**")
    left, right = st.columns(2)
    with left:
        category("EQUIPM", "Central furnace")
        category("FUELHEAT", "Natural gas")
        no_heat = p["EQUIPM"] == "No main heating equipment"
        number("TEMPHOME", 68, disabled=no_heat, help="Daytime indoor temperature in winter when someone is home. Ignored when there is no main heating.")
    with right:
        category("ACEQUIPM_PUB", "Central AC / central heat pump")
        no_cooling = p["ACEQUIPM_PUB"] == "No air conditioning"
        number("TEMPHOMEAC", 75, disabled=no_cooling, help="Daytime indoor temperature in summer when someone is home. Ignored when there is no air conditioning.")

    st.markdown("**4 · Additional features**")
    left, right = st.columns(2)
    with left:
        category("SWIMPOOL", "No")
    with right:
        category("RECBATH", "No")
    st.caption("For an apartment, answer ‘No’ for a shared building pool. Select ‘Not sure’ instead of guessing.")
    assert set(p) == set(USER_FIELDS)
    if bundle is not None:
        with map_container:
            render_location_map(p, bundle)
            st.divider()
    return p, st.button("Estimate annual electricity", type="primary", key="estimate_home")
