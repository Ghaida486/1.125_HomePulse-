import joblib
import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from homepulse import home_profile as h
from homepulse.location_estimator import estimate_states, prediction_map, selected_state


def profile():
    return {"state_postal": "MA", "TYPEHUQ": "Detached house", "TOTSQFT_EN": 1800,
            "YEARMADERANGE": "2000-2009", "NHSLDMEM": 3, "EQUIPM": "Central furnace",
            "FUELHEAT": "Natural gas", "ACEQUIPM_PUB": "Central AC / central heat pump",
            "TEMPHOME": 68, "TEMPHOMEAC": 75, "SWIMPOOL": "No", "RECBATH": "No"}


def test_map_selection_accepts_only_supported_locations():
    assert selected_state({"selection": {"points": [{"location": "CA"}]}}) == "CA"
    assert selected_state({"selection": {"points": [{"customdata": ["TX", "Detached house"]}]}}) == "TX"
    for event in [None, {}, {"selection": {"points": []}},
                  {"selection": {"points": [{"location": "XX"}]}},
                  {"selection": {"points": [{"location": {"bad": 1}}]}}]:
        assert selected_state(event) is None


@pytest.mark.skipif(not h.MODEL.exists(), reason="Requires the deployed artifact")
def test_every_state_map_value_matches_deployed_app_prediction():
    bundle = joblib.load(h.MODEL)
    p = profile()
    rows = estimate_states(p, bundle)
    assert set(rows.state_postal) == set(h.STATES) and len(rows) == 51
    for _, row in rows.iterrows():
        expected = h.predict({**p, "state_postal": row.state_postal}, bundle)
        for field in ["estimate_kwh", "lower_kwh", "upper_kwh"]:
            assert row[field] == pytest.approx(expected[field], abs=.02)
        assert row.region == h.STATES[row.state_postal]["region"]
        assert row.TYPEHUQ == p["TYPEHUQ"] and row.TOTSQFT_EN == p["TOTSQFT_EN"]
    assert p == profile(), "Map must not mutate a user's profile"
    fig = prediction_map(rows, "MA")
    assert list(fig.data[0].locations) == list(rows.state_postal)
    assert np.allclose(fig.data[0].z, rows.estimate_kwh)
    assert "Model estimate" in fig.layout.coloraxis.colorbar.title.text
    assert fig.layout.clickmode == "event+select"
    with pytest.raises(ValueError, match="Heating equipment and fuel"):
        estimate_states({**p, "EQUIPM": "No main heating equipment"}, bundle)
    with pytest.raises(ValueError, match="saved model"):
        estimate_states(p, {**bundle, "schema_version": "wrong"})
    unknown = estimate_states({**p, "YEARMADERANGE": h.UNKNOWN, "TEMPHOME": None}, bundle)
    assert np.isfinite(unknown.estimate_kwh).all()


@pytest.mark.skipif(not h.MODEL.exists(), reason="Requires the deployed artifact")
def test_visual_card_state_and_estimate_stay_in_sync():
    app = AppTest.from_file(str(h.ROOT / "app.py")).run(timeout=60)
    app.radio(key="homepulse_workspace").set_value("Original annual estimator").run(timeout=60)
    app.selectbox(key="profile12_state").select("CA").run(timeout=60)
    app.number_input(key="profile12_TOTSQFT_EN").set_value(1500).run(timeout=60)
    app.button(key="home_card_1").click().run(timeout=60)
    assert not app.exception
    assert app.selectbox(key="profile12_TYPEHUQ").value == "Attached house / townhouse"
    assert app.selectbox(key="profile12_state").value == "CA"
    assert app.number_input(key="profile12_TOTSQFT_EN").value == 1500
    p = {**profile(), "state_postal": "CA", "TOTSQFT_EN": 1500,
         "TYPEHUQ": "Attached house / townhouse"}
    expected = h.predict(p)["estimate_kwh"]
    assert next(m.value for m in app.metric if m.label == "Map profile estimate") == f"{expected:,.0f} kWh/year"
    app.button(key="estimate_home").click().run(timeout=60)
    assert not app.exception and not app.error
    assert next(m.value for m in app.metric if m.label == "Estimated annual electricity") == f"{expected:,.0f} kWh"
    # Invalid edits must hide map predictions instead of leaving an old estimate.
    app.selectbox(key="profile12_EQUIPM").select("No main heating equipment").run(timeout=60)
    assert not any(m.label == "Map profile estimate" for m in app.metric)
    assert any("Heating equipment and fuel" in x.value for x in app.info)
