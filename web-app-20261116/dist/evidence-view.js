// Render only aggregate evidence returned by the validated calculation service.
const $ = id => document.getElementById(id);
const format = (number, decimals = 0) => number.toLocaleString('en-US', {maximumFractionDigits: decimals});

function element(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

export function clearEvidence() {
  $('calculation-steps').replaceChildren();
  $('matching-rows').replaceChildren();
  $('matching-explanation').textContent = '';
  $('estimate-evidence').hidden = true;
}

export function renderEvidence(result) {
  const steps = [
    ['01', 'Start with the state forecast', `${format(result.state_sales_mwh)} MWh`,
      'Residential electricity sales for the selected month, across the whole state.'],
    ['02', 'Convert to a per-account average', `${format(result.account_kwh, 1)} kWh`,
      `${format(result.state_sales_mwh)} × 1,000 ÷ ${format(result.customer_count_assumption)} residential accounts. The account count is held at its historical assumption.`],
    ['03', 'Calculate the home-profile factor', `${format(result.factor, 3)}×`,
      `${format(result.profile_mean_annual_kwh)} ÷ ${format(result.reference_mean_annual_kwh)} annual kWh: the weighted mean for matching homes divided by the mean for all eligible homes in ${result.geography}.`],
    ['04', 'Apply the factor to this month', `${format(result.estimate_kwh)} kWh`,
      `${format(result.account_kwh, 1)} × ${format(result.factor, 3)}. Calculated at full precision; displayed values are rounded.`],
  ];
  $('calculation-steps').replaceChildren(...steps.map(([number, title, value, detail]) => {
    const item = element('li', '', 'calculation-step');
    const head = element('div', '', 'calculation-heading');
    head.append(element('span', number, 'calculation-number'), element('strong', title));
    item.append(head, element('span', value, 'calculation-value'), element('p', detail));
    return item;
  }));
  $('matching-rows').replaceChildren(...result.matching_attempts.map(attempt => {
    const row = document.createElement('tr');
    row.className = attempt.decision === 'selected' ? 'selected-match' : '';
    const reasons = attempt.reasons.map(reason => reason === 'insufficient_count' ?
      'fewer than 50 matching homes' : 'effective count below 30');
    const decision = attempt.decision === 'selected' ? 'Selected' : `Not used: ${reasons.join('; ')}`;
    row.append(element('td', attempt.geography), element('td', format(attempt.sample_n)),
      element('td', format(attempt.effective_n, 1)), element('td', decision));
    return row;
  }));
  $('matching-explanation').textContent = `We select the closest geography with at least ${result.support_policy.min_sample} matching homes and an effective count of ${result.support_policy.min_effective_sample}. Your profile is compared within the ${result.size_band} band. Effective count accounts for uneven survey weights; it is a support check, not an accuracy score.`;
  $('estimate-evidence').hidden = false;
}
