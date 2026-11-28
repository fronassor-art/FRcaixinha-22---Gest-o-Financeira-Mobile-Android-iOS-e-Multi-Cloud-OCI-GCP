/** M39910: no-money documentary timeline strict contract tests. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseExclusiveCashboxHistory} from '../services/exclusiveCashboxHistoryBoundary';
import {isRoleTabAllowed} from '../services/roleScope';

const tenant='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const entry={
 id:'11111111-1111-4111-8111-111111111111',
 occurred_at:'2026-11-14T17:30:00+00:00',
 category:'SAAS_INTENT',state:'APPROVED',
 amount_cents:null,settlement_verified:false,
};
const master={
 source:'POSTGRESQL_RLS',scope:'MASTER_PLATFORM_SAAS_ONLY',tenant_id:null,
 entries:[entry,{...entry,id:'22222222-2222-4222-8222-222222222222',
   category:'SAAS_PREPARATION',state:'PENDING_PAYMENT',
   occurred_at:'2026-11-14T17:29:00+00:00'}],
 available_balance_cents:null,cash_movement_verified:false,
 transfer_enabled:false,status:'DOCUMENTARY_ONLY_NOT_RECONCILED',
};
const admin={
 ...master,scope:'TENANT_ADMIN_COLLECTIVE_REFERENCE_ONLY',tenant_id:tenant,
 entries:[{...entry,category:'TENANT_COLLECTIVE_LEDGER',
   state:'RECORDED_NOT_REMUNERATION'}],
};
assert.equal(parseExclusiveCashboxHistory(master,'MASTER').entries.length,2);
assert.equal(parseExclusiveCashboxHistory(admin,'TENANT_ADMIN',tenant).entries.length,1);
assert.equal(parseExclusiveCashboxHistory({...master,entries:[]},'MASTER').entries.length,0);

for(const invalid of [
 {...master,tenant_id:tenant},{...master,available_balance_cents:0},
 {...master,cash_movement_verified:true},{...master,transfer_enabled:true},
 {...master,status:'RECONCILED'},{...master,money:100},
 {...master,entries:[{...entry,amount_cents:10}]},
 {...master,entries:[{...entry,settlement_verified:true}]},
 {...master,entries:[{...entry,category:'TENANT_COLLECTIVE_LEDGER'}]},
 {...master,entries:[{...entry,state:'SETTLED'}]},
 {...master,entries:[{...entry,occurred_at:'2026-14-99T10:00:00Z'}]},
 {...master,entries:[{...entry,occurred_at:'2026-11-14'}]},
 {...master,entries:[{...entry,payer:'private'}]},
 {...master,entries:Array(11).fill(entry)},
 {...master,entries:[entry,entry]},
 {...master,entries:[master.entries[1],master.entries[0]]},
]){
 assert.throws(()=>parseExclusiveCashboxHistory(invalid,'MASTER'));
}
for(const invalid of [
 {...admin,tenant_id:'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'},
 {...admin,entries:[{...entry,category:'SAAS_INTENT'}]},
 {...admin,entries:[{...entry,category:'TENANT_COLLECTIVE_LEDGER',
   state:'ADMIN_PAID'}]},
 {...admin,entries:[{...entry,category:'TENANT_COLLECTIVE_LEDGER',
   state:'RECORDED_NOT_REMUNERATION',amount_cents:0}]},
]){
 assert.throws(()=>parseExclusiveCashboxHistory(invalid,'TENANT_ADMIN',tenant));
}
assert.throws(()=>parseExclusiveCashboxHistory(admin,'MASTER'));
assert.throws(()=>parseExclusiveCashboxHistory(master,'TENANT_ADMIN',tenant));
assert.equal(isRoleTabAllowed('TENANT_MEMBER','ADMIN_CASHBOX'),false);
assert.equal(isRoleTabAllowed('TENANT_MEMBER','MASTER_CASHBOX'),false);

const api=readFileSync('src/services/financialApiService.ts','utf8');
const view=readFileSync('src/components/ExclusiveCashboxView.tsx','utf8');
const router=readFileSync('backend/app/routers/exclusive_cashboxes.py','utf8');
assert.match(api,/fetchMasterExclusiveCashboxHistory\(/);
assert.match(api,/fetchTenantAdminExclusiveCashboxHistory\(/);
assert.match(api,/parseExclusiveCashboxHistory\(raw,'MASTER'\)/);
assert.match(api,/parseExclusiveCashboxHistory\(raw,'TENANT_ADMIN',tenantId\)/);
assert.match(view,/History|Histórico documental/);
assert.match(view,/Histórico não disponível nesta versão da API/);
assert.match(view,/não é extrato bancário/);
assert.match(view,/não é remuneração/);
assert.match(view,/authService\.isSessionSnapshotCurrent\(snapshot\)/);
assert.match(view,/catch\(\(\)=>/);
assert.match(router,/TENANT_ADMIN_COLLECTIVE_REFERENCE_ONLY/);
assert.match(router,/SELECT id,created_at FROM public\.ledger_transactions/);
assert.doesNotMatch(view,/authorizeLoanPixPayout\(|payContribution\(|createContributionPix\(/);

console.log('M39910_HISTORY_MASTER_AND_TENANT_STRICT=PASS');
console.log('M39910_CROSS_TENANT_AND_MEMBER_DENIAL=PASS');
console.log('M39910_NO_UNVERIFIED_MONEY_IN_HISTORY=PASS');
console.log('M39910_STALE_FASTAPI_FAIL_CLOSED=PASS');
