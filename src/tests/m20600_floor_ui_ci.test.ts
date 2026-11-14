import assert from 'node:assert/strict';
import {parseCyclePriceInput,parseCycleContributionPolicy} from '../services/cyclePriceBoundary';
assert.equal(parseCyclePriceInput('150'),15000);
assert.equal(parseCyclePriceInput('200,50'),20050);
for(const v of ['1','99','100','149,99','0','-1']) assert.throws(()=>parseCyclePriceInput(v));
const tenant='00000000-0000-4000-8000-000000000001';
const p={contract:'AI_STUDIO_M20400_CYCLE_PRICE_REVIEW_V1',source:'POSTGRESQL_VERIFIED_SESSION',
 tenant_id:tenant,cycle_id:'00000000-0000-4000-8000-000000000002',
 cycle_year:2027,start_date:'2027-01-01',end_date:'2027-12-31',
 amount_cents:20000,policy_version:1,registered_contributions:12,
 can_edit:false,blocked_reason:'COMPETENCIAS_JA_REGISTRADAS',
 pending_requested_cents:15000,real_payments_enabled:false};
assert.equal(parseCycleContributionPolicy(p,tenant).amount_cents,20000);
assert.throws(()=>parseCycleContributionPolicy({...p,amount_cents:10000},tenant));
assert.equal(parseCycleContributionPolicy(p,tenant).pending_requested_cents,15000);
console.log('M20600_CONTRACT_MINIMUM_150_UI_PASS');
