"""Export aggregate HomePulse data for the web UI. Never publish household records."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--project', type=Path, required=True)
parser.add_argument('--database', type=Path, help='Existing SQLite snapshot; defaults to PROJECT/data/homepulse_monthly.sqlite')
args = parser.parse_args()
sys.path.insert(0, str(args.project / 'src'))
from homepulse.monthly import load_store, profile_adjustment, estimate_home, STATES, SIZE_LABELS, HOME_TYPES
from homepulse.peer_matching import SurveyProfileMatcher, ProfileSupportError
from plotly.offline import get_plotlyjs

root = Path(__file__).resolve().parents[1]
database = args.database or args.project / 'data/homepulse_monthly.sqlite'
store = load_store(database)
matcher = SurveyProfileMatcher(store['profiles'])
profiles, fixtures = {}, []
areas = [500, 1000, 1800, 2200, 3000, 4000]
for state in STATES:
    for kind in HOME_TYPES:
        for band, area in zip(SIZE_LABELS, areas):
            key = f'{state}|{kind}|{band}'
            try:
                profiles[key] = profile_adjustment(store['profiles'], state, kind, area, matcher=matcher)
                for month in store['metadata']['estimate_months']:
                    result = estimate_home(store, state, month, kind, area, matcher=matcher)
                    fixtures.append({k: result[k] for k in ['state','month','area_sqft','estimate_kwh','account_kwh','seasonal_estimate_kwh','factor']} | {'kind': kind})
            except ProfileSupportError as e:
                profiles[key] = {'unavailable': str(e), 'matching_attempts': e.attempts,
                                 'support_policy': dict(matcher.policy)}

obs = store['monthly_observations'].sort_values('date').groupby('state').tail(24)
payload = {
    'states': STATES, 'home_types': HOME_TYPES, 'size_bands': SIZE_LABELS,
    'profiles': profiles, 'forecasts': store['forecasts'].to_dict('records'),
    'history': obs[['state','date','sales_mwh']].to_dict('records'),
    'metadata': {k: v for k, v in store['metadata'].items() if k not in ('historical_test', 'selected_model')},
    'snapshot_date': '2026-11-16',
    'schema_version': 2,
    'source_db_sha256': hashlib.sha256(database.read_bytes()).hexdigest(),
}
evidence = {
    'test_predictions': store['test_predictions'][['state','date','sales_mwh','xgboost','same_month_three_year_mean']].to_dict('records'),
    'state_metrics': store['test_state_metrics'].to_dict('records'),
    'historical_test': store['metadata']['historical_test'],
    'selected_model': store['metadata']['selected_model'],
    'source_db_sha256': payload['source_db_sha256'],
}
(root/'evidence').mkdir(exist_ok=True)
(root/'evidence/model-results.json').write_text(json.dumps(evidence, allow_nan=False, separators=(',',':')))
(root/'dist/assets/homepulse-data.json').write_text(json.dumps(payload, allow_nan=False, separators=(',',':')))
(root/'dist/assets/plotly.min.js').write_text(get_plotlyjs())
(root/'scripts/parity-fixtures.json').write_text(json.dumps(fixtures, allow_nan=False))
print(json.dumps({'profile_groups':len(profiles),'supported_groups':sum('factor' in v for v in profiles.values()),'parity_cases':len(fixtures),'state_month_tests':len(evidence['test_predictions'])}))
