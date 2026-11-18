"""Recalculate errors on the existing state test; no training or app changes."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.dont_write_bytecode = True

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

parser = argparse.ArgumentParser()
parser.add_argument('--project', type=Path, default=Path('/Users/ghaidaaljuhani/Desktop/MIT/1.125/Project/HomePulse'))
parser.add_argument('--output', type=Path, default=Path(__file__).parent)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
database = args.project / 'data/homepulse_monthly.sqlite'
with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as con:
    data = pd.read_sql_query('SELECT * FROM test_predictions ORDER BY date,state', con)
assert len(data) == 1632 and data.state.nunique() == 51
assert not data.duplicated(['state', 'date']).any()
assert data[['sales_mwh', 'xgboost', 'same_month_three_year_mean']].notna().all().all()
assert (data.sales_mwh > 0).all()

def metrics(rows, col):
    actual, pred = rows.sales_mwh.to_numpy(), rows[col].to_numpy()
    error = pred - actual
    absolute_pct = np.abs(error) / actual
    return {
        'n': len(rows), 'r2': float(r2_score(actual, pred)),
        'mae_mwh': float(mean_absolute_error(actual, pred)),
        'rmse_mwh': float(np.sqrt(mean_squared_error(actual, pred))),
        'wape_pct': float(100 * np.abs(error).sum() / actual.sum()),
        'median_absolute_percentage_error_pct': float(100 * np.median(absolute_pct)),
        'bias_mwh': float(error.mean()),
        'within_absolute_percentage_error': {
            str(t): {'count': int((absolute_pct <= t/100).sum()),
                     'percentage': float(100 * (absolute_pct <= t/100).mean())}
            for t in [5, 10, 20]
        },
    }

methods = {'XGBoost': 'xgboost', 'Seasonal average': 'same_month_three_year_mean'}
overall = {name: metrics(data, col) for name, col in methods.items()}
subgroups = {state: {name: metrics(rows, col) for name, col in methods.items()}
             for state, rows in data.groupby('state')}
examples = []
for _, row in data.loc[data.state == 'MA'].head(3).iterrows():
    examples.append({'state': row.state, 'month': row.date[:7], 'actual_mwh': float(row.sales_mwh),
                     'predicted_mwh': float(row.xgboost),
                     'difference_mwh': float(row.xgboost - row.sales_mwh),
                     'absolute_error_pct': float(100 * abs(row.xgboost - row.sales_mwh) / row.sales_mwh)})
hidden_path = args.project / 'docs/target-input-audit-20261114/result.json'
hidden = json.loads(hidden_path.read_text())
assert hidden['hidden_answer_and_after_cutoff_sales_reproduce_stored_predictions']
assert hidden['predictions_checked'] == len(data)
result = {
    'description': 'Accuracy recalculation on an existing test, not a new independent holdout or a retrained model.',
    'period': [data.date.min()[:7], data.date.max()[:7]],
    'target': 'State monthly residential electricity sales, MWh',
    'locations': 51, 'test_observations': len(data),
    'model_unchanged': True, 'test_rows_removed': 0,
    'hidden_answer_replay_verified': True,
    'hidden_answer_audit': str(hidden_path),
    'database_sha256': hashlib.sha256(database.read_bytes()).hexdigest(),
    'overall': overall, 'by_state': subgroups,
    'examples_selection': 'First three Massachusetts months in the test period, not selected by their errors.',
    'examples': examples,
    'interpretation': [
        'The answer and all sales newer than each permitted cutoff can be hidden without changing the 1,632 state predictions.',
        'Historical electricity records are still allowed inputs; users do not supply household bills.',
        'Threshold percentages describe this observed test and are not future coverage guarantees or prespecified pass criteria.',
        'The seasonal baseline has lower overall MAE and a larger fraction within 10% than XGBoost.',
        'High pooled R-squared includes between-state size differences; inspect state metrics too.',
        'This does not validate the RECS-adjusted individual-household estimate.',
        'Current revised EIA data are used, not archived release vintages. The test has already been inspected.',
    ],
}
(args.output / 'accuracy-results.json').write_text(json.dumps(result, indent=2))

teal, orange, navy, grey = '#007D80', '#D58B35', '#142F43', '#506877'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.labelcolor': navy,
                     'text.color': navy, 'axes.spines.top': False, 'axes.spines.right': False})
fig, (left, right) = plt.subplots(1, 2, figsize=(13.5, 5.8), gridspec_kw={'width_ratios': [1.05, 1]})
fig.subplots_adjust(left=.075, right=.96, top=.79, bottom=.23, wspace=.34)
fig.suptitle('HomePulse: predictions compared with actual EIA records', x=.075, y=.97,
             ha='left', fontsize=19, fontweight='bold')
fig.text(.075, .90, 'Existing historical test · Jan 2024–Aug 2026 · 1,632 state-months · all 50 states + D.C.',
         color=grey, fontsize=11.5)
x, y = data.sales_mwh.to_numpy()/1e6, data.xgboost.to_numpy()/1e6
limit = max(x.max(), y.max())*1.06
left.scatter(x, y, s=10, color=teal, alpha=.55, edgecolor='none', zorder=3)
left.plot([0, limit], [0, limit], linestyle='--', color='#C74745', linewidth=1.4, label='Perfect prediction', zorder=2)
left.set(xlim=(0, limit), ylim=(0, limit), xlabel='Actual sales (million MWh)', ylabel='Predicted sales (million MWh)')
left.set_title('XGBoost: all test predictions', loc='left', fontsize=13, pad=13, fontweight='bold')
left.text(.05, .91, f"Pooled R² = {overall['XGBoost']['r2']:.3f}", transform=left.transAxes, fontsize=12)
left.legend(loc='lower right', frameon=False, fontsize=10)
left.grid(color='#E2EAEE', linewidth=.6, alpha=.7)
categories = [5, 10, 20]
positions = np.arange(3)
for name, offset, color in [('XGBoost', -.18, teal), ('Seasonal average', .18, orange)]:
    values = [overall[name]['within_absolute_percentage_error'][str(t)]['percentage'] for t in categories]
    bars = right.barh(positions+offset, values, height=.31, color=color, label=name, zorder=3)
    right.bar_label(bars, labels=[f'{v:.1f}%' for v in values], padding=4, fontsize=10.5, color=navy)
right.set_yticks(positions, ['Within ±5%', 'Within ±10%', 'Within ±20%'])
right.invert_yaxis()
right.set_xlim(0, 114)
right.set_xticks([0, 25, 50, 75, 100])
right.set_xlabel('Share of test predictions (%)')
right.set_title('How close were they to actual values?', loc='left', fontsize=13, pad=13, fontweight='bold')
right.grid(axis='x', color='#E2EAEE', linewidth=.6, alpha=.7)
right.legend(loc='upper center', bbox_to_anchor=(.5, -.20), ncol=2, frameon=False, fontsize=10)
fig.text(.075, .10, 'The seasonal baseline has lower overall error. Results vary by state.', fontsize=11.5, color=navy)
fig.text(.075, .045, 'State forecasting evidence only: this does not establish individual-household accuracy.', fontsize=11, color=grey)
fig.savefig(args.output / 'actual-versus-predicted.png', dpi=180, facecolor='white')
plt.close(fig)

xm, bm = overall['XGBoost'], overall['Seasonal average']
lines = [
    '# HomePulse — prediction accuracy check', '',
    'November 14, 2026. The model and app were not changed. This recalculates the existing historical test, rather than creating a new independent test.', '',
    '## The question', '',
    'Can the model predict a value close to the actual recorded electricity sales when that answer is hidden?', '',
    'For each test month, the prediction uses only state/calendar inputs and state electricity records at least three months old. The separate hidden-answer audit removes the target value and all newer-than-cutoff sales and reproduces all 1,632 stored predictions. Actual values are then used to score the results.', '',
    '## Results', '',
    '| Metric | XGBoost | Seasonal average |', '|---|---:|---:|',
    f"| Pooled R² | {xm['r2']:.3f} | {bm['r2']:.3f} |",
    f"| Mean absolute error, MWh/state-month | {xm['mae_mwh']:,.0f} | {bm['mae_mwh']:,.0f} |",
    f"| WAPE | {xm['wape_pct']:.2f}% | {bm['wape_pct']:.2f}% |",
]
for t in categories:
    a, b = xm['within_absolute_percentage_error'][str(t)], bm['within_absolute_percentage_error'][str(t)]
    lines.append(f"| Predictions within {t}% of actual | {a['percentage']:.1f}% ({a['count']}/1632) | {b['percentage']:.1f}% ({b['count']}/1632) |")
lines += ['', 'WAPE is total absolute error divided by total actual sales. Each state-month receives equal weight in the threshold percentages. These descriptive thresholds were not a previously agreed pass criterion and are not future prediction guarantees.', '',
          '## Concrete examples', '', 'The first three Massachusetts test months are shown below, without selection based on their error.', '',
          '| Month | Actual MWh | Predicted MWh | Absolute error |', '|---|---:|---:|---:|']
for e in examples:
    lines.append(f"| {e['month']} | {e['actual_mwh']:,.0f} | {e['predicted_mwh']:,.0f} | {e['absolute_error_pct']:.2f}% |")
lines += ['', '## What this answers for Abel', '',
          '- The actual-versus-predicted comparison, named baseline and error measures are explicit.',
          '- Every state has separate metrics in accuracy-results.json; the app also exposes state-specific results.',
          '- The baseline still performs better overall, so this is not evidence that XGBoost adds predictive value over it.',
          '- A practical household error target and independent validation of the RECS-adjusted household output are still needed.',
          '- The evaluated target is state-level monthly sales. It is not the electricity bill or consumption of one home.',
          '- Do not use these already-inspected test results to select further model settings and call them a fresh final test.', '',
          'Source: the existing read-only data/homepulse_monthly.sqlite and its documented EIA snapshot. Prediction-time masking verification: docs/target-input-audit-20261114/result.json.', '',
          'Reproduce by running evaluate_predictions.py with --project pointing at the HomePulse root and --output pointing at an output directory. The script reads the source database and produces this report, a figure and overall/per-state metrics; it never fits or replaces a model.', '']
(args.output / 'accuracy-review.md').write_text('\n'.join(lines))
print(json.dumps({'overall': overall, 'first_example': examples[0], 'figure': str(args.output / 'actual-versus-predicted.png')}))
