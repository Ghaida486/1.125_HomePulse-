"""The agreed twelve-question HomePulse input contract, without appliances."""
import math
import sqlite3

import joblib
import numpy as np
import pandas as pd

from .config import ROOT
from . import practical

MODEL = ROOT / "models/home-profile12.joblib"
DATABASE = ROOT / "data/homepulse_profile12.sqlite"
REPORTS = ROOT / "reports/home-profile12"
REQUESTED_R2_TARGET = .9
REMOVED = {"FUELH2O", "NUMFRIG", "NUMFREEZ", "DRYRFUEL", "DRYRUSE"}
STATES, UNKNOWN = practical.STATES, practical.UNKNOWN
USER_FIELDS = [f for f in practical.USER_FIELDS if f not in REMOVED]
FEATURES = USER_FIELDS + ["REGIONC"]
NUMERIC = {f: details for f, details in practical.NUMERIC.items() if f in FEATURES}
CATEGORIES = {f: mapping for f, mapping in practical.CATEGORIES.items() if f in FEATURES}
LABELS = {f: label for f, label in practical.LABELS.items() if f in FEATURES}
OPTIONAL = set(USER_FIELDS) - {"state_postal", "TYPEHUQ", "TOTSQFT_EN", "NHSLDMEM"}


def clean_records(raw):
    """Preserve the established cohort and codebook rules; remove appliance columns."""
    frame = practical.clean_practical_records(raw).drop(columns=sorted(REMOVED))
    assert not set(frame.columns) & REMOVED
    return frame


def load_data():
    with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True) as conn:
        return pd.read_sql_query("SELECT * FROM households ORDER BY DOEID", conn)


def validate_profile(profile):
    if set(profile) != set(USER_FIELDS):
        raise ValueError("Provide exactly the 12 agreed household fields")
    p = dict(profile)
    if p["state_postal"] not in STATES:
        raise ValueError("Select a supported U.S. state or District of Columbia")
    for key, (_, low, high) in NUMERIC.items():
        if p[key] is None and key in OPTIONAL:
            p[key] = np.nan
            continue
        try:
            value = float(p[key])
        except (TypeError, ValueError):
            raise ValueError(f"{LABELS[key]} must be a number") from None
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{LABELS[key]} must be between {low} and {high}")
        if key != "TOTSQFT_EN" and not value.is_integer():
            raise ValueError(f"{LABELS[key]} must be a whole number")
        p[key] = value
    for key, mapping in CATEGORIES.items():
        if p[key] == UNKNOWN and key in OPTIONAL:
            p[key] = np.nan
        elif p[key] not in mapping.values():
            raise ValueError(f"Select a recognized {LABELS[key].lower()}")
    equipment, fuel = p["EQUIPM"], p["FUELHEAT"]
    if pd.notna(equipment) and pd.notna(fuel):
        if (equipment == "No main heating equipment") != (fuel == "No main heating fuel"):
            raise ValueError("Heating equipment and fuel must consistently indicate whether heating is used")
    if equipment == "No main heating equipment":
        p["TEMPHOME"] = np.nan
    if p["ACEQUIPM_PUB"] == "No air conditioning":
        p["TEMPHOMEAC"] = np.nan
    p["REGIONC"] = STATES[p["state_postal"]]["region"]
    return pd.DataFrame([p], columns=FEATURES)


def predict(profile, bundle=None):
    bundle = joblib.load(MODEL) if bundle is None else bundle
    if bundle.get("features") != FEATURES or bundle.get("schema_version") != "home-profile12-v1":
        raise ValueError("The saved model does not match the 12-question form")
    value = max(0., float(bundle["pipeline"].predict(validate_profile(profile))[0]))
    radius = bundle["radius"]
    return {"estimate_kwh": value, "lower_kwh": max(0., value - radius), "upper_kwh": value + radius}
