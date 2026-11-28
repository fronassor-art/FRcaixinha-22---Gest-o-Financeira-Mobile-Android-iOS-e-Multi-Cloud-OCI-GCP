import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  parseLifecycleCapabilities, parseLifecycleItem, LifecycleCapabilities,
} from '../services/memberLifecycleBoundary';

const T='00000000-0000-4000-8000-000000000001';
const C='00000000-0000-4000-8000-000000000002';
const M='00000000-0000-4000-8000-000000000003';
const U='00000000-0000-4000-8000-000000000004';
const I='00000000-0000-4000-8000-000000000005';
const member={
 tenant_id:T,year:2027,role:'TENANT_MEMBER',
 schema_ready:true,sandbox_only:true,can_submit_voluntary_exit:true,
 can_submit_delinquency_review:false,financial_effects_enabled:false,
 bank_reconciled:false,production_payments_enabled:false,
} as const;
const admin={...member,role:'TENANT_ADMIN',
  can_submit_voluntary_exit:false,can_submit_delinquency_review:true} as const;
const off={...member,schema_ready:false,
  can_submit_voluntary_exit:false,can_submit_delinquency_review:false} as const;
for(const sample of [member,admin,off]){
 const r=parseLifecycleCapabilities(
   sample,T,2027,sample.role as 'TENANT_MEMBER'|'TENANT_ADMIN'
 );
 assert.equal(r.sandbox_only,true);
 assert.equal(r.financial_effects_enabled,false);
 assert.equal(r.production_payments_enabled,false);
 assert.equal(r.bank_reconciled,false);
}
const invalid=[
 {...member,tenant_id:C},{...member,year:2028},
 {...member,role:'MASTER'},
 {...member,schema_ready:false},
 {...member,financial_effects_enabled:true},
 {...member,production_payments_enabled:true},
 {...member,bank_reconciled:true},
 {...member,sandbox_only:false},
 {...member,can_submit_delinquency_review:true},
 {...member,can_submit_voluntary_exit:'yes'},
 {...member,can_submit_voluntary_exit:1},
 {...member,additional_field:'UNTRUSTED'},
 {...member,policy_reference:'ADMIN_OVERRIDE'},
 {...member,auth_token:'secret'},
 {...member,can_submit_voluntary_exit:null},
];
for(const x of invalid){
 assert.throws(()=>parseLifecycleCapabilities(x,T,2027,'TENANT_MEMBER'));
}
for(let i=0;i<240;i++){
 const role=i%2===0?'TENANT_MEMBER':'TENANT_ADMIN';
 const ready=i%3===0;
 const c={
   ...member,role,schema_ready:ready,
   can_submit_voluntary_exit:ready&&role==='TENANT_MEMBER',
   can_submit_delinquency_review:ready&&role==='TENANT_ADMIN'
 };
 const out:LifecycleCapabilities=parseLifecycleCapabilities(c,T,2027,role);
 assert.equal(out.schema_ready,ready);
 assert.equal(out.can_submit_voluntary_exit,ready&&role==='TENANT_MEMBER');
 assert.equal(out.can_submit_delinquency_review,ready&&role==='TENANT_ADMIN');
 assert.equal(out.financial_effects_enabled,false);
}
const item={
 id:I,tenant_id:T,cycle_id:C,membership_id:M,requested_by_user_id:U,
 request_kind:'VOLUNTARY_EXIT',policy_reference:'SANDBOX-MASTER-2027-NO-EFFECTS',
 status:'PENDING_REVIEW',requested_at:'2027-05-12T12:00:00+00:00',
 latest_review_event:null,technical_review_pending:true,
 sandbox_only:true,bank_reconciled:false,financial_effect_applied:false,
 member_status_changed:false,profit_rights_modified:false,payment_authorized:false,
};
assert.equal(parseLifecycleItem(item,T).status,'PENDING_REVIEW');
assert.equal(parseLifecycleItem({
 ...item,latest_review_event:'ADMIN_REVIEW_REJECTED_SANDBOX',
 technical_review_pending:false
},T).technical_review_pending,false);

const api=readFileSync('src/services/financialApiService.ts','utf8');
const panel=readFileSync('src/components/MemberLifecyclePanel.tsx','utf8');
assert.match(api,/fetchMemberLifecycleCapabilities/);
assert.match(api,/parseLifecycleCapabilities/);
assert.match(api,/submitMemberLifecycleSandbox/);
assert.match(api,/parseLifecycleItem/);
assert.match(api,/idempotency_key:key/);
assert.match(api,/\/me\/voluntary-exit/);
assert.match(api,/delinquency-review/);
assert.match(panel,/can_submit_voluntary_exit/);
assert.match(panel,/can_submit_delinquency_review/);
assert.match(panel,/Confirmo que este é um TESTE/);
assert.match(panel,/globalThis\.crypto\?\.randomUUID/);
assert.match(panel,/authService\.isSessionSnapshotCurrent/);
assert.match(panel,/requestKey\.current/);
assert.match(panel,/if\(!supported\|\|!tenant\)return/);
assert.match(panel,/membro|membro/i);
assert.doesNotMatch(panel,/localStorage|closeCycle|createPix|releaseLoan/);
console.log('M921_CAPABILITIES_UI_SANDBOX=PASS; INVALID='+invalid.length+
  '; ROLE_SCHEMA_COMBINATIONS=240; FINANCIAL_EFFECTS=OFF');
