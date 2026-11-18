"""Monthly state forecasts and an explicit RECS home-profile adjustment."""
import json
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from .config import ROOT

DATABASE = ROOT / "data/homepulse_monthly.sqlite"
REPORTS = ROOT / "reports/monthly"
STATES = json.loads(Path(__file__).with_name("states.json").read_text())
HOME_TYPES = {1: "Mobile home", 2: "Detached house", 3: "Attached house / townhouse",
              4: "Apartment — building with 2–4 apartments", 5: "Apartment — building with 5+ apartments"}
SIZE_EDGES = [200, 1000, 1500, 2000, 2500, 3500, 15001]
SIZE_LABELS = ["200–999 sq ft", "1,000–1,499 sq ft", "1,500–1,999 sq ft",
               "2,000–2,499 sq ft", "2,500–3,499 sq ft", "3,500–15,000 sq ft"]
MIN_SAMPLE = 50
MIN_EFFECTIVE_SAMPLE = 30
LAGS = [3, 4, 5, 6, 12, 13, 14, 15, 24, 36]


def load_store(path=DATABASE):
    with sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True) as con:
        result = {name: pd.read_sql_query(f"SELECT * FROM {name}", con) for name in
                  ["monthly_observations", "forecasts", "profiles", "test_predictions", "test_state_metrics"]}
        result["metadata"] = json.loads(con.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])
    return result


def size_band(area):
    if isinstance(area, bool):
        raise ValueError("Enter a home size from 200 to 15,000 square feet.")
    try:
        area = float(area)
    except (TypeError, ValueError):
        raise ValueError("Enter a numeric home size.") from None
    if not np.isfinite(area) or not 200 <= area <= 15000:
        raise ValueError("Enter a home size from 200 to 15,000 square feet.")
    return SIZE_LABELS[int(np.searchsorted(SIZE_EDGES, area, side="right") - 1)]


def profile_adjustment(profiles, state, home_type, area):
    """Joint type-size weighted means, with disclosed geography fallback.

    No independent multipliers are multiplied together, no model is fitted,
    and low-support groups do not silently produce personalized estimates.
    """
    if state not in STATES or home_type not in HOME_TYPES:
        raise ValueError("Choose a supported state and house type.")
    band = size_band(area)
    region = STATES[state]["region"]
    scopes = [("State", STATES[state]["name"], profiles.loc[profiles.state == state]),
              ("Region", region, profiles.loc[profiles.region == region]),
              ("United States", "United States", profiles)]
    for level, geography, reference in scopes:
        peers = reference.loc[(reference.home_type == home_type) & (reference.size_band == band)]
        weights = peers.weight.to_numpy(dtype=float)
        neff = float(weights.sum() ** 2 / np.square(weights).sum()) if len(weights) else 0.
        if len(peers) < MIN_SAMPLE or neff < MIN_EFFECTIVE_SAMPLE:
            continue
        profile_mean = float(np.average(peers.kwh, weights=weights))
        reference_mean = float(np.average(reference.kwh, weights=reference.weight))
        return {"factor": profile_mean / reference_mean, "sample_n": len(peers),
                "effective_n": neff, "level": level, "geography": geography,
                "size_band": band, "profile_mean_annual_kwh": profile_mean,
                "reference_mean_annual_kwh": reference_mean}
    raise ValueError("Too few comparable survey homes for this house type and size. Try a better-supported profile; no estimate has been calculated.")


def estimate_home(store, state, month, home_type, area):
    adj = profile_adjustment(store["profiles"], state, home_type, area)
    rows = store["forecasts"].loc[(store["forecasts"].state == state) & (store["forecasts"].month == month)]
    if len(rows) != 1:
        raise ValueError("Choose one of the supported estimate months.")
    row = rows.iloc[0]
    if row.customer_count_assumption <= 0:
        raise ValueError("A positive residential customer count is required.")
    account_kwh = float(row.xgboost_mwh * 1000 / row.customer_count_assumption)
    benchmark_kwh = float(row.seasonal_mean_mwh * 1000 / row.customer_count_assumption)
    return {**adj, "state": state, "month": month, "home_type": HOME_TYPES[home_type],
            "area_sqft": float(area), "estimate_kwh": account_kwh * adj["factor"],
            "seasonal_estimate_kwh": benchmark_kwh * adj["factor"],
            "account_kwh": account_kwh, "state_sales_mwh": float(row.xgboost_mwh),
            "customer_count_assumption": int(row.customer_count_assumption),
            "latest_observation_month": row.latest_observation_month,
            "training_target_end": row.training_target_end}


