import hashlib
import json
import sqlite3
import numpy as np
import pandas as pd
from .config import RAW, CODEBOOK, DATABASE, REPORTS, FEATURES, NUMERIC, CATEGORIES, TARGET, REPLICATES, SOURCES


def clean_records(raw):
    """Deterministic codebook translation, not fitted statistical preprocessing."""
    required = ["DOEID", TARGET, "NWEIGHT", *FEATURES, *REPLICATES]
    missing = set(required) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing source columns: {sorted(missing)}")
    df = raw[required].copy()
    if df.DOEID.duplicated().any():
        raise ValueError("Duplicate DOEID records; cannot create independent splits")
    valid = df[TARGET].gt(0) & np.isfinite(df[TARGET]) & df.NWEIGHT.gt(0)
    df = df.loc[valid].copy()
    for field, (_, low, high) in NUMERIC.items():
        values = pd.to_numeric(df[field], errors="coerce")
        # Unknown/invalid numerical codes become missing, imputed inside training pipeline.
        df[field] = values.where(values.between(low, high))
    for field, mapping in CATEGORIES.items():
        # Explicit -2 categories remain meaningful (e.g. no AC), never negative numbers.
        unexpected = set(df[field].dropna()) - set(mapping) - {-1, -9}
        if unexpected:
            raise ValueError(f"Unrecognized {field} codes: {unexpected}")
        df[field] = df[field].map(mapping).astype(object).where(lambda x: x.notna(), np.nan)
    return df


def prepare():
    REPORTS.mkdir(exist_ok=True)
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(RAW, low_memory=False)
    clean = clean_records(raw)
    with sqlite3.connect(DATABASE) as conn:
        clean.to_sql("households", conn, if_exists="replace", index=False)
        conn.execute("CREATE UNIQUE INDEX household_id ON households(DOEID)")
    book = pd.read_excel(CODEBOOK, sheet_name="codebook", header=1)
    selected = book[book["Variable"].isin([*FEATURES, TARGET, "NWEIGHT"])].fillna("")
    selected.to_csv(REPORTS / "input-codebook.csv", index=False)
    audit = {
        "raw_rows": len(raw), "raw_columns": len(raw.columns), "clean_rows": len(clean),
        "excluded_invalid_target_or_weight": len(raw) - len(clean), "features": FEATURES,
        "missing_inputs": clean[FEATURES].isna().sum().to_dict(),
        "raw_duplicate_ids": int(raw.DOEID.duplicated().sum()),
        "clean_unique_ids": int(clean.DOEID.nunique()),
        "database_column_roles": {"predictors": len(FEATURES), "target": 1, "identifier": 1, "full_sample_weight": 1, "replicate_weights": len(REPLICATES)},
        "target_kwh": clean[TARGET].describe(percentiles=[.01, .5, .99]).to_dict(),
        "source_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(), "sources": SOURCES,
        "outliers": "Valid high-consumption households retained. No target-based trimming.",
        "weighting": "NWEIGHT is used for population comparisons; never a model predictor.",
    }
    (REPORTS / "data-audit.json").write_text(json.dumps(audit, indent=2))
    export_cleaning_evidence(raw, clean, audit, selected)
    return audit


