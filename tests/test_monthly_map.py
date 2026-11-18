"""State selection must update the active form, not overwrite other inputs."""
import pytest
from streamlit.testing.v1 import AppTest

from homepulse import monthly_map
from homepulse.monthly import ROOT, STATES, DATABASE, load_store, estimate_home


def test_map_covers_all_locations_and_highlights_dropdown_state():
    for selected in ["MA", "TX", "AK", "HI", "DC"]:
        fig = monthly_map.state_picker_figure(selected)
        states, dc = fig.data
        assert len(states.locations) == 51
        assert set(states.locations) == set(STATES)
        assert sum(states.z) == 1
        assert states.locations[list(states.z).index(1)] == selected
        assert dc.customdata[0][0] == "DC"
        assert fig.layout.geo.scope == "usa"
        assert fig.layout.geo.projection.type == "albers usa"
        assert not states.showscale
    with pytest.raises(ValueError):
        monthly_map.state_picker_figure("XX")


def test_click_parser_and_empty_selection():
    assert monthly_map.state_from_selection({"selection":{"points":[{"location":"TX"}]}}) == "TX"
    assert monthly_map.state_from_selection({"selection":{"points":[{"customdata":["DC", "Washington, D.C."]}]}}) == "DC"
    for event in [None, {}, {"selection":None}, {"selection":{"points":None}},
                  {"selection":{"points":[]}}, {"selection":{"points":[None]}},
                  {"selection":{"points":[{"location":"XX"}]}},
                  {"selection":{"points":[{"customdata":"CA"}]}}]:
        assert monthly_map.state_from_selection(event) is None


def test_callback_only_changes_location_and_never_resets_on_deselection(monkeypatch):
    session={"monthly_state":"MA", "monthly_month":"2026-10", "monthly_type":5, "monthly_area":1000,
             monthly_map.MAP_KEY:{"selection":{"points":[{"location":"TX"}]}}}
    monkeypatch.setattr(monthly_map.st,"session_state",session)
    monthly_map.choose_monthly_map_state()
    assert session["monthly_state"] == "TX"
    assert (session["monthly_month"],session["monthly_type"],session["monthly_area"]) == ("2026-10",5,1000)
    session[monthly_map.MAP_KEY]={"selection":{"points":[]}}
    monthly_map.choose_monthly_map_state()
    assert session["monthly_state"] == "TX"


def test_dropdown_rerender_updates_map_and_estimate_together():
    app=AppTest.from_file(str(ROOT/"app.py")).run(timeout=60)
    for state in ["TX", "DC", "HI"]:
        app.selectbox(key="monthly_state").select(state).run(timeout=60)
        assert not app.exception and not app.error
        assert any(f"Selected: {STATES[state]['name']}" in item.value for item in app.markdown)
        expected=estimate_home(load_store(DATABASE),state,"2026-11",2,1800)
        assert next(m.value for m in app.metric if m.label=="Estimated monthly electricity") == f"{expected['estimate_kwh']:,.0f} kWh"