def make_features(data):
    """Same predictors as the frozen feasibility study; future targets may be null."""
    frames = []
    for state, source in data.groupby("state", sort=True):
        g = source.sort_values("date").copy()
        y = g.sales_mwh
        for k in LAGS:
            g[f"lag_{k}"] = y.shift(k)
        g["recent_mean"] = y.shift(3).rolling(12).mean()
        g["prior_mean"] = y.shift(15).rolling(12).mean()
        g["recent_std_ratio"] = y.shift(3).rolling(12).std() / g.recent_mean
        for k in LAGS:
            g[f"relative_lag_{k}"] = g[f"lag_{k}"] / g.recent_mean
        g["annual_growth"] = g.recent_mean / g.prior_mean
        g["recent_3_growth"] = y.shift(3).rolling(3).mean() / y.shift(15).rolling(3).mean()
        g["log_recent_mean"] = np.log(g.recent_mean)
        g["days"] = g.date.dt.days_in_month
        g["month_sin"] = np.sin(2 * np.pi * g.month / 12)
        g["month_cos"] = np.cos(2 * np.pi * g.month / 12)
        g["latest_observation_month"] = g.date - pd.DateOffset(months=3)
        g["same_month_last_year"] = g.lag_12
        g["same_month_three_year_mean"] = (g.lag_12 + g.lag_24 + g.lag_36) / 3
        frames.append(g)
    f = pd.concat(frames).sort_values(["date", "state"]).reset_index(drop=True)
    cols = ["state", "month", "year", "days", "month_sin", "month_cos", "log_recent_mean",
            "recent_std_ratio", "annual_growth", "recent_3_growth"] + [f"relative_lag_{k}" for k in LAGS]
    return f.loc[f.date >= "2013-01-01"].copy(), cols


def overall_metrics(predictions, field="xgboost"):
    """Pooled state-month scores, without filtering or aggregating test rows."""
    actual = predictions.sales_mwh.to_numpy(dtype=float)
    predicted = predictions[field].to_numpy(dtype=float)
    if not len(actual) or not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("The complete test predictions must be finite and nonempty.")
    residual = predicted - actual
    total_variation = np.square(actual - actual.mean()).sum()
    if total_variation <= 0 or np.abs(actual).sum() <= 0:
        raise ValueError("The test data must have nonzero variation and electricity use.")
    return {"n": len(actual), "pooled_r2": float(1 - np.square(residual).sum() / total_variation),
            "mae_mwh": float(np.abs(residual).mean()),
            "wape": float(np.abs(residual).sum() / np.abs(actual).sum())}


def overall_evidence_chart(predictions):
    """Each point represents one state and month, never a household or U.S. total."""
    g = predictions.sort_values(["state", "date"])
    limit = float(max(g.sales_mwh.max(), g.xgboost.max()) * 1.04)
    fig = go.Figure(go.Scatter(
        x=g.sales_mwh, y=g.xgboost, mode="markers", name="State-month prediction",
        customdata=np.column_stack([g.state, pd.to_datetime(g.date).dt.strftime("%b %Y")]),
        marker=dict(color="#00868B", size=6, opacity=.5),
        hovertemplate="%{customdata[0]} · %{customdata[1]}<br>Actual: %{x:,.0f} MWh<br>Predicted: %{y:,.0f} MWh<extra></extra>"))
    fig.add_trace(go.Scatter(x=[0,limit],y=[0,limit],mode="lines",name="Perfect prediction",
        line=dict(color="#D44840",dash="dash",width=2),hoverinfo="skip"))
    fig.update_layout(template="plotly_white",height=440,
        xaxis_title="Actual sales (MWh)",yaxis_title="Predicted sales (MWh)",
        xaxis=dict(range=[0,limit],tickformat="~s"),yaxis=dict(range=[0,limit],tickformat="~s"),
        margin=dict(t=15,l=25,r=15,b=70),legend=dict(orientation="h",y=-.22,x=0),
        font=dict(color="#143247"))
    return fig


def evidence_chart(predictions, state):
    g = predictions.loc[predictions.state == state].sort_values("date")
    fig = go.Figure()
    for field, label, colour, dash in [
        ("sales_mwh", "EIA actual", "#D44840", "solid"),
        ("xgboost", "XGBoost prediction", "#12857A", "dash"),
        ("same_month_three_year_mean", "Seasonal-average benchmark", "#8B96A4", "dot")]:
        fig.add_trace(go.Scatter(x=g.date, y=g[field], mode="lines+markers", name=label,
            line=dict(color=colour, dash=dash, width=2.5), marker=dict(size=4),
            hovertemplate="%{x|%b %Y}<br>%{y:,.0f} MWh<extra>%{fullData.name}</extra>"))
    fig.update_layout(title=f"{STATES[state]['name']}: predicted versus actual",
        template="plotly_white", height=440, xaxis_title="Target month",
        yaxis_title="State residential electricity sales (MWh)",
        margin=dict(t=60,l=30,r=15,b=80), hovermode="x unified",
        legend=dict(orientation="h", y=-.22, x=0), font=dict(color="#143247"))
    return fig


def outlook_chart(observations, forecasts, state):
    h = observations.loc[observations.state == state].sort_values("date").tail(24)
    f = forecasts.loc[forecasts.state == state].sort_values("month")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=h.date, y=h.sales_mwh, name="EIA actual", mode="lines",line=dict(color="#143247",width=2.5)))
    fig.add_trace(go.Scatter(x=f.month, y=f.xgboost_mwh, name="XGBoost estimate", mode="lines+markers",line=dict(color="#12857A",width=2.5,dash="dash")))
    fig.add_trace(go.Scatter(x=f.month, y=f.seasonal_mean_mwh, name="Seasonal benchmark", mode="lines+markers",line=dict(color="#8B96A4",dash="dot")))
    fig.update_layout(template="plotly_white", height=350, yaxis_title="State residential sales (MWh)",
        xaxis_title="Month", margin=dict(l=20,r=20,t=20,b=70),hovermode="x unified",
        legend=dict(orientation="h",y=-.24))
    return fig
