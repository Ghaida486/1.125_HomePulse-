from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/recs2020_public_v7.csv"
CODEBOOK = ROOT / "data/raw/recs2020_codebook_v7.xlsx"
DATABASE = ROOT / "data/homepulse.sqlite"
MODEL = ROOT / "models/pipeline.joblib"
REPORTS = ROOT / "reports"
SEED = 42
TARGET = "KWH"
NUMERIC = {
    "TOTSQFT_EN": ("Energy-consuming floor area (sq ft)", 200, 15000),
    "NHSLDMEM": ("Residents (7 means 7 or more)", 1, 7),
    "NUMFRIG": ("Refrigerators", 0, 9),
    "NUMFREEZ": ("Separate freezers", 0, 8),
}
CATEGORIES = {
    "TYPEHUQ": {1: "Mobile home", 2: "Detached house", 3: "Attached house / townhouse", 4: "Apartment (2-4 units)", 5: "Apartment (5+ units)"},
    "YEARMADERANGE": {1: "Before 1950", 2: "1950-1959", 3: "1960-1969", 4: "1970-1979", 5: "1980-1989", 6: "1990-1999", 7: "2000-2009", 8: "2010-2015", 9: "2016-2020"},
    "REGIONC": {k: k.title() for k in ["NORTHEAST", "MIDWEST", "SOUTH", "WEST"]},
    "BA_climate": {k: k for k in ["Cold", "Hot-Dry", "Hot-Humid", "Marine", "Mixed-Dry", "Mixed-Humid", "Subarctic", "Very-Cold"]},
    "EQUIPM": {3: "Central furnace", 2: "Boiler / radiators", 4: "Central heat pump", 13: "Ductless heat pump", 5: "Built-in electric units", 7: "Built-in gas / oil room heater", 8: "Wood / pellet stove", 10: "Portable electric heaters", 99: "Other", -2: "No main heating equipment"},
    "FUELHEAT": {5: "Electricity", 1: "Natural gas", 2: "Propane", 3: "Fuel oil", 7: "Wood / pellets", 99: "Other", -2: "No main heating fuel"},
    "ACEQUIPM_PUB": {1: "Central AC / central heat pump", 3: "Ductless heat pump", 4: "Window / wall AC", 5: "Portable AC", 6: "Evaporative cooler", -2: "No air conditioning"},
}
FIELD_LABELS = {"TYPEHUQ": "Home type", "YEARMADERANGE": "Construction period", "REGIONC": "Census region", "BA_climate": "Local climate", "EQUIPM": "Main heating equipment", "FUELHEAT": "Main heating fuel", "ACEQUIPM_PUB": "Main cooling equipment"}
FEATURES = list(NUMERIC) + list(CATEGORIES)
REPLICATES = [f"NWEIGHT{i}" for i in range(1, 61)]
SOURCES = {
    "csv": "https://www.eia.gov/consumption/residential/data/2020/csv/recs2020_public_v7.csv",
    "codebook": "https://www.eia.gov/consumption/residential/data/2020/xls/RECS%202020%20Codebook%20for%20Public%20File%20-%20v7.xlsx",
    "weighting": "https://www.eia.gov/consumption/residential/data/2020/pdf/microdata-guide.pdf",
}
