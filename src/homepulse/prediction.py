import math
import joblib
import pandas as pd
from .config import FEATURES, NUMERIC, CATEGORIES, MODEL


def validate_profile(profile):
    if set(profile) != set(FEATURES):
        raise ValueError("Provide exactly the required home characteristics")
    for field, (_, low, high) in NUMERIC.items():
        try:
            number = float(profile[field])
        except (ValueError, TypeError):
            raise ValueError(f"{field} must be a number") from None
        if not math.isfinite(number) or not low <= number <= high:
            raise ValueError(f"{field} must be between {low} and {high}")
        if field != "TOTSQFT_EN" and not number.is_integer():
            raise ValueError(f"{field} must be a whole number")
    for field, mapping in CATEGORIES.items():
        if profile[field] not in mapping.values():
            raise ValueError(f"Unrecognized category for {field}")
    if (profile["EQUIPM"] == "No main heating equipment") != (profile["FUELHEAT"] == "No main heating fuel"):
        raise ValueError("Heating equipment and fuel must consistently indicate whether heating is used")
    return pd.DataFrame([profile], columns=FEATURES)


def predict(profile, bundle=None):
    # Load only our locally trained artifact. Never load pickles from a third-party repository.
    bundle = joblib.load(MODEL) if bundle is None else bundle
    frame = validate_profile(profile)
    estimate = max(0., float(bundle["pipeline"].predict(frame)[0]))
    radius = bundle["radius"]
    return {"estimate_kwh": estimate, "lower_kwh": max(0., estimate - radius), "upper_kwh": estimate + radius}
