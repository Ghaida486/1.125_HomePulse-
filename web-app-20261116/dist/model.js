// Same calculation and eligibility rules as homepulse.monthly. No model training here.
export function sizeBand(area, bands) {
  if (typeof area !== 'number' || !Number.isFinite(area) || area < 200 || area > 15000) throw new Error('Enter your home’s floor area between 200 and 15,000 sq ft.');
  const edges = [200,1000,1500,2000,2500,3500,15001];
  return bands[edges.findIndex((x,i) => i < 6 && area >= x && area < edges[i+1])];
}
export function estimate(data, state, month, kind, area) {
  if (!data.states[state] || !data.home_types[kind]) throw new Error('Choose a supported state and home type.');
  const band = sizeBand(area, data.size_bands);
  const profile = data.profiles[`${state}|${kind}|${band}`];
  if (!profile || profile.unavailable) throw new Error('There are too few comparable survey homes for this type and size. No estimate is available for this profile.');
  const row = data.forecasts.find(x => x.state === state && x.month === month);
  if (!row || !(row.customer_count_assumption > 0)) throw new Error('Choose a supported estimate month.');
  const account = row.xgboost_mwh * 1000 / row.customer_count_assumption;
  return {...profile, state, month, kind, area_sqft:area, account_kwh:account, estimate_kwh:account*profile.factor,
    seasonal_estimate_kwh:row.seasonal_mean_mwh*1000/row.customer_count_assumption*profile.factor,
    latest_observation_month:row.latest_observation_month, state_sales_mwh:row.xgboost_mwh,
    customer_count_assumption:row.customer_count_assumption};
}
