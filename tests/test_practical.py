import json
import joblib
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from homepulse import practical as p
from homepulse.config import RAW
from homepulse.training import metrics


def profile():
    return {"state_postal": "MA", "TYPEHUQ": "Detached house", "TOTSQFT_EN": 1800,
            "YEARMADERANGE": "2000-2009", "NHSLDMEM": 3, "EQUIPM": "Central furnace",
            "FUELHEAT": "Natural gas", "ACEQUIPM_PUB": "Central AC / central heat pump",
            "FUELH2O": "Natural gas", "NUMFRIG": 1, "NUMFREEZ": 0,
            "DRYRFUEL": "Electricity", "DRYRUSE": 3, "TEMPHOME": 68,
            "TEMPHOMEAC": 75, "SWIMPOOL": "No", "RECBATH": "No"}


def test_state_derivation_and_input_contract():
    assert len(p.USER_FIELDS) == 17 and len(p.FEATURES) == 18
    assert len(p.STATES) == 51
    for state, region in [("MA", "Northeast"), ("TX", "South"), ("CA", "West"), ("IL", "Midwest"), ("DC", "South")]:
        frame = p.validate_profile({**profile(), "state_postal": state})
        assert frame.REGIONC.iloc[0] == region
    with pytest.raises(ValueError, match="state"):
        p.validate_profile({**profile(), "state_postal": "XX"})
    assert not set(p.FEATURES) & {"KWH", "TOTALBTU", "TOTALDOL", "DOEID", "NWEIGHT", "BA_climate", "HDD65", "CDD65"}


def test_unknown_values_and_absent_equipment():
    frame = p.validate_profile({**profile(), "FUELH2O": p.UNKNOWN, "TEMPHOME": None})
    assert pd.isna(frame.FUELH2O.iloc[0]) and pd.isna(frame.TEMPHOME.iloc[0])
    no_equipment = {**profile(), "EQUIPM": "No main heating equipment", "FUELHEAT": "No main heating fuel",
                    "ACEQUIPM_PUB": "No air conditioning", "DRYRFUEL": "No clothes dryer"}
    frame = p.validate_profile(no_equipment)
    assert pd.isna(frame.TEMPHOME.iloc[0]) and pd.isna(frame.TEMPHOMEAC.iloc[0])
    assert frame.DRYRUSE.iloc[0] == 0
    with pytest.raises(ValueError, match="Heating equipment and fuel"):
        p.validate_profile({**profile(), "EQUIPM": "No main heating equipment"})
    with pytest.raises(ValueError):
        p.validate_profile({**profile(), "TOTSQFT_EN": float("inf")})


@pytest.mark.skipif(not RAW.exists(), reason="Requires official source data")
def test_cleaning_retains_cohort_and_codebook_absence():
    raw = pd.read_csv(RAW, low_memory=False)
    clean = p.clean_practical_records(raw)
    assert len(clean) == 18496 and clean.DOEID.is_unique
    assert clean.loc[raw.DRYRFUEL == -2, "DRYRFUEL"].eq("No clothes dryer").all()
    assert clean.loc[raw.DRYRUSE == -2, "DRYRUSE"].eq(0).all()
    assert clean.loc[raw.TEMPHOME == -2, "TEMPHOME"].isna().all()
    assert clean.loc[raw.SWIMPOOL == -2, "SWIMPOOL"].eq("No").all()


@pytest.mark.skipif(not p.MODEL.exists(), reason="Requires trained state model")
def test_saved_model_reproduces_full_benchmark_and_public_prediction():
    data = p.load_data().set_index("DOEID")
    scores = pd.read_csv(p.REPORTS / "test-predictions.csv")
    bundle = joblib.load(p.MODEL)
    predicted = np.maximum(0, bundle["pipeline"].predict(data.loc[scores.DOEID, p.FEATURES]))
    assert np.allclose(predicted, scores.prediction_kwh, atol=.01)
    result = metrics(scores.KWH, predicted)
    for k, value in result.items():
        assert abs(value - bundle["metrics"]["xgboost"][k]) < 1e-5
    # Test public profile processing against the exact same prediction engine.
    input_frame = p.validate_profile(profile())
    expected = max(0, float(bundle["pipeline"].predict(input_frame)[0]))
    output = p.predict(profile(), bundle)
    assert output["estimate_kwh"] == expected
    assert 0 <= output["lower_kwh"] <= expected <= output["upper_kwh"]
    assert np.isfinite(p.predict({**profile(), "FUELH2O": p.UNKNOWN, "TEMPHOME": None}, bundle)["estimate_kwh"])


@pytest.mark.skipif(not p.MODEL.exists(), reason="Requires trained state model")
def test_app_state_estimate_matches_saved_model_and_unknowns_work():
    from homepulse import home_profile
    active = home_profile if home_profile.MODEL.exists() else p
    active_profile = {k: v for k, v in profile().items() if k in active.USER_FIELDS}
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=60)
    app.radio(key="homepulse_workspace").set_value("Original annual estimator").run(timeout=60)
    assert not app.exception
    state = next(x for x in app.selectbox if x.label == "State")
    state.select("TX").run(timeout=60)
    app.button(key="estimate_home").click().run(timeout=60)
    assert not app.exception and not app.error
    expected = active.predict({**active_profile, "state_postal": "TX"})["estimate_kwh"]
    actual = next(x.value for x in app.metric if x.label == "Estimated annual electricity")
    assert actual == f"{expected:,.0f} kWh"
    next(x for x in app.selectbox if x.label == "Construction period").select(p.UNKNOWN)
    next(x for x in app.number_input if x.label.startswith("Winter daytime")).set_value(None)
    app.button(key="estimate_home").click().run(timeout=60)
    assert not app.exception and not app.error
    assert any("unknown" in x.value.lower() for x in app.warning)
