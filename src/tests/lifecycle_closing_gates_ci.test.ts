import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseLifecycleClosingGates} from '../services/memberLifecycleBoundary';
const T='00000000-0000-4000-8000-000000000001';
const C='00000000-0000-4000-8000-000000000002';
const B='00000000-0000-4000-8000-000000000003';
const value={
 tenant_id:T,cycle_id:C,year:2027,
 pending_voluntary_exits:1,pending_delinquency_reviews:1,
 registered_unsettled_contributions:23,unclosed_loans:1,
 status:'REVIEW_AND_BANK_EVIDENCE_REQUIRED',
 bank_reconciled:false,can_close_cycle:false,
 can_distribute_profit:false,real_payout_enabled:false,
};
const parsed=parseLifecycleClosingGates(value,T,2027);
assert.equal(parsed.registered_unsettled_contributions,23);
assert.equal(parsed.pending_voluntary_exits,1);
assert.equal(parsed.can_close_cycle,false);
assert.equal(parsed.can_distribute_profit,false);
assert.equal(parsed.real_payout_enabled,false);

const invalid=[
 {...value,tenant_id:B},{...value,cycle_id:'wrong'},
 {...value,year:2028},{...value,bank_reconciled:true},
 {...value,can_close_cycle:true},{...value,can_distribute_profit:true},
 {...value,real_payout_enabled:true},
 {...value,pending_voluntary_exits:-1},
 {...value,pending_delinquency_reviews:1.25},
 {...value,registered_unsettled_contributions:'23'},
 {...value,unclosed_loans:1e40},
 {...value,status:'READY_FOR_SETTLEMENT'},
 {...value,status:'LIQUIDADO'},
 {...value,master_revenue_cents:1500},
 {...value,member_profit_cents:8500},
 {...value,access_token:'EXPOSED'},
];
for(const candidate of invalid){
 assert.throws(()=>parseLifecycleClosingGates(candidate,T,2027));
}
for(let n=0;n<260;n++){
 const record={...value,
   pending_voluntary_exits:n%8,
   pending_delinquency_reviews:n%7,
   registered_unsettled_contributions:n,
   unclosed_loans:n%9,
 };
 const r=parseLifecycleClosingGates(record,T,2027);
 assert.equal(r.registered_unsettled_contributions,n);
 assert.equal(r.pending_voluntary_exits,n%8);
 assert.equal(r.pending_delinquency_reviews,n%7);
 assert.equal(r.can_close_cycle,false);
 assert.equal(r.real_payout_enabled,false);
}
const service=readFileSync('src/services/financialApiService.ts','utf8');
const ui=readFileSync('src/components/MemberLifecyclePanel.tsx','utf8');
assert.match(service,/fetchLifecycleClosingGates/);
assert.match(service,/parseLifecycleClosingGates/);
assert.match(service,/member-lifecycle\/closing-gates/);
assert.match(service,/role!=='TENANT_ADMIN'/);
assert.match(ui,/fetchLifecycleClosingGates/);
assert.match(ui,/Nenhum desses dados é saldo bancário conciliado/);
assert.match(ui,/closing\.pending_voluntary_exits/);
assert.match(ui,/closing\.unclosed_loans/);
assert.doesNotMatch(ui,/localStorage|createPix|closeCycle/);
console.log('M921_CLOSING_GATES_UI=PASS; MALFORMED='+invalid.length+
  '; SYNTHETIC_CASES=260; MONEY_REAL=0');
