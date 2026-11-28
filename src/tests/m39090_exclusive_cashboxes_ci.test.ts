/** FR Finance M39090 — full source + parser regression, no network/PG. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {tabsAllowedToRole,isRoleTabAllowed,initialRoleTab} from '../services/roleScope';
import {
  parseMasterExclusiveCashbox,parseTenantAdminExclusiveCashbox,
} from '../services/exclusiveCashboxBoundary';

const TENANT='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const master={
  source:'POSTGRESQL_RLS',scope:'MASTER_PLATFORM_SAAS_ONLY',tenant_id:null,
  cashbox:'PLATFORM_SAAS',payment_intents_count:3,
  subscription_preparations_count:2,settled_balance_cents:null,
  bank_reconciled:false,transfer_enabled:false,real_payments_enabled:false,
  status:'AWAITING_PROVIDER_RECONCILIATION',
};
const admin={
  source:'POSTGRESQL_RLS',scope:'TENANT_ADMIN_OWN_REMUNERATION_ONLY',tenant_id:TENANT,
  cashbox:'TENANT_ADMIN_REMUNERATION',ledger_transactions_count:7,
  administrator_profit_share_pct:'15.00',members_profit_share_pct:'85.00',
  settled_balance_cents:null,bank_reconciled:false,closing_authorized:false,
  transfer_enabled:false,real_payments_enabled:false,
  status:'AWAITING_CLOSING_AND_RECONCILIATION',
};
assert.equal(parseMasterExclusiveCashbox(master).payment_intents_count,3);
assert.equal(parseTenantAdminExclusiveCashbox(admin,TENANT).ledger_transactions_count,7);
for(const x of [
  {...master,settled_balance_cents:0}, {...master,transfer_enabled:true},
  {...master,bank_reconciled:true}, {...master,payment_intents_count:1.5},
  {...master,tenant_id:TENANT}, {...master,balance:99999},
  {...master,scope:'TENANT_ADMIN_OWN_REMUNERATION_ONLY'},
]){
  assert.throws(()=>parseMasterExclusiveCashbox(x));
}
for(const x of [
  {...admin,tenant_id:'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'},
  {...admin,administrator_profit_share_pct:'100.00'},
  {...admin,members_profit_share_pct:'0.00'},
  {...admin,closing_authorized:true},
  {...admin,settled_balance_cents:0},
  {...admin,ledger_transactions_count:-1},
  {...admin,real_payments_enabled:true},
]){
  assert.throws(()=>parseTenantAdminExclusiveCashbox(x,TENANT));
}
for(const role of ['MASTER','TENANT_ADMIN','TENANT_MEMBER'] as const){
  const permitted=role==='MASTER'?'MASTER_CASHBOX':
    role==='TENANT_ADMIN'?'ADMIN_CASHBOX':null;
  for(const tab of ['MASTER_CASHBOX','ADMIN_CASHBOX']){
    assert.equal(isRoleTabAllowed(role,tab),tab===permitted);
  }
}
assert.equal(initialRoleTab('MASTER'),'DASHBOARD');
assert.equal(initialRoleTab('TENANT_ADMIN'),'DASHBOARD');
assert(!tabsAllowedToRole('TENANT_MEMBER').includes('ADMIN_CASHBOX'));
assert(!tabsAllowedToRole('TENANT_MEMBER').includes('MASTER_CASHBOX'));

const app=readFileSync('src/App.tsx','utf8');
const dash=readFileSync('src/components/DashboardView.tsx','utf8');
const view=readFileSync('src/components/ExclusiveCashboxView.tsx','utf8');
const api=readFileSync('src/services/financialApiService.ts','utf8');
assert.match(app,/visibleTab === 'MASTER_CASHBOX' && state.currentRole === 'MASTER'/);
assert.match(app,/visibleTab === 'ADMIN_CASHBOX' && state.currentRole === 'TENANT_ADMIN'/);
assert.match(app,/ExclusiveCashboxView state=\{state\}/);
assert.match(dash,/onNavigateTab\('MASTER_CASHBOX'\)/);
assert.match(dash,/onNavigateTab\('ADMIN_CASHBOX'\)/);
assert.match(api,/authService.getUser\(\)/);
assert.match(api,/parseMasterExclusiveCashbox\(raw\)/);
assert.match(api,/parseTenantAdminExclusiveCashbox\(raw,tenantId\)/);
assert.match(view,/authService.isSessionSnapshotCurrent\(snapshot\)/);
assert.match(view,/Saldo conciliado e disponível/);
assert.match(view,/Não disponível/);
assert.match(view,/15% do lucro líquido elegível/);
assert.doesNotMatch(view,/onOpenPixModal|pix\.create|transfer\(/i);
console.log('M39090_MASTER_ADMIN_EXCLUSIVE_CASHBOX=PASS');
console.log('M39090_TENANT_RBAC_AND_NO_FABRICATED_BALANCE=PASS');
