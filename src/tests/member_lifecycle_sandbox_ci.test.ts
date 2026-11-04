import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseLifecycleItem,parseLifecycleQueue} from '../services/memberLifecycleBoundary';
const T='00000000-0000-4000-8000-000000000001';
const B='00000000-0000-4000-8000-000000000002';
const M='00000000-0000-4000-8000-000000000003';
const U='00000000-0000-4000-8000-000000000004';
const C='00000000-0000-4000-8000-000000000005';
const Q='00000000-0000-4000-8000-000000000006';

const item={
 id:Q,tenant_id:T,cycle_id:C,membership_id:M,requested_by_user_id:U,
 request_kind:'VOLUNTARY_EXIT',policy_reference:'CI-POLICY-2027-ACCEPTED',
 status:'PENDING_REVIEW',requested_at:'2027-05-12T12:00:00+00:00',
 sandbox_only:true,bank_reconciled:false,financial_effect_applied:false,
 member_status_changed:false,profit_rights_modified:false,payment_authorized:false,
};
const queue={
 tenant_id:T,year:2027,scope:'SELF_READ_ONLY',items:[item],
 has_more:false,bank_reconciled:false,financial_effect_applied:false,
};
const parsed=parseLifecycleQueue(queue,T,2027,'TENANT_MEMBER');
assert.equal(parsed.items.length,1);
assert.equal(parsed.items[0].request_kind,'VOLUNTARY_EXIT');
assert.equal(parsed.items[0].financial_effect_applied,false);
assert.equal(parsed.items[0].profit_rights_modified,false);
assert.equal(parsed.items[0].payment_authorized,false);
assert.equal(parseLifecycleQueue(
 {...queue,scope:'TENANT_ADMIN_READ_ONLY'},T,2027,'TENANT_ADMIN'
).scope,'TENANT_ADMIN_READ_ONLY');
const bad=[
 {...item,tenant_id:B},{...item,id:'no'},
 {...item,cycle_id:'INVALID'},{...item,membership_id:'WRONG'},
 {...item,requested_by_user_id:'WRONG'},
 {...item,request_kind:'DELETE_MEMBER'},
 {...item,policy_reference:'BAD'},
 {...item,policy_reference:'leak token or PII'},
 {...item,status:'LIQUIDADO'},
 {...item,status:'CLOSED'},
 {...item,sandbox_only:false},
 {...item,bank_reconciled:true},
 {...item,financial_effect_applied:true},
 {...item,member_status_changed:true},
 {...item,profit_rights_modified:true},
 {...item,payment_authorized:true},
 {...item,requested_at:'invalid-date'},
 {...item,extra:'extra'},
];
for(const candidate of bad){
 assert.throws(()=>parseLifecycleItem(candidate,T));
}
const badQueue=[
 {...queue,tenant_id:B},
 {...queue,year:2028},
 {...queue,scope:'MASTER_READ_ONLY'},
 {...queue,has_more:true},
 {...queue,bank_reconciled:true},
 {...queue,financial_effect_applied:true},
 {...queue,items:[item,item]},
 {...queue,items:'wrong'},
 {...queue,items:Array.from({length:101},()=>item)},
 {...queue,extra:'secret'},
];
for(const v of badQueue){
 assert.throws(()=>parseLifecycleQueue(v,T,2027,'TENANT_MEMBER'));
}
for(let n=0;n<140;n++){
 const id=n.toString(16).padStart(12,'0');
 const list={...queue,items:[{
   ...item,id:'00000000-0000-4000-8000-'+id,
   request_kind:n%2?'DELINQUENCY_REVIEW':'VOLUNTARY_EXIT'
 }]};
 const current=parseLifecycleQueue(list,T,2027,'TENANT_MEMBER');
 assert.equal(current.items.length,1);
 assert.equal(current.items[0].financial_effect_applied,false);
}
const api=readFileSync('src/services/financialApiService.ts','utf8');
const panel=readFileSync('src/components/MemberLifecyclePanel.tsx','utf8');
const annual=readFileSync('src/components/MemberAnnualPreviewView.tsx','utf8');
assert.match(api,/fetchMemberLifecycleQueue/);
assert.match(api,/parseLifecycleQueue/);
assert.match(api,/assertTenantReadScope/);
assert.match(panel,/authService\.isSessionSnapshotCurrent/);
assert.match(panel,/Registrar um pedido não encerra vínculo/);
assert.match(panel,/bank_reconciled|Efeito financeiro: nenhum/);
assert.match(annual,/<MemberLifecyclePanel state=\{state\}\/>/);
assert.doesNotMatch(panel,/localStorage|closeCycle|createPix|releaseLoan/);
console.log('M761_CLIENTE_FILA_CICLO=PASS; MALFORMED='+bad.length+
            '; QUEUE_MALFORMED='+badQueue.length+
            '; SYNTHETIC_CASES=140');
