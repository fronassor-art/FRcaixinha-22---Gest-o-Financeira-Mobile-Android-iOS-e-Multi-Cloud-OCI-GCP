import assert from 'node:assert/strict';
import {parseCycleOpeningPreview} from '../services/cycleOpeningBoundary';
const tenant='00000000-0000-4000-8000-0000000000a1';
const raw={
 contract:'AI_STUDIO_M20800_CYCLE_OPENING_PREVIEW_V1',
 source:'POSTGRESQL_RLS_AUTHENTICATED_ADMIN',tenant_id:tenant,
 year:2030,start_date:'2030-01-01',end_date:'2030-12-31',
 amount_cents:25000,minimum_amount_cents:15000,
 price_explicitly_entered:true,historical_obligations_unchanged:true,
 blocked_reasons:[],preconditions_satisfied:true,
 cycle_creation_enabled:false,financial_effect:false,reason_recorded:false,
};
assert.equal(parseCycleOpeningPreview(raw,tenant).amount_cents,25000);
assert.throws(()=>parseCycleOpeningPreview({...raw,amount_cents:10000},tenant));
assert.throws(()=>parseCycleOpeningPreview({...raw,financial_effect:true},tenant));
assert.throws(()=>parseCycleOpeningPreview({...raw,cycle_creation_enabled:true},tenant));
assert.throws(()=>parseCycleOpeningPreview({...raw,tenant_id:'OTHER'},tenant));
assert.throws(()=>parseCycleOpeningPreview({...raw,blocked_reasons:['YEAR_ALREADY_EXISTS']},tenant));
assert.equal(parseCycleOpeningPreview({...raw,blocked_reasons:['YEAR_ALREADY_EXISTS'],preconditions_satisfied:false},tenant).cycle_creation_enabled,false);
console.log('M20900_ANDROID_OPENING_PREVIEW_FAIL_CLOSED=PASS');
