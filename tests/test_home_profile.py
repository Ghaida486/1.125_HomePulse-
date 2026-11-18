import json

import joblib
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from homepulse import home_profile as h
from homepulse.training import metrics


def example():
    return {"state_postal": "MA", "TYPEHUQ": "Detached house", "TOTSQFT_EN": 1800,
            "YEARMADERANGE": "2000-2009", "NHSLDMEM": 3, "EQUIPM": "Central furnace",
            "FUELHEAT": "Natural gas", "ACEQUIPM_PUB": "Central AC / central heat pump",
            "TEMPHOME": 68, "TEMPHOMEAC": 75, "SWIMPOOL": "No", "RECBATH": "No"}


def test_agreed_fields_reject_appliances_and_derive_location():
    assert set(h.USER_FIELDS) == set(example()) and len(h.FEATURES) == 13
    for field in h.REMOVED:
        with pytest.raises(ValueError, match="12 agreed"):
            h.validate_profile({**example(), field: 1})
    assert h.validate_profile({**example(), "state_postal": "CA"}).REGIONC.iloc[0] == "West"
    with pytest.raises(ValueError, match="state"):
        h.validate_profile({**example(), "state_postal": "XX"})
    with pytest.raises(ValueError):
        h.validate_profile({**example(), "NHSLDMEM": None})
    frame = h.validate_profile({**example(), "YEARMADERANGE": h.UNKNOWN, "TEMPHOME": None})
    assert pd.isna(frame.YEARMADERANGE.iloc[0]) and pd.isna(frame.TEMPHOME.iloc[0])
    frame = h.validate_profile({**example(), "EQUIPM": "No main heating equipment",
                                "FUELHEAT": "No main heating fuel", "ACEQUIPM_PUB": "No air conditioning"})
    assert pd.isna(frame.TEMPHOME.iloc[0]) and pd.isna(frame.TEMPHOMEAC.iloc[0])
    with pytest.raises(ValueError, match="Heating equipment and fuel"):
        h.validate_profile({**example(), "EQUIPM": "No main heating equipment"})


@pytest.mark.skipif(not h.MODEL.exists(), reason="Requires the trained 12-input artifact")
def test_database_model_and_full_benchmark_have_no_appliance_inputs():
    data = h.load_data().set_index("DOEID")
    bundle = joblib.load(h.MODEL)
    assert len(data) == 18496 and data.index.is_unique
    assert not set(data.columns) & h.REMOVED
    assert bundle['features'] == list(bundle['pipeline'].feature_names_in_) == h.FEATURES
    assert not set(h.FEATURES) & (h.REMOVED | {"KWH", "DOEID", "NWEIGHT", "TOTALBTU", "TOTALDOL"})
    scored = pd.read_csv(h.REPORTS / "test-predictions.csv")
    pred = np.maximum(0, bundle['pipeline'].predict(data.loc[scored.DOEID, h.FEATURES]))
    assert np.allclose(pred, scored.prediction_kwh, atol=.01)
    for name, value in metrics(scored.KWH, pred).items():
        assert abs(value - bundle['metrics']['xgboost'][name]) < 1e-5
    manifest = pd.read_csv(h.REPORTS / "split-manifest.csv")
    assert set(scored.DOEID) == set(manifest.loc[manifest.split == "test", "DOEID"])
    result = h.predict(example(), bundle)
    assert np.isfinite(result['estimate_kwh'])
    assert 0 <= result['lower_kwh'] <= result['estimate_kwh'] <= result['upper_kwh']


@pytest.mark.skipif(not h.MODEL.exists(), reason="Requires the trained 12-input artifact")
def test_app_has_twelve_inputs_and_uses_the_twelve_input_model():
    app = AppTest.from_file(str(h.ROOT / "app.py")).run(timeout=60)
    app.radio(key="homepulse_workspace").set_value("Original annual estimator").run(timeout=60)
    assert not app.exception
    questions = [x for x in app.selectbox if str(x.key).startswith('profile12_')]
    numbers = [x for x in app.number_input if str(x.key).startswith('profile12_')]
    assert len(questions) + len(numbers) == 12
    labels = [x.label for x in questions + numbers]
    assert not any(any(word in label.lower() for word in ['dryer', 'refrigerator', 'freezer', 'water-heater']) for label in labels)
    app.button(key="estimate_home").click().run(timeout=60)
    assert not app.exception and not app.error
    value = next(x.value for x in app.metric if x.label == 'Estimated annual electricity')
    assert value == f"{h.predict(example())['estimate_kwh']:,.0f} kWh"
    reported = next(x.value for x in app.metric if x.label == 'Current 12-input R²')
    assert reported == f"{joblib.load(h.MODEL)['metrics']['xgboost']['r2']:.3f}"
    assert any('Not met' in x.value and '0.900' in x.value for x in app.markdown)
