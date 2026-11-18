// Runtime contracts and the household scenario calculation. No model training here.
export const SUPPORT_POLICY = Object.freeze({min_sample: 50, min_effective_sample: 30});
const SIZE_EDGES = [200, 1000, 1500, 2000, 2500, 3500, 15001];
const LEVELS = ['State', 'Region', 'United States'];
const own = (object, key) => Object.hasOwn(object, key);

function requirePositive(value, label) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    throw new Error(`${label} must be a finite, positive number.`);
  }
}
function nearlyEqual(a, b) {
  return Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(a), Math.abs(b));
}
export function sizeBand(area, bands) {
  if (typeof area !== 'number' || !Number.isFinite(area) || area < 200 || area > 15000) {
    throw new Error('Enter your home’s floor area between 200 and 15,000 sq ft.');
  }
  if (!Array.isArray(bands) || bands.length !== 6) throw new Error('Invalid floor-area categories.');
  const index = SIZE_EDGES.findIndex((lower, i) => area >= lower && area < SIZE_EDGES[i + 1]);
  return bands[index];
}

export function validateSupport(profile) {
  const policy = profile.support_policy;
  if (!policy || policy.min_sample !== SUPPORT_POLICY.min_sample || policy.min_effective_sample !== SUPPORT_POLICY.min_effective_sample) {
    throw new Error('The survey support policy is missing or inconsistent.');
  }
  const attempts = profile.matching_attempts;
  if (!Array.isArray(attempts) || !attempts.length || attempts.length > 3) throw new Error('Missing survey matching evidence.');
  for (const [index, attempt] of attempts.entries()) {
    if (attempt.level !== LEVELS[index] || !attempt.geography || !Number.isInteger(attempt.sample_n) || attempt.sample_n < 0 ||
        !Number.isFinite(attempt.effective_n) || attempt.effective_n < 0 || attempt.effective_n > attempt.sample_n + 1e-8 ||
        (attempt.sample_n > 0 && attempt.effective_n < 1 - 1e-8)) throw new Error('Invalid survey matching evidence.');
    const reasons = [];
    if (attempt.sample_n < policy.min_sample) reasons.push('insufficient_count');
    if (attempt.effective_n < policy.min_effective_sample) reasons.push('insufficient_effective_sample');
    const decision = reasons.length ? 'rejected' : 'selected';
    if (attempt.decision !== decision || JSON.stringify(attempt.reasons) !== JSON.stringify(reasons) ||
        (decision === 'selected' && index !== attempts.length - 1)) throw new Error('Survey fallback decisions are inconsistent.');
  }
  const selected = attempts.at(-1);
  if (profile.unavailable) {
    if (attempts.length !== 3 || attempts.some(x => x.decision !== 'rejected') || own(profile, 'factor')) throw new Error('An unsupported profile cannot have an estimate.');
    return;
  }
  if (selected.decision !== 'selected' || profile.level !== selected.level || profile.geography !== selected.geography ||
      profile.sample_n !== selected.sample_n || !nearlyEqual(profile.effective_n, selected.effective_n)) throw new Error('Selected survey group is inconsistent.');
  for (const key of ['factor', 'profile_mean_annual_kwh', 'reference_mean_annual_kwh']) requirePositive(profile[key], key);
  if (!nearlyEqual(profile.factor, profile.profile_mean_annual_kwh / profile.reference_mean_annual_kwh)) throw new Error('Profile factor does not match its survey evidence.');
}

function validateForecast(row) {
  for (const key of ['xgboost_mwh', 'seasonal_mean_mwh', 'customer_count_assumption']) requirePositive(row[key], key);
  if (!Number.isInteger(row.customer_count_assumption)) throw new Error('Account counts must be whole numbers.');
  const validMonth = value => typeof value === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(value);
  const monthIndex = value => Number(value.slice(0, 4)) * 12 + Number(value.slice(5));
  if (!validMonth(row.month) || !validMonth(row.latest_observation_month) ||
      monthIndex(row.month) - monthIndex(row.latest_observation_month) !== 3 ||
      row.training_target_end !== row.latest_observation_month) {
    throw new Error('Forecast observations must respect the three-month historical cutoff.');
  }
}

export function validateSnapshot(data) {
  if (data.schema_version !== 2 || !data.states || !data.home_types || !data.profiles || !Array.isArray(data.forecasts)) throw new Error('Unsupported data snapshot.');
  const months = data.metadata?.estimate_months;
  if (!Array.isArray(months) || !months.length || new Set(months).size !== months.length) throw new Error('Invalid available months.');
  const keys = new Set();
  for (const row of data.forecasts) {
    const key = `${row.state}|${row.month}`;
    if (!own(data.states, row.state) || !months.includes(row.month) || keys.has(key)) throw new Error('Duplicate or unsupported state-month forecast.');
    validateForecast(row);
    keys.add(key);
  }
  if (keys.size !== Object.keys(data.states).length * months.length) throw new Error('Forecast snapshot is incomplete.');
  if (!Array.isArray(data.size_bands) || data.size_bands.length !== 6 || new Set(data.size_bands).size !== 6) throw new Error('Invalid floor-area categories.');
  for (const [state, info] of Object.entries(data.states)) {
    for (const kind of Object.keys(data.home_types)) {
      for (const band of data.size_bands) {
        const profile = data.profiles[`${state}|${kind}|${band}`];
        if (!profile) throw new Error('A survey group is missing from the snapshot.');
        validateSupport(profile);
        const expectedGeographies = [info.name, info.region, 'United States'];
        if (profile.matching_attempts.some((x, i) => x.geography !== expectedGeographies[i]) ||
            (!profile.unavailable && profile.size_band !== band)) throw new Error('Survey geography or size band does not match the request.');
      }
    }
  }
  return data;
}

export function estimate(data, state, month, kind, area) {
  if (!own(data.states, state) || !Number.isInteger(kind) || !own(data.home_types, kind)) throw new Error('Choose a supported state and home type.');
  const band = sizeBand(area, data.size_bands);
  const profile = data.profiles[`${state}|${kind}|${band}`];
  if (!profile) throw new Error('The requested survey group is missing.');
  validateSupport(profile);
  if (profile.unavailable) throw new Error('There are too few comparable survey homes for this type and size. No estimate is available for this profile.');
  const rows = data.forecasts.filter(x => x.state === state && x.month === month);
  if (rows.length !== 1) throw new Error('Choose a supported estimate month with one forecast.');
  const row = rows[0];
  validateForecast(row);
  const account = row.xgboost_mwh * 1000 / row.customer_count_assumption;
  const result = account * profile.factor;
  requirePositive(result, 'Calculated estimate');
  return {...profile, state, month, kind, area_sqft: area, account_kwh: account, estimate_kwh: result,
    seasonal_estimate_kwh: row.seasonal_mean_mwh * 1000 / row.customer_count_assumption * profile.factor,
    latest_observation_month: row.latest_observation_month, state_sales_mwh: row.xgboost_mwh,
    customer_count_assumption: row.customer_count_assumption,
    calculation: {
      forecast_mwh: row.xgboost_mwh, kwh_per_mwh: 1000, residential_accounts: row.customer_count_assumption,
      state_account_kwh: account, profile_factor: profile.factor, monthly_scenario_kwh: result,
      formula: 'forecast_mwh * 1000 / residential_accounts * profile_factor',
      profile_factor_formula: 'profile_mean_annual_kwh / reference_mean_annual_kwh',
    }};
}
