import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseCyclePriceInput} from '../services/cyclePriceBoundary';
import {parseCycleOpeningReceipt,parseCycleOpeningPreview} from '../services/cycleOpeningBoundary';
const tenant='00000000-0000-4000-8000-0000000000a1';
const amount=32500;
assert.equal(parseCyclePriceInput('325,00'),amount);
for(const price of ['100','149,99','0'])assert.throws(()=>parseCyclePriceInput(price));
const receipt={
 contract:'FR_FINANCE_M37423_CYCLE_OPENING_V1',
 source:'POSTGRESQL_AUTHENTICATED_ADMIN_M044',
 tenant_id:tenant,opened_cycle_id:'00000000-0000-4000-8000-0000000000b1',
 opened_policy_id:'00000000-0000-4000-8000-0000000000b2',
 year:2030,amount_cents:32500,opening_status:'CREATED',
 opening_audit_persisted:true,existing_contributions_repriced:false,payments_executed:false,
};
assert.equal(parseCycleOpeningReceipt(receipt,tenant).amount_cents,amount);
for(const x of [
 {...receipt,amount_cents:10000},{...receipt,opening_audit_persisted:false},
 {...receipt,tenant_id:'other'},{...receipt,payments_executed:true},
 {...receipt,existing_contributions_repriced:true},{...receipt,opening_status:'FAKE'},
])assert.throws(()=>parseCycleOpeningReceipt(x,tenant));
const preview={
 contract:'AI_STUDIO_M20800_CYCLE_OPENING_PREVIEW_V1',
 source:'POSTGRESQL_RLS_AUTHENTICATED_ADMIN',tenant_id:tenant,
 year:2030,start_date:'2030-01-01',end_date:'2030-12-31',
 amount_cents:32500,minimum_amount_cents:15000,
 price_explicitly_entered:true,historical_obligations_unchanged:true,
 blocked_reasons:[],preconditions_satisfied:true,cycle_creation_enabled:true,
 financial_effect:false,reason_recorded:false,
};
assert.equal(parseCycleOpeningPreview(preview,tenant).cycle_creation_enabled,true);
assert.throws(()=>parseCycleOpeningPreview({...preview,amount_cents:10000},tenant));
const screen=readFileSync('src/components/CycleOpeningPreviewPanel.tsx','utf8');
assert.match(screen,/setAmount\] =useState|setAmount\]=useState/);
assert.match(screen,/Confirmar abertura do ciclo/);
assert.match(screen,/preview\.cycle_creation_enabled/);
assert.match(screen,/crypto\.randomUUID/);
assert.match(screen,/financialApi\.openCycle/);
assert.doesNotMatch(screen,/useState\(['"]150|defaultValue=['"]150/);
console.log('M37427_EXPLICIT_ADMIN_SELECTED_CYCLE_AMOUNT=PASS');
