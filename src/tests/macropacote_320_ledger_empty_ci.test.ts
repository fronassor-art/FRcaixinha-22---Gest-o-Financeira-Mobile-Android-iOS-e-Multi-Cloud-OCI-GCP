import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseLedgerAccountDirectory} from '../services/ledgerAccountDirectoryBoundary';

const T='00000000-0000-4000-8000-000000000001';
const B='00000000-0000-4000-8000-000000000002';
const X='00000000-0000-4000-8000-000000000003';
const account={id:X,account_code:'1.1.1',account_name:'Conta sintética sem saldo',
 account_type:'ASSET'};
const good={source:'POSTGRESQL_RLS',scope:'TENANT_ADMIN_READ_ONLY',tenant_id:T,
 accounts:[account],balance_values_hidden:true,complete_ledger_verified:false,
 bank_reconciled:false,financial_closing_authorized:false};
assert.deepEqual(parseLedgerAccountDirectory(good,T).accounts,[account]);
assert.deepEqual(parseLedgerAccountDirectory({...good,accounts:[]},T).accounts,[]);
const bad=(v:unknown)=>assert.throws(()=>parseLedgerAccountDirectory(v,T));
bad({...good,tenant_id:B});
bad({...good,source:'SEED_LOCAL'});
bad({...good,scope:'MASTER'});
bad({...good,balance_values_hidden:false});
bad({...good,complete_ledger_verified:true});
bad({...good,bank_reconciled:true});
bad({...good,financial_closing_authorized:true});
bad({...good,accounts:[account,account]});
bad({...good,accounts:[account,{...account,id:B}]});
bad({...good,accounts:[{...account,account_code:'',id:B}]});
bad({...good,accounts:[{...account,account_code:'x;DROP'}]});
bad({...good,accounts:[{...account,account_name:''}]});
bad({...good,accounts:[{...account,account_name:'x\ninvalid'}]});
bad({...good,accounts:[{...account,account_type:''}]});
bad({...good,accounts:[{...account,id:'bad'}]});
bad({...good,accounts:[{...account,balance_cents:999}]});
bad({...good,accounts:[{...account,tenant_id:B}]});
bad({...good,accounts:Array.from({length:501},(_,i)=>({...account,id:X}))});
bad({...good,sensitive_token:'secret'});

const financialApi=readFileSync('src/services/financialApiService.ts','utf8');
const view=readFileSync('src/components/LedgerView.tsx','utf8');
const entries=readFileSync('src/components/LedgerAccountEntries.tsx','utf8');
assert.match(financialApi,/fetchLedgerAccountDirectory\(tenantId:string\)/);
assert.match(financialApi,/this.assertLedgerAdmin\(tenantId\)/);
assert.match(financialApi,/parseLedgerAccountDirectory\(raw,tenantId\)/);
assert.match(view,/integrity.status!=='BALANCED'/);
assert.match(view,/ledgerReadMode\(integrity\)==='DIRECTORY_WITHOUT_BALANCES'/);
assert.match(view,/fetchLedgerAccountDirectory\(state.currentTenantId!\)/);
assert.match(view,/current.integrity\?\.status==='NO_TRANSACTIONS'/);
assert.match(view,/current.directory.accounts.map\(account/);
assert.match(view,/Ver extrato da conta/);
assert.match(view,/Nenhuma conta contábil cadastrada/);
assert.match(view,/nunca saldos ou lançamentos simulados/);
assert.match(view,/isSessionSnapshotCurrent\(snapshot\)/);
assert.match(view,/setSelectedAccountId\(null\)/);
assert.match(entries,/LedgerAccountDirectoryItem/);
assert.match(entries,/isSessionSnapshotCurrent\(snapshot\)/);
assert.doesNotMatch(view,/Math.random\(|setTimeout\(/);
console.log('FR_CAIXINHA_M320_EMPTY_DIRECTORY_AND_SECURITY=PASS');
