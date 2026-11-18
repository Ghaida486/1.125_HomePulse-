import fs from 'node:fs';
import assert from 'node:assert/strict';
import {estimate,sizeBand} from '../dist/model.js';
const root=new URL('../',import.meta.url);
const data=JSON.parse(fs.readFileSync(new URL('dist/assets/homepulse-data.json',root)));
const evidence=JSON.parse(fs.readFileSync(new URL('evidence/model-results.json',root)));
const cases=JSON.parse(fs.readFileSync(new URL('scripts/parity-fixtures.json',root)));
for(const c of cases){const actual=estimate(data,c.state,c.month,c.kind,c.area_sqft);for(const key of ['estimate_kwh','account_kwh','seasonal_estimate_kwh','factor'])assert.ok(Math.abs(actual[key]-c[key])<1e-8,`${key} differs for ${JSON.stringify(c)}`)}
for(const value of [null,true,'1000',NaN,Infinity,199,15001])assert.throws(()=>sizeBand(value,data.size_bands));
assert.equal(sizeBand(999,data.size_bands),data.size_bands[0]);assert.equal(sizeBand(1000,data.size_bands),data.size_bands[1]);assert.equal(sizeBand(15000,data.size_bands),data.size_bands[5]);
assert.throws(()=>estimate(data,'XX','2026-11',2,1800));assert.throws(()=>estimate(data,'MA','2027-01',2,1800));assert.throws(()=>estimate(data,'MA','2026-11',9,1800));
let unsupported=0;for(const [key,p] of Object.entries(data.profiles)){if(!p.unavailable)continue;const[state,kind,band]=key.split('|'),index=data.size_bands.indexOf(band),area=[500,1000,1800,2200,3000,4000][index];assert.throws(()=>estimate(data,state,'2026-11',Number(kind),area));unsupported++;}
assert.equal(data.forecasts.length,153);assert.equal(evidence.test_predictions.length,1632);assert.equal(Object.keys(data.states).length,51);
assert.equal(Math.round(estimate(data,'MA','2026-11',5,1000).estimate_kwh),338);
const y=evidence.test_predictions.map(x=>x.sales_mwh),mean=y.reduce((a,b)=>a+b,0)/y.length;
const r2=1-evidence.test_predictions.reduce((s,x)=>s+(x.sales_mwh-x.xgboost)**2,0)/y.reduce((s,x)=>s+(x-mean)**2,0);
assert.ok(Math.abs(r2-evidence.historical_test.xgboost.pooled_r2)<1e-12);
assert.equal('test_predictions' in data,false);assert.equal('state_metrics' in data,false);assert.equal('historical_test' in data.metadata,false);
console.log(JSON.stringify({status:'passed',python_parity_cases:cases.length,unsupported_groups_checked:unsupported,state_month_test_rows:1632,recomputed_pooled_r2:r2,household_rows_exported:0},null,2));
