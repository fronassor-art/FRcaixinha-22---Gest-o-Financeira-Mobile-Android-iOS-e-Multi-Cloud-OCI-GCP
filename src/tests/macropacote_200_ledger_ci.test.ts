/* Macropacote 200: contratos sintéticos de integridade e segregação. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseLedgerIntegrityPreview} from '../services/ledgerIntegrityPreview';
const A='00000000-0000-4000-8000-000000000001';
const B='00000000-0000-4000-8000-000000000002';
const good={
 source:'POSTGRESQL_RLS',scope:'TENANT_ADMIN_READ_ONLY',tenant_id:A,
 checked_transactions:2,balanced_transactions:2,review_required_transactions:0,
 status:'BALANCED',bank_reconciled:false,financial_closing_authorized:false
};
let checks=0;const check=(f:()=>void)=>{f();checks++};
const reject=(x:unknown)=>assert.throws(()=>parseLedgerIntegrityPreview(x,A));
const parsed=parseLedgerIntegrityPreview(good,A);
check(()=>assert.equal(parsed.status,'BALANCED'));
check(()=>assert.equal(parsed.checked_transactions,2));
check(()=>assert.equal(parsed.bank_reconciled,false));
check(()=>assert.equal(parsed.financial_closing_authorized,false));
check(()=>assert.equal(parseLedgerIntegrityPreview({
 ...good,checked_transactions:0,balanced_transactions:0,status:'NO_TRANSACTIONS'
},A).status,'NO_TRANSACTIONS'));
check(()=>assert.equal(parseLedgerIntegrityPreview({
 ...good,balanced_transactions:1,review_required_transactions:1,status:'REVIEW_REQUIRED'
},A).status,'REVIEW_REQUIRED'));
check(()=>reject({...good,tenant_id:B}));
check(()=>reject({...good,source:'LOCAL_SEED'}));
check(()=>reject({...good,scope:'MASTER'}));
check(()=>reject({...good,bank_reconciled:true}));
check(()=>reject({...good,financial_closing_authorized:true}));
check(()=>reject({...good,checked_transactions:1}));
check(()=>reject({...good,balanced_transactions:3}));
check(()=>reject({...good,review_required_transactions:-1}));
check(()=>reject({...good,status:'REVIEW_REQUIRED'}));
check(()=>reject({...good,checked_transactions:501,balanced_transactions:501}));
check(()=>reject({...good,token:'SECRET'}));
check(()=>reject({...good,cpf:'SECRET'}));
check(()=>reject({...good,balance_cents:200}));
check(()=>reject({...good,transaction_details:[{id:'x'}]}));
assert.equal(checks,20);
const api=readFileSync('src/services/financialApiService.ts','utf8');
const view=readFileSync('src/components/LedgerView.tsx','utf8');
const backend=readFileSync('backend/app/routers/ledger.py','utf8');
const audit=readFileSync('backend/app/routers/audit.py','utf8');
const closings=readFileSync('backend/app/routers/closings.py','utf8');
assert.match(api,/assertLedgerAdmin\(tenantId\)/);
assert.match(api,/parseLedgerIntegrityPreview\(raw,tenantId\)/);
assert.match(view,/fetchLedgerIntegrityPreview\(state\.currentTenantId\)/);
assert.match(view,/integrity\.status!=='BALANCED'/);
assert.match(view,/authService\.isSessionSnapshotCurrent\(snapshot\)/);
assert.match(view,/Integridade matemática não é conciliação bancária/);
assert.match(backend,/async def get_ledger_integrity_preview/);
assert.match(backend,/WHERE t\.tenant_id=\$1/);
assert.match(audit,/Registro manual de auditoria indisponível/);
assert.match(closings,/Fechamento indisponível até validação/);
console.log('MACROPACOTE_200_LEDGER_CI=PASS');
