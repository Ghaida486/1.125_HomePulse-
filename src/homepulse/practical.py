"""State-based household profile: codebook cleaning and shared app inference."""
import json
import math
import sqlite3
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .config import ROOT, NUMERIC as ORIGINAL_NUMERIC, CATEGORIES as ORIGINAL_CATEGORIES
from .data import clean_records

MODEL = ROOT / "models/practical-state.joblib"
DATABASE = ROOT / "data/homepulse_state.sqlite"
REPORTS = ROOT / "reports/practical-state"
STATES = json.loads(Path(__file__).with_name("states.json").read_text())
UNKNOWN = "Not sure"
NUMERIC = {
    **ORIGINAL_NUMERIC,
    "DRYRUSE": ("Dryer loads per week", 0, 30),
    "TEMPHOME": ("Winter daytime temperature when home (°F)", 50, 90),
    "TEMPHOMEAC": ("Summer daytime temperature when home (°F)", 50, 90),
}
CATEGORIES = {k: v for k, v in ORIGINAL_CATEGORIES.items() if k not in ["REGIONC", "BA_climate"]}
CATEGORIES.update({
    "FUELH2O": {5: "Electricity", 1: "Natural gas", 2: "Propane", 3: "Fuel oil", 7: "Wood", 8: "Solar thermal", 99: "Other"},
    "DRYRFUEL": {5: "Electricity", 1: "Natural gas", 2: "Propane", -2: "No clothes dryer"},
    "SWIMPOOL": {1: "Yes", 0: "No", -2: "No"},
    "RECBATH": {1: "Yes", 0: "No"},
})
LABELS = {
    "state_postal": "State", "TYPEHUQ": "Home type", "YEARMADERANGE": "Construction period",
    "EQUIPM": "Main heating equipment", "FUELHEAT": "Main heating fuel",
    "ACEQUIPM_PUB": "Main cooling equipment", "FUELH2O": "Water-heater fuel",
    "DRYRFUEL": "Clothes-dryer fuel", "SWIMPOOL": "Private swimming pool", "RECBATH": "Hot tub",
    **{k: v[0] for k, v in NUMERIC.items()}, "REGIONC": "Region (derived from state)",
}
USER_FIELDS = ["state_postal", "TYPEHUQ", "TOTSQFT_EN", "YEARMADERANGE", "NHSLDMEM",
               "EQUIPM", "FUELHEAT", "ACEQUIPM_PUB", "FUELH2O", "NUMFRIG", "NUMFREEZ",
               "DRYRFUEL", "DRYRUSE", "TEMPHOME", "TEMPHOMEAC", "SWIMPOOL", "RECBATH"]
FEATURES = USER_FIELDS + ["REGIONC"]
OPTIONAL = set(USER_FIELDS) - {"state_postal", "TYPEHUQ", "TOTSQFT_EN", "NHSLDMEM"}
EXTRA_FIELDS = ["FUELH2O", "DRYRFUEL", "DRYRUSE", "TEMPHOME", "TEMPHOMEAC", "SWIMPOOL", "RECBATH"]


def clean_practical_records(raw):
    """No learned statistics: retain the original cohort and add explicit labels."""
    df = clean_records(raw)
    extra = raw[["DOEID", "state_postal", *EXTRA_FIELDS]].set_index("DOEID").loc[df.DOEID].reset_index()
    if not extra.state_postal.isin(STATES).all():
        raise ValueError("Unrecognized state in source data")
    df["state_postal"] = extra.state_postal.to_numpy()
    derived = df.state_postal.map(lambda s: STATES[s]["region"])
    if not (derived == df.REGIONC).all():
        raise ValueError("Source region disagrees with state lookup")
    for field in EXTRA_FIELDS:
        source = pd.to_numeric(extra[field], errors="raise")
        if field in CATEGORIES:
            if not source.isin([*CATEGORIES[field], -1, -9]).all():
                raise ValueError(f"Unexpected {field} codes")
            df[field] = source.map(CATEGORIES[field]).astype(object).to_numpy()
        else:
            _, low, high = NUMERIC[field]
            if not (source.between(low, high) | source.isin([-2, -1, -9])).all():
                raise ValueError(f"Unexpected {field} values")
            if field == "DRYRUSE":
                source = source.replace(-2, 0)
            df[field] = source.where(source.between(low, high)).to_numpy()
    return df


def load_data():
    with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True) as conn:
        return pd.read_sql_query("SELECT * FROM households ORDER BY DOEID", conn)


def validate_profile(profile):
    if set(profile) != set(USER_FIELDS):
        raise ValueError("Provide the required household fields")
    p = dict(profile)
    if p["state_postal"] not in STATES:
        raise ValueError("Select a supported U.S. state or District of Columbia")
    for key, (_, low, high) in NUMERIC.items():
        if p[key] is None and key in OPTIONAL:
            p[key] = np.nan
            continue
        try:
            value = float(p[key])
        except (ValueError, TypeError):
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
    if p["DRYRFUEL"] == "No clothes dryer":
        p["DRYRUSE"] = 0.
    p["REGIONC"] = STATES[p["state_postal"]]["region"]
    return pd.DataFrame([p], columns=FEATURES)


def predict(profile, bundle=None):
    bundle = joblib.load(MODEL) if bundle is None else bundle
    if bundle.get("features") != FEATURES:
        raise ValueError("The model and household form use different input schemas")
    frame = validate_profile(profile)
    value = max(0., float(bundle["pipeline"].predict(frame)[0]))
    radius = bundle["radius"]
    return {"estimate_kwh": value, "lower_kwh": max(0., value - radius), "upper_kwh": value + radius}
