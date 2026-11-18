import fs from 'node:fs';
import assert from 'node:assert/strict';
import {estimate, validateSnapshot} from '../dist/model.js';
const data = JSON.parse(fs.readFileSync(new URL('../dist/assets/homepulse-data.json', import.meta.url)));
const profileKey = 'MA|5|1,000–1,499 sq ft';
const profile = copy => copy.profiles[profileKey];
const cases = [
  ['duplicate forecasts', copy => copy.forecasts.push({...copy.forecasts[0]})],
  ['missing forecasts', copy => copy.forecasts.pop()],
  ['non-finite forecast', copy => copy.forecasts[0].xgboost_mwh = NaN],
  ['negative forecast', copy => copy.forecasts[0].xgboost_mwh = -1],
  ['zero accounts', copy => copy.forecasts[0].customer_count_assumption = 0],
  ['string accounts', copy => copy.forecasts[0].customer_count_assumption = '1000'],
  ['fractional accounts', copy => copy.forecasts[0].customer_count_assumption = 1000.5],
  ['future observations', copy => copy.forecasts[0].latest_observation_month = copy.forecasts[0].month],
  ['incorrect historical cutoff', copy => copy.forecasts[0].latest_observation_month = '2026-07'],
  ['late model training', copy => copy.forecasts[0].training_target_end = '2026-09'],
  ['missing profile', copy => delete copy.profiles[profileKey]],
  ['unsubstantiated factor', copy => profile(copy).factor *= 2],
  ['weakened support threshold', copy => profile(copy).support_policy.min_sample = 1],
  ['wrong chosen geography', copy => profile(copy).geography = 'West'],
  ['wrong size band', copy => profile(copy).size_band = '200–999 sq ft'],
  ['inflated support count', copy => profile(copy).sample_n = 500],
  ['missing matching trail', copy => profile(copy).matching_attempts = []],
  ['invalid effective count', copy => profile(copy).matching_attempts[0].effective_n = Infinity],
  ['effective count exceeds records', copy => profile(copy).matching_attempts[0].effective_n = 200],
  ['skipped geography', copy => profile(copy).matching_attempts.shift()],
  ['unsupported group accepted', copy => profile(copy).matching_attempts[0].decision = 'selected'],
  ['omitted rejection reason', copy => profile(copy).matching_attempts[0].reasons = []],
  ['schema drift', copy => copy.schema_version = 1],
];
for (const [name, mutate] of cases) {
  const copy = structuredClone(data);
  mutate(copy);
  assert.throws(() => validateSnapshot(copy), undefined, name);
}
const result = estimate(data, 'MA', '2026-11', 5, 1000);
assert.equal(result.matching_attempts[0].sample_n, 17);
assert.equal(result.matching_attempts[1].sample_n, 149);
assert.equal(result.calculation.monthly_scenario_kwh, result.estimate_kwh);
assert.equal(result.calculation.state_account_kwh * result.calculation.profile_factor, result.estimate_kwh);
// Area is a band selector: do not silently imply exact continuous floor-area scaling.
assert.equal(estimate(data, 'MA', '2026-11', 5, 1499).estimate_kwh, result.estimate_kwh);
assert.notEqual(estimate(data, 'MA', '2026-11', 5, 1500).size_band, result.size_band);
const unsupported = Object.keys(data.profiles).find(key => data.profiles[key].unavailable);
const tampered = structuredClone(data);
tampered.profiles[unsupported].factor = 1;
assert.throws(() => validateSnapshot(tampered));
// Validate selected forecasts again even if a caller bypasses initial snapshot validation.
const duplicate = structuredClone(data);
duplicate.forecasts.push({...duplicate.forecasts.find(x => x.state === 'MA' && x.month === '2026-11')});
assert.throws(() => estimate(duplicate, 'MA', '2026-11', 5, 1000));
console.log(JSON.stringify({status: 'passed', corrupt_snapshot_cases_rejected: cases.length + 1,
  duplicate_lookup_rejected: true, calculation_trace_checked: true, size_band_behavior_checked: true}, null, 2));
