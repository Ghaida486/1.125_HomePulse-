"""User-facing fields for the practical state model."""
import streamlit as st
from .practical import STATES, CATEGORIES, NUMERIC, LABELS, USER_FIELDS, OPTIONAL, UNKNOWN


def render_profile():
    st.caption("Example values are prefilled. Change them to describe your home; select ‘Not sure’ or clear an optional number if needed.")
    p = {}

    def category(key, default):
        options = list(dict.fromkeys(CATEGORIES[key].values()))
        if key in OPTIONAL:
            options.append(UNKNOWN)
        p[key] = st.selectbox(LABELS[key], options, index=options.index(default), key="practical_" + key)

    def number(key, default, disabled=False, help=None):
        label, low, high = NUMERIC[key]
        p[key] = st.number_input(label, min_value=low, max_value=high, value=default,
                                 step=10 if key == "TOTSQFT_EN" else 1, key="practical_" + key,
                                 disabled=disabled, placeholder="Not sure", help=help)

    st.markdown("**1 · Home and location**")
    left, right = st.columns(2)
    with left:
        states = sorted(STATES, key=lambda k: STATES[k]["name"])
        p["state_postal"] = st.selectbox("State", states, index=states.index("MA"),
                                        format_func=lambda k: STATES[k]["name"], key="practical_state")
        category("TYPEHUQ", "Detached house")
        number("TOTSQFT_EN", 1800, help="Energy-consuming floor area, including basements and conditioned attics/garages where applicable.")
    with right:
        category("YEARMADERANGE", "2000-2009")
        number("NHSLDMEM", 3, help="7 means seven or more residents.")
        st.caption("Location is taken from your state. No climate-zone lookup is needed. The training data covers homes built through 2020.")

    st.markdown("**2 · Heating, cooling and hot water**")
    left, right = st.columns(2)
    with left:
        category("EQUIPM", "Central furnace")
        category("FUELHEAT", "Natural gas")
        no_heat = p["EQUIPM"] == "No main heating equipment"
        number("TEMPHOME", 68, disabled=no_heat, help="Daytime indoor temperature in winter when someone is home. Ignored when there is no main heating.")
    with right:
        category("ACEQUIPM_PUB", "Central AC / central heat pump")
        category("FUELH2O", "Natural gas")
        no_cooling = p["ACEQUIPM_PUB"] == "No air conditioning"
        number("TEMPHOMEAC", 75, disabled=no_cooling, help="Daytime indoor temperature in summer when someone is home. Ignored when there is no air conditioning.")

    with st.expander("3 · Appliances and outdoor features", expanded=True):
        left, right = st.columns(2)
        with left:
            number("NUMFRIG", 1)
            number("NUMFREEZ", 0)
            category("DRYRFUEL", "Electricity")
            number("DRYRUSE", 3, disabled=p["DRYRFUEL"] == "No clothes dryer", help="Loads dried each week. Automatically zero when there is no dryer.")
        with right:
            category("SWIMPOOL", "No")
            category("RECBATH", "No")
            st.caption("For an apartment, answer ‘No’ for a shared building pool. Select ‘Not sure’ instead of guessing equipment details.")
    assert set(p) == set(USER_FIELDS)
    return p, st.button("Estimate annual electricity", type="primary")
