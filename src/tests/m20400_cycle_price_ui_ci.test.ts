import assert from 'node:assert/strict';
import {parseCyclePriceInput,parseCycleContributionPolicy,parseCyclePriceChange} from '../services/cyclePriceBoundary';
const tenant='00000000-0000-4000-8000-000000000001';
const cycle='00000000-0000-4000-8000-000000000002';
assert.equal(parseCyclePriceInput('150,00'),15000);
assert.equal(parseCyclePriceInput('150.5'),15050);
assert.equal(parseCyclePriceInput('1'),100);
for(const bad of ['0','-1','1.234','1e2','R$ 150','10000,01','NaN','','1,000', '  ']){
 assert.throws(()=>parseCyclePriceInput(bad),/valor|Informe/i,bad);
}
const source={
 contract:'AI_STUDIO_M20400_CYCLE_PRICE_REVIEW_V1',
 source:'POSTGRESQL_VERIFIED_SESSION',
 tenant_id:tenant,cycle_id:cycle,cycle_year:2027,
 start_date:'2027-01-01',end_date:'2027-12-31',
 amount_cents:10000,policy_version:1,registered_contributions:1,
 can_edit:false,blocked_reason:'COMPETENCIAS_JA_REGISTRADAS',
 pending_requested_cents:15000,real_payments_enabled:false,
};
assert.equal(parseCycleContributionPolicy(source,tenant).amount_cents,10000);
assert.throws(()=>parseCycleContributionPolicy({...source,tenant_id:cycle},tenant));
assert.throws(()=>parseCycleContributionPolicy({...source,real_payments_enabled:true},tenant));
const request_id='00000000-0000-4000-8000-000000000004';
assert.equal(parseCyclePriceChange({
 ...source,change_status:'PENDING_REVIEW',request_id,existing_contributions_repriced:false,
}).change_status,'PENDING_REVIEW');
assert.throws(()=>parseCyclePriceChange({
 ...source,change_status:'APPLIED',request_id,existing_contributions_repriced:true,
}));
console.log('M20400_CYCLE_PRICE_AND_EXISTING_DEBT_GUARDS=PASS');
