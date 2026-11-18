"""Install frozen EIA sources from the bundled workbook, cache or official download."""
from pathlib import Path
import argparse
import hashlib
import shutil
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ("experiments/state-forecast-20261113/raw/eia_monthly_state_sales.xlsx",
     "https://www.eia.gov/electricity/data/state/xls/861m/HS861M%202010-.xlsx",
     "c7963ad7c9bd2020cc7472f100a9c5330a4dff97a62be95407137a14b9c4044e"),
    ("data/raw/recs2020_public_v7.csv",
     "https://www.eia.gov/consumption/residential/data/2020/csv/recs2020_public_v7.csv",
     "8d5f6d3120d2cbc2535151c7d455e7a536ca9768f773e15edd45932ec38b3592"),
]
BUNDLED_SOURCES = {
    "experiments/state-forecast-20261113/raw/eia_monthly_state_sales.xlsx":
        "data/sources/eia_monthly_state_sales.xlsx",
}

def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-project", type=Path, help="Reuse the same verified source snapshot from another local HomePulse folder")
    args = parser.parse_args()
    for relative, url, expected in SOURCES:
        dest = ROOT / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if digest(dest) != expected:
                raise SystemExit(f"Existing file differs from the frozen source: {relative}. Preserve it and use a clean project folder.")
            print(f"Verified existing source: {relative}", flush=True)
            continue
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp) / "source"
            if args.cache_project:
                shutil.copyfile(args.cache_project.resolve() / relative, candidate)
                method = "verified local snapshot"
            elif relative in BUNDLED_SOURCES and (ROOT / BUNDLED_SOURCES[relative]).is_file():
                shutil.copyfile(ROOT / BUNDLED_SOURCES[relative], candidate)
                method = "bundled source snapshot"
            else:
                print(f"Downloading {url}", flush=True)
                with urllib.request.urlopen(url, timeout=120) as response, candidate.open("wb") as output:
                    shutil.copyfileobj(response, output)
                method = "official EIA download"
            if digest(candidate) != expected:
                raise SystemExit(f"Source checksum changed: {relative}. EIA may have revised its release. This fixed study must use its original snapshot; no file was installed. Use --cache-project with a verified copy, or design a separately dated update.")
            shutil.copyfile(candidate, dest)
        print(f"Verified {relative} ({method})", flush=True)

if __name__ == "__main__":
    main()