def export_cleaning_evidence(raw, clean, audit, dictionary):
    """Readable exports document the same records stored in SQLite; no extra fitting."""
    processed = DATABASE.parent / "processed"
    processed.mkdir(exist_ok=True)
    readable = clean[["DOEID", *FEATURES, TARGET, "NWEIGHT"]]
    readable.to_csv(processed / "households_clean.csv", index=False)
    readable.head(20).to_csv(REPORTS / "cleaned-preview.csv", index=False)
    before_after = []
    for field, mapping in CATEGORIES.items():
        for code, label in mapping.items():
            count = int((raw[field] == code).sum())
            before_after.append({"column": field, "source_code": code, "clean_label": label, "households": count})
    pd.DataFrame(before_after).to_csv(REPORTS / "category-translations.csv", index=False)
    dictionary = dictionary.copy()
    dictionary["HomePulse role"] = dictionary["Variable"].map(
        lambda k: "Predictor" if k in FEATURES else ("Prediction target" if k == TARGET else "Comparison weight only"))
    dictionary.to_csv(REPORTS / "input-codebook.csv", index=False)
    with sqlite3.connect(DATABASE) as conn:
        dictionary.to_sql("input_dictionary", conn, if_exists="replace", index=False)
        metadata = pd.DataFrame([{"key": "source_sha256", "value": audit["source_sha256"]},
                                 {"key": "data_year", "value": "2020"},
                                 {"key": "source_url", "value": SOURCES["csv"]},
                                 {"key": "predictor_columns", "value": json.dumps(FEATURES)}])
        metadata.to_sql("dataset_metadata", conn, if_exists="replace", index=False)
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM households").fetchone()[0] == len(clean)
    lines = ["# Pandas cleaning and SQLite verification", "",
             f"Original CSV: {audit['raw_rows']:,} households and {audit['raw_columns']} columns.",
             f"Cleaned records: {audit['clean_rows']:,}. Removed: {audit['excluded_invalid_target_or_weight']}.",
             f"Duplicate IDs: {audit['raw_duplicate_ids']}. Missing selected inputs after cleaning: {sum(audit['missing_inputs'].values())}.", "",
             "## What changed", "",
             "- Selected an explicit predictor allowlist and preserved annual KWH, DOEID and survey weights for their separate roles.",
             "- Translated categorical codes into labels using the EIA codebook.",
             "- Preserved equipment -2 categories as meaningful absence/not-applicable labels.",
             "- Numeric out-of-range or unknown values become missing for later training-only imputation. None occurred in the selected real-data inputs.",
             "- Kept all valid high-consumption households. No target-based outlier trimming.",
             "- Did not fit encoders or imputers on the complete dataset; that belongs inside training splits.", "",
             "## Why no rows were removed", "",
             "All source records met the current valid-ID, positive annual KWH and positive analysis-weight criteria. EIA already processes and imputes this public file. Zero missing selected inputs does not mean zero survey uncertainty.", "",
             "## Database column roles", "",
             "74 columns = 11 predictors + 1 target + 1 identifier + 1 analysis weight + 60 replicate weights.",
             "Only the 11 allowlisted characteristics enter the model. IDs and weights never do.", "",
             "## Database tables", "",
             "- households: cleaned records, with a unique index on DOEID.",
             "- input_dictionary: official descriptions, response codes and HomePulse roles.",
             "- dataset_metadata: original-source hash, URL, year and predictor list.", "",
             "Integrity check passed and SQLite row count matches pandas.", "",
             "The CSV in data/processed is an inspection export, not an additional training source.", "",
             "Source: " + SOURCES["csv"], "Codebook: " + SOURCES["codebook"], ""]
    (REPORTS / "cleaning-summary.md").write_text("\n".join(lines))


def load_data():
    with sqlite3.connect(DATABASE) as conn:
        return pd.read_sql_query("SELECT * FROM households ORDER BY DOEID", conn)


def weighted_comparison(df, field):
    """Weighted mean with EIA's 60-replicate JK1 RSE, plus actual sample counts."""
    rows = []
    for value, group in df.groupby(field, dropna=False):
        y = group[TARGET].to_numpy()
        w = group.NWEIGHT.to_numpy()
        estimate = float(np.average(y, weights=w))
        replicate_weights = group[REPLICATES].to_numpy()
        replicate_means = (replicate_weights * y[:, None]).sum(axis=0) / replicate_weights.sum(axis=0)
        se = float(np.sqrt(59 / 60 * np.sum((replicate_means - estimate) ** 2)))
        rows.append({"group": value, "sample_households": len(group), "represented_households": float(w.sum()),
                     "mean_kwh": estimate, "standard_error": se, "rse_percent": 100 * se / estimate,
                     "low_support": len(group) < 50 or se / estimate > .30})
    return pd.DataFrame(rows)
