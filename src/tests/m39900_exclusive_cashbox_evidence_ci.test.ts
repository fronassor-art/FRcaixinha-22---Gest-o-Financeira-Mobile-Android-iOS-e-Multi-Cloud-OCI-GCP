/** M39900: offline-exclusive read model with no fabricated money. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {masterCashboxEvidence,adminCashboxEvidence} from '../services/exclusiveCashboxEvidence';
import {parseMasterExclusiveCashbox,parseTenantAdminExclusiveCashbox} from '../services/exclusiveCashboxBoundary';
import {isRoleTabAllowed} from '../services/roleScope';

const tenant='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const m=parseMasterExclusiveCashbox({
  source:'POSTGRESQL_RLS',scope:'MASTER_PLATFORM_SAAS_ONLY',tenant_id:null,
  cashbox:'PLATFORM_SAAS',payment_intents_count:11,
  subscription_preparations_count:4,settled_balance_cents:null,
  bank_reconciled:false,transfer_enabled:false,real_payments_enabled:false,
  status:'AWAITING_PROVIDER_RECONCILIATION',
});
const a=parseTenantAdminExclusiveCashbox({
  source:'POSTGRESQL_RLS',scope:'TENANT_ADMIN_OWN_REMUNERATION_ONLY',tenant_id:tenant,
  cashbox:'TENANT_ADMIN_REMUNERATION',ledger_transactions_count:17,
  administrator_profit_share_pct:'15.00',members_profit_share_pct:'85.00',
  settled_balance_cents:null,bank_reconciled:false,closing_authorized:false,
  transfer_enabled:false,real_payments_enabled:false,
  status:'AWAITING_CLOSING_AND_RECONCILIATION',
},tenant);

const master=masterCashboxEvidence(m);
assert.equal(master.length,5);
assert.deepEqual(master.filter(x=>x.kind==='COUNT_ONLY').map(x=>x.count),[11,4]);
assert.equal(master.find(x=>x.id==='platform-expenses')?.kind,'NOT_ATTESTED');
assert.equal(master.find(x=>x.id==='platform-history')?.kind,'NOT_ATTESTED');
assert.equal(master.find(x=>x.id==='platform-reconciliation')?.kind,'NOT_ATTESTED');
assert(master.every(x=>!('amount_cents' in x)&&!('balance' in x)));
assert(!master.some(x=>x.id.includes('tenant-ledger')));

const admin=adminCashboxEvidence(a);
assert.equal(admin.length,5);
assert.equal(admin.filter(x=>x.kind==='COUNT_ONLY').length,1);
assert.equal(admin[0].count,17);
assert.match(admin[0].detail,/não remuneração pessoal/);
assert.equal(admin.find(x=>x.id==='administrator-remuneration')?.kind,'NOT_ATTESTED');
assert.equal(admin.find(x=>x.id==='administrator-expenses')?.kind,'NOT_ATTESTED');
assert.equal(admin.find(x=>x.id==='administrator-history')?.kind,'NOT_ATTESTED');
assert.equal(admin.find(x=>x.id==='administrator-reconciliation')?.kind,'NOT_ATTESTED');
assert(admin.every(x=>!('amount_cents' in x)&&!('balance' in x)));
assert(!admin.some(x=>x.id.startsWith('saas-')));

for(const [role,masterAllowed,adminAllowed] of [
  ['MASTER',true,false],['TENANT_ADMIN',false,true],['TENANT_MEMBER',false,false],
] as const){
  assert.equal(isRoleTabAllowed(role,'MASTER_CASHBOX'),masterAllowed);
  assert.equal(isRoleTabAllowed(role,'ADMIN_CASHBOX'),adminAllowed);
}
assert.throws(()=>parseMasterExclusiveCashbox({...m,settled_balance_cents:0}));
assert.throws(()=>parseTenantAdminExclusiveCashbox({...a,transfer_enabled:true},tenant));

const view=readFileSync('src/components/ExclusiveCashboxView.tsx','utf8');
const boundary=readFileSync('src/services/exclusiveCashboxEvidence.ts','utf8');
const api=readFileSync('backend/app/routers/exclusive_cashboxes.py','utf8');
assert.match(view,/masterCashboxEvidence\(current\.master\)/);
assert.match(view,/adminCashboxEvidence\(current\.admin\)/);
assert.match(view,/authService\.isSessionSnapshotCurrent\(snapshot\)/);
assert.match(view,/política versionada comprovada/);
assert.match(view,/15% do lucro líquido elegível/);
assert.match(view,/Não disponível/);
assert.match(view,/Aguardando comprovação/);
assert.match(view,/somente quantidade/);
assert.match(boundary,/Não há extrato de despesas da plataforma/);
assert.match(boundary,/não remuneração pessoal do administrador/);
assert.match(api,/require_tenant_access\(str\(tenant_id\), session\)/);
assert.match(api,/session\.role != "TENANT_ADMIN"/);
assert.match(api,/Depends\(require_master\)/);
assert.doesNotMatch(view,/onOpenPixModal|payContribution\(|createContributionPix\(|authorizeLoanPixPayout\(/);
assert.doesNotMatch(boundary,/localStorage|sessionStorage|fetch\(|POST|PATCH|DELETE/);

console.log('M39900_MASTER_SAAS_ONLY=PASS');
console.log('M39900_ADMIN_REMUNERATION_SEPARATE_FROM_COLLECTIVE=PASS');
console.log('M39900_NO_FAKE_BALANCES_EXPENSES_OR_WITHDRAWAL=PASS');
console.log('M39900_RBAC_ROLE_SWITCH=PASS');
