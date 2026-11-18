"""Check the selected upload and saved evidence without ML dependencies.

Run from any directory: python3 scripts/check_submission.py
This does not train a model, access the network, or validate household accuracy.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative):
    return json.loads((ROOT / relative).read_text())


def read_csv(relative):
    with (ROOT / relative).open(newline="") as source:
        return list(csv.DictReader(source))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-7)


def main():
    listed = (ROOT / "docs/github-upload-files.txt").read_text().splitlines()
    require(len(listed) == len(set(listed)), "Duplicate upload entries")
    denied = {".git", ".venv", "__pycache__", ".openai", ".aws", "node_modules"}
    required = {"README.md", "docs/architecture.md", "docs/README.md", "docs/setup.md",
                "docs/household-validation-plan-20261114.md", "requirements-lock.txt",
                "data/README.md", "data/source-manifest.json",
                "data/sources/eia_monthly_state_sales.xlsx",
                "data/sources/monthly_residential_sales_2010_2026.csv",
                "web-app-20261116/dist/index.html", "web-app-20261116/dist/model.js"}
    require(required.issubset(listed), "A required entry is absent from the manifest")
    python_files = json_files = links = byte_count = 0
    for relative in listed:
        p = Path(relative)
        require(not p.is_absolute() and ".." not in p.parts, f"Unsafe path: {relative}")
        require(not denied.intersection(p.parts), f"Excluded directory: {relative}")
        require(not (p.name.startswith(".env") or p.name == "secrets.toml"),
                f"Potential secret file: {relative}")
        source = ROOT / p
        require(source.is_file() and not source.is_symlink(), f"Missing/nonregular: {relative}")
        byte_count += source.stat().st_size
        if p.suffix == ".py":
            ast.parse(source.read_text(), filename=relative)
            python_files += 1
        elif p.suffix == ".json":
            load_json(relative)
            json_files += 1
        elif p.suffix == ".md":
            for target in re.findall(r"\]\(([^\s)]+)(?:\s+[^)]*)?\)", source.read_text()):
                target = target.strip("<>")
                parts = urlsplit(target)
                if parts.scheme or target.startswith("#"):
                    continue
                path = (source.parent / unquote(parts.path)).resolve()
                require(path.is_relative_to(ROOT), f"External local link in {relative}: {target}")
                rel = path.relative_to(ROOT).as_posix()
                require(path.is_file() and rel in listed,
                        f"Local link absent from upload in {relative}: {target}")
                links += 1

    sources = load_json("data/source-manifest.json")
    for entry in sources["files"]:
        require(entry["path"] in listed, "Source snapshot omitted from manifest")
        blob = (ROOT / entry["path"]).read_bytes()
        require(hashlib.sha256(blob).hexdigest() == entry["sha256"], "Source snapshot hash mismatch")
        require(len(blob) == entry["bytes"], "Source snapshot size mismatch")
    observations = read_csv("data/sources/monthly_residential_sales_2010_2026.csv")
    source_rows = {(r["state"], r["date"]): r for r in observations}
    require(len(observations) == len(source_rows) == 10200, "Missing or duplicate source observations")
    expected_months = {f"{year}-{month:02d}-01" for year in range(2010, 2027)
                       for month in range(1, 13) if year < 2026 or month <= 8}
    states = {r["state"] for r in observations}
    require(len(states) == 51, "Incomplete source geography coverage")
    for state in states:
        require({r["date"] for r in observations if r["state"] == state} == expected_months,
                f"Incomplete monthly source series: {state}")
    require(all(math.isfinite(float(r["sales_mwh"])) and float(r["sales_mwh"]) > 0
                for r in observations), "Invalid residential sales")

    predictions = read_csv("reports/monthly/test-predictions.csv")
    evidence = load_json("web-app-20261116/evidence/model-results.json")
    require(len(predictions) == 1632, "Unexpected number of historical test rows")
    by_key = {(r["state"], r["date"]): r for r in predictions}
    require(len(by_key) == 1632, "Duplicate historical state/month rows")
    require(len(evidence["test_predictions"]) == 1632, "Missing exported test evidence")
    for row in evidence["test_predictions"]:
        reference = by_key[(row["state"], row["date"])]
        for key in ("sales_mwh", "xgboost", "same_month_three_year_mean"):
            require(close(row[key], reference[key]), f"Exported test mismatch: {row['state']}")
    for row in predictions:
        require(close(row["sales_mwh"], source_rows[(row["state"], row["date"])]["sales_mwh"]),
                "Actual test sales disagree with included source data")
        year, month = map(int, row["date"][:7].split("-"))
        prior_year, prior_month = map(int, row["latest_observation_month"][:7].split("-"))
        require((year * 12 + month) - (prior_year * 12 + prior_month) >= 3,
                "Historical forecast cutoff is too recent")
    actual = [float(r["sales_mwh"]) for r in predictions]
    mean = math.fsum(actual) / len(actual)
    denominator = math.fsum((v - mean) ** 2 for v in actual)
    metrics = {}
    for column, label in (("xgboost", "xgboost"), ("same_month_three_year_mean", "baseline")):
        errors = [float(r[column]) - float(r["sales_mwh"]) for r in predictions]
        measured = {
            "pooled_r2": 1 - math.fsum(e * e for e in errors) / denominator,
            "mae_mwh": math.fsum(abs(e) for e in errors) / len(errors),
            "wape": math.fsum(abs(e) for e in errors) / math.fsum(actual),
        }
        for key, value in measured.items():
            require(close(value, evidence["historical_test"][label][key]), f"Incorrect {label} {key}")
        metrics[label] = measured

    data = load_json("web-app-20261116/dist/assets/homepulse-data.json")
    require("test_predictions" not in data and "state_metrics" not in data,
            "Technical results should be separate from public app data")
    require(len(data["states"]) == 51 and len(data["profiles"]) == 1530,
            "Unexpected snapshot coverage")
    require(not any(k in data for k in ("households", "raw_recs", "DOEID")),
            "Unexpected household-level export")
    forecasts = {(r["state"], r["month"]): r for r in read_csv("reports/monthly/state-forecasts.csv")}
    require(len(forecasts) == len(data["forecasts"]) == 153, "Missing production forecasts")
    for row in data["forecasts"]:
        reference = forecasts[(row["state"], row["month"])]
        for key in ("xgboost_mwh", "seasonal_mean_mwh", "customer_count_assumption"):
            require(close(row[key], reference[key]), f"Forecast export mismatch: {key}")
        for key in ("latest_observation_month", "training_target_end"):
            require(row[key] == reference[key], f"Forecast date mismatch: {key}")

    print(json.dumps({"status": "passed", "selected_files": len(listed), "bytes": byte_count,
                      "python_sources_parsed": python_files, "json_files_parsed": json_files,
                      "local_document_links_checked": links, "historical_source_rows": len(observations),
                      "source_files_hash_verified": len(sources["files"]),
                      "historical_test_rows": len(predictions),
                      "production_forecasts_matched": len(forecasts), "metrics": metrics,
                      "scope": "Selected files and saved evidence; no new training or household validation"},
                     indent=2))


if __name__ == "__main__":
    main()
