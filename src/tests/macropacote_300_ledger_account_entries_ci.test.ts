import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseLedgerAccountJournalPage as parse} from '../services/ledgerAccountJournalBoundary';
const T='00000000-0000-4000-8000-000000000001';
const A='00000000-0000-4000-8000-000000000002';
const B='00000000-0000-4000-8000-000000000003';
const entry={id:'00000000-0000-4000-8000-000000000010',
 transaction_id:'00000000-0000-4000-8000-000000000011',
 transaction_date:'2027-01-10T12:00:00+00:00',
 description:'Lançamento sintético',reference_id:'CI:READ_ONLY',
 entry_type:'DR',amount_cents:125,amount_brl:'1.25'};
const good={source:'POSTGRESQL_RLS',tenant_id:T,account_id:A,
 page:1,page_size:25,has_more:false,complete_ledger_verified:false,
 bank_reconciled:false,financial_closing_authorized:false,entries:[entry]};
assert.equal(parse(good,T,A,1,25).entries[0].amount_cents,125);
assert.equal(parse({...good,entries:[]},T,A,1,25).entries.length,0);
const bad=(obj:unknown,t=T,a=A,page=1,size=25)=>assert.throws(()=>parse(obj,t,a,page,size));
bad({...good,tenant_id:B});
bad({...good,account_id:B});
bad({...good,page:2});
bad({...good,page_size:50});
bad({...good,source:'SEED_LOCAL'});
bad({...good,complete_ledger_verified:true});
bad({...good,bank_reconciled:true});
bad({...good,financial_closing_authorized:true});
bad({...good,has_more:'yes'});
bad({...good,has_more:true});
bad({...good,entries:[entry,entry]});
bad({...good,entries:[{...entry,cpf:'123'}]});
bad({...good,entries:[{...entry,amount_cents:126}]});
bad({...good,entries:[{...entry,amount_cents:NaN}]});
bad({...good,entries:[{...entry,amount_cents:-1}]});
bad({...good,entries:[{...entry,amount_brl:'1.251'}]});
bad({...good,entries:[{...entry,entry_type:'CREDIT'}]});
bad({...good,entries:[{...entry,transaction_id:'bad'}]});
bad({...good,entries:[{...entry,transaction_date:'2027-99-99T12:00:00Z'}]});
bad({...good,token:'sensitive'});
bad({...good,entries:Array(26).fill(entry)});
const api=readFileSync('src/services/financialApiService.ts','utf8');
assert.match(api,/fetchLedgerAccountJournal/);
assert.match(api,/this.assertLedgerAdmin\(tenantId\)/);
assert.match(api,/parseLedgerAccountJournalPage\(raw,tenantId,accountId,page,pageSize\)/);
const view=readFileSync('src/components/LedgerView.tsx','utf8');
const component=readFileSync('src/components/LedgerAccountEntries.tsx','utf8');
assert.match(view,/Ver extrato da conta/);
assert.match(view,/LedgerAccountEntries/);
assert.match(component,/isSessionSnapshotCurrent\(snapshot\)/);
assert.match(component,/has_more/);
assert.match(component,/Não comprova completude do Livro-Razão/);
console.log('FR_CAIXINHA_M300_LEDGER_ACCOUNT_JOURNAL=PASS');
