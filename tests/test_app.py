from pathlib import Path
from streamlit.testing.v1 import AppTest
from homepulse.config import MODEL
import pytest


@pytest.mark.skipif(not MODEL.exists(), reason="Requires the trained local artifact")
def test_full_user_prediction_and_validation():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=45)
    app.radio(key="homepulse_workspace").set_value("Original annual estimator").run(timeout=45)
    assert not app.exception
    app.button(key="estimate_home").click().run(timeout=45)
    assert not app.exception
    assert not app.error
    assert any(m.label == "Estimated annual electricity" for m in app.metric)
    # Contradictory heating inputs must produce a readable error rather than an estimate.
    heater = next(x for x in app.selectbox if x.label == "Main heating equipment")
    heater.select("No main heating equipment")
    app.button(key="estimate_home").click().run(timeout=45)
    assert not app.exception
    assert any("Heating equipment and fuel" in e.value for e in app.error)
