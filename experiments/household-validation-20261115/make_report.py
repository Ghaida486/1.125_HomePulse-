"""Present the fixed first-run results, without refitting or selecting homes."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import plotly.graph_objects as go


def main():
    p=argparse.ArgumentParser(); p.add_argument('--results',type=Path,required=True); a=p.parse_args(); out=a.results
    summary=json.loads((out/'summary.json').read_text())
    full=pd.read_csv(out/'evaluation-predictions-with-labels.csv'); d=full.loc[full.supported].copy()
    m=pd.read_csv(out/'overall-household-metrics.csv')
    m=m.loc[m.weighting=='unweighted'].set_index('method')
    sub=pd.read_csv(out/'subgroup-household-metrics.csv')
    sub=sub.loc[(sub.weighting=='unweighted')&(sub.method=='hybrid_kwh')]
    home=sub.loc[sub.dimension=='home_type'].copy(); regions=sub.loc[sub.dimension=='region'].copy()
    h=m.loc['hybrid_kwh']; q=summary['interval_half_width_kwh']
    colors={'ink':'#18364B','teal':'#008B8B','red':'#C45C4F','grey':'#7E90A0'}
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.labelcolor':colors['ink'],'text.color':colors['ink'],'axes.titleweight':'bold'})
    fig,axes=plt.subplots(2,2,figsize=(14.5,9.5),gridspec_kw={'hspace':.42,'wspace':.50})
    fig.suptitle('HomePulse | Household validation',x=.065,ha='left',fontsize=24,fontweight='bold',y=.985)
    fig.text(.065,.935,'Historical annual 2020 test · 3,515 supported evaluation homes · household R² = '+f"{h.r2:.3f}",fontsize=13)
    ax=axes[0,0]; limit=float(max(d.actual_kwh.max(),d.hybrid_kwh.max())*1.05)
    ax.scatter(d.actual_kwh,d.hybrid_kwh,s=12,c=colors['teal'],alpha=.22,edgecolors='none',rasterized=True)
    ax.plot([0,limit],[0,limit],'--',color=colors['red'],lw=1.5,label='Perfect prediction')
    ax.set(xlim=(0,limit),ylim=(0,limit),xlabel='RECS reference electricity (kWh/year)',ylabel='Estimated electricity (kWh/year)',title='Every supported evaluation home')
    ax.legend(loc='upper left',frameon=False); ax.xaxis.set_major_formatter(FuncFormatter(lambda x,p:f'{x/1000:.0f}k')); ax.yaxis.set_major_formatter(FuncFormatter(lambda x,p:f'{x/1000:.0f}k'))
    ax=axes[0,1]
    fields=['regional_median_kwh','state_only_kwh','hybrid_kwh']
    labels=['Regional median','State average only','Home type + size']
    vals=[m.loc[f,'mae_kwh'] for f in fields]
    ax.barh(labels,vals,color=[colors['grey'],colors['grey'],colors['teal']],height=.55)
    for i,v in enumerate(vals): ax.text(v+70,i,f'{v:,.0f}',va='center',fontsize=12)
    ax.set(xlabel='Mean absolute error (kWh/home/year)',title='Does the household adjustment help?',xlim=(0,5700))
    ax.invert_yaxis(); ax.text(.0,-.28,'10.7% lower MAE than the regional median.\nThe proposed 15% improvement target was not met.',transform=ax.transAxes,fontsize=11)
    ax=axes[1,0]; names=['Mobile home','Detached house','Attached / townhouse','Apartment (2–4 units)','Apartment (5+ units)']
    ax.barh(names,home.mae_kwh,color=colors['teal'],height=.55)
    for i,v in enumerate(home.mae_kwh):ax.text(v+55,i,f'{v:,.0f}',va='center')
    ax.set(xlabel='Mean absolute error (kWh/home/year)',title='Errors differ by home type',xlim=(0,5700));ax.invert_yaxis()
    ax=axes[1,1]
    ax.barh(regions.group_label,regions.mae_kwh,color=colors['teal'],height=.55)
    for i,v in enumerate(regions.mae_kwh):ax.text(v+55,i,f'{v:,.0f}',va='center')
    ax.set(xlabel='Mean absolute error (kWh/home/year)',title='Errors differ by Census region',xlim=(0,5700));ax.invert_yaxis()
    fig.subplots_adjust(top=.86,bottom=.13,left=.15,right=.95)
    fig.text(.065,.055,'56 of 3,571 evaluation homes had insufficient profile support and received no estimate (98.4% coverage).',fontsize=10)
    fig.text(.065,.030,'Annual 2020 diagnostic using previously explored data. This does not validate monthly or present-day household estimates.',fontsize=10)
    fig.savefig(out/'household-validation.png',dpi=170,facecolor='white'); plt.close(fig)

    # Self-contained interactive chart, each record is traceable to the saved CSV.
    chart=go.Figure(go.Scatter(x=d.actual_kwh,y=d.hybrid_kwh,mode='markers',name='Evaluation home',
        customdata=np.column_stack([d.survey_id,d.state,d.home_type,d.area_sqft,d.absolute_error_kwh]),
        marker=dict(size=6,color=colors['teal'],opacity=.4),
        hovertemplate='Survey home %{customdata[0]} · %{customdata[1]}<br>Type code %{customdata[2]} · %{customdata[3]:,.0f} sq ft<br>RECS: %{x:,.0f} kWh/year<br>Estimate: %{y:,.0f} kWh/year<br>Absolute error: %{customdata[4]:,.0f} kWh<extra></extra>'))
    chart.add_trace(go.Scatter(x=[0,limit],y=[0,limit],mode='lines',line=dict(dash='dash',color=colors['red']),name='Perfect prediction'))
    chart.update_layout(template='plotly_white',title=f'HomePulse annual household test | R² {h.r2:.3f} | MAE {h.mae_kwh:,.0f} kWh/year',
        xaxis_title='RECS 2020 reference annual electricity (kWh)',yaxis_title='Historical household estimate (kWh/year)',
        xaxis=dict(range=[0,limit]),yaxis=dict(range=[0,limit]),height=720,
        annotations=[dict(text='All 3,515 supported evaluation homes. 56 unsupported. Historical diagnostic; not current monthly accuracy.',
                          x=0,y=-.18,xref='paper',yref='paper',showarrow=False,xanchor='left')],margin=dict(b=110))
    chart.write_html(out/'household-validation-interactive.html',include_plotlyjs=True,full_html=True)

    method_rows='\n'.join(f'| {r.label} | {r.mae_kwh:,.0f} | {r.rmse_kwh:,.0f} | {r.r2:.3f} | {r.within_20_pct:.1f}% |' for r in m.itertuples())
    group_rows='\n'.join(f'| {r.group_label} | {r.supported_n:,} / {r.total_n:,} | {r.mae_kwh:,.0f} | {r.r2:.3f} | {r.observed_coverage_pct:.1f}% |' for r in pd.concat([home,regions]).itertuples())
    weighted=pd.read_csv(out/'overall-household-metrics.csv').query("method == 'hybrid_kwh' and weighting == 'survey_weighted_sensitivity'").iloc[0]
    report=f'''# HomePulse household validation — November 15, 2026

The current household adjustment improves on two simple baselines, but its individual-home errors remain substantial. The prespecified first-run benchmark was **not met**. This result does not support calling the current household output a precise electricity prediction.

## Main findings

- Evaluated annual estimates against the **same-year RECS 2020 annual KWH** reference.
- Predicted **3,515 of 3,571 evaluation homes** (98.4%); 56 had insufficient comparable-home support. No homes were removed for large errors or extreme electricity consumption.
- Mean absolute error: **{h.mae_kwh:,.0f} kWh/home/year**. Household R²: **{h.r2:.3f}**.
- **{h.within_20_pct:.1f}%** of supported homes were within ±20% of their reference annual consumption; median absolute percentage error was **{h.median_ape_pct:.1f}%**.
- MAE improved **{summary['improvement_over_regional_median_pct']:.1f}%** over the regional-median baseline and **{summary['improvement_over_unadjusted_state_pct']:.1f}%** over the unadjusted state/account estimate. The protocol required at least 15% improvement over the regional median and no worse error than the unadjusted state estimate; the first condition failed.
- Supplying observed state averages instead of forecasts left household error almost unchanged. This is evidence that the home-profile method itself needs attention, beyond improving state forecasts.

![Household evaluation](household-validation.png)

## Fixed method and leakage controls

The November 14 protocol was saved before this run. Of 18,496 source households, the app's existing exclusion of 645 identified-solar homes leaves 17,851 eligible records. Apartment solar status is not measured. No new outlier filtering was used.

With seed 20261114, stratified by home type and Census region, 10,710 homes formed development profiles, 3,570 formed the uncertainty-calibration group and 3,571 formed the evaluation group. IDs are persisted and disjoint. Both the profile numerator and its geographic reference denominator use development homes only. State → region → national fallback and the app's fixed size bands, minimum 50 records and effective sample 30 were retained.

The state model was recreated for historical 2020. Six configurations were compared using only pre-2020 validation; the winner was refitted through September 2019. Its coefficients remain fixed through 2020. Every target month's sales inputs and held account count are dated at least three months earlier. Earlier 2020 state observations may therefore enter later months' inputs, without refitting the model. These are rolling historical predictions, not twelve forecasts all issued in 2019.

For each evaluation home, the method sums twelve 2020 monthly state forecasts, divided by the permitted customer counts and multiplied by a development-only home-type/size factor. The input function receives only survey ID, state, region, home type and area; it never receives that home's KWH. Predictions are saved before joining household outcomes for scoring. IDs and region are lookup metadata; users continue to have the same four app inputs.

Because development profiles use other **2020** homes, this is a retrospective household generalization check, not an as-issued forecast of 2020 using only 2019 information.

## Baselines and error measures

The primary baseline is the unweighted median annual KWH of development homes in the same Census region. The second baseline is the same annual state/account forecast without the household factor. All methods below are scored on the identical 3,515 supported homes. MAE is the primary measure; RMSE, R², bias and percentage-error measures are supporting evidence.

| Method | MAE, kWh/year | RMSE, kWh/year | R² | Within ±20% |
|---|---:|---:|---:|---:|
{method_rows}

The observed-state component diagnostic supplies actual state values. It is not a forecast score and must not be presented as an operational model result. It isolates the remaining household estimation error.

The household R² here is distinct from the existing 0.990 state-month R². The recreated 2020 state stage had pooled R² {summary['historical_state_metrics']['pooled_r2']:.3f}; neither state score measures household accuracy.

## Errors by home type and region

Coverage denominators include unsupported profiles. Report all groups; do not select only favorable ones. Full state results are in the subgroup CSV, with fewer-than-50 supported records flagged as low support.

| Group | Predicted / evaluation homes | MAE, kWh/year | R² | Coverage of nominal 80% interval |
|---|---:|---:|---:|---:|
{group_rows}

## Survey weights and comparison limits

`NWEIGHT` is used for development profile means. Primary errors treat each evaluation home equally. NWEIGHT-weighted sensitivity results are MAE **{weighted.mae_kwh:,.0f} kWh/year** and R² **{weighted.r2:.3f}**. These are separate from the primary results, not a replacement selected because the score is higher.

The full weighted and unweighted error tables are saved. This run does **not** compute survey-design confidence intervals for population comparisons. EIA's replicate-weight method remains appropriate for that separate task; split-sample adjustments would need consideration. Survey-weight uncertainty for a group average is different from the predictive uncertainty for one home.

RECS primary residences and utility residential accounts are different populations. RECS KWH contains total electricity including self-generated solar, while state sales represent supplied electricity. Excluding known solar homes reduces but does not eliminate that mismatch. RECS consumption values include EIA annualization/imputation; they are reference estimates, not error-free meter measurements for every home.

## Uncertainty for one annual estimate

Using only supported calibration homes, the 80% nominal absolute-residual interval has half-width **{q:,.0f} kWh/year**, with the lower endpoint clipped at zero. Evaluation coverage was **{summary['interval']['observed_coverage_pct']:.1f}%**, with mean total width **{summary['interval']['mean_width_kwh']:,.0f} kWh/year**.

That broad interval is informative about the limitations: reaching approximately 80% average coverage does not make the point estimate precise. Coverage varies by subgroup, and there is no guarantee for a particular home, a future year or the U.S. population. This annual interval is **not** installed in the monthly app.

## What this means for Deliverable 2

Suggested wording:

> I tested the household calculation against withheld 2020 household outcomes, using separate development, calibration and evaluation homes. The household adjustment lowered average error by 10.7% compared with a regional median, but individual errors remain large and our 15% improvement benchmark was not met. State-level accuracy does not establish home-level accuracy. The next task is improving or limiting the household estimate and validating monthly outputs with compatible household outcomes.

This directly addresses Abel's requests for a named baseline, error measure, improvement criterion, subgroup results, weight handling and uncertainty. Replicate-weight population confidence intervals and present-day/monthly external validation remain unfinished. John’s request is addressed by the bounded six-candidate state selection and explicit leakage checks, without further tuning against evaluation outcomes.

## Recommended next decision

Keep the current household output labeled as an exploratory scenario. A four-input state/month/type/size adjustment does not currently support a precise individual-home claim. The strongest immediate next step is to compare this result with the already documented richer household-characteristics models, using an appropriate common evaluation protocol before choosing a direction. Any new experiment should be specified before it runs; this evaluation has now been inspected.

A monthly or current-year household accuracy claim needs matching household outcomes. Bills or meter readings can be hidden evaluation labels without becoming an additional input users must provide to make a prediction.

## Reproducibility and integrity

- Source CSV, database, code, protocol and package versions are hashed/recorded in the run manifest.
- `integrity-checks.json` records hidden-target checks for all 612 historical state-month predictions and household split isolation.
- `independent-verification.json` separately reconstructs all 3,515 supported household predictions from development profiles, checks all 612 account counts, recomputes baselines, weighted/unweighted metrics and interval coverage.
- The app, monthly source files and production database hashes are unchanged.
- The 2020 records and model family have already been examined during prior development. This is a transparent historical diagnostic, **not a fresh independent external test**. Revised state data were used rather than historical publication vintages.

Source documentation: [EIA RECS 2020](https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata), [EIA weighting guide](https://www.eia.gov/consumption/residential/data/2020/pdf/microdata-guide.pdf), [EIA state electricity data](https://www.eia.gov/electricity/data/state/).
'''
    (out/'household-validation-report.md').write_text(report)
    print('Created report, static figure and self-contained interactive chart.')


if __name__=='__main__':main()
