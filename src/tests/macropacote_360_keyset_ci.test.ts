import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseLedgerKeysetPage as parse} from '../services/ledgerKeysetBoundary';
import {initialJournalNavigation,nextJournalNavigation,previousJournalNavigation} from '../services/ledgerJournalCursorNavigation';
const T='00000000-0000-4000-8000-000000000001';
const A='00000000-0000-4000-8000-000000000002';
const OTHER='00000000-0000-4000-8000-000000000003';
const entry=(i:number)=>({
 id:'00000000-0000-4000-8000-'+i.toString(16).padStart(12,'0'),
 transaction_id:'00000000-0000-4000-8000-'+(i+100).toString(16).padStart(12,'0'),
 transaction_date:'2027-01-10T12:00:00+00:00',description:'Lancamento sintético',
 reference_id:'CI:READ_ONLY',entry_type:'DR',amount_cents:125,amount_brl:'1.25',
});
const cursor='YWJj';
const many=Array.from({length:25},(_,i)=>entry(i+10));
const first={source:'POSTGRESQL_RLS',tenant_id:T,account_id:A,page_size:25,
 has_more:true,next_cursor:cursor,complete_ledger_verified:false,
 bank_reconciled:false,financial_closing_authorized:false,entries:many};
assert.equal(parse(first,T,A,25).entries.length,25);
const last={...first,has_more:false,next_cursor:null,entries:[entry(50)]};
assert.equal(parse(last,T,A,25).has_more,false);
assert.equal(parse({...last,entries:[]},T,A,25).entries.length,0);
const bad=(v:unknown,t=T,a=A,s=25)=>assert.throws(()=>parse(v,t,a,s));
bad({...first,tenant_id:OTHER});
bad({...first,account_id:OTHER});
bad({...first,source:'MOCK'});
bad({...first,page_size:50});
bad({...first,has_more:false});
bad({...first,next_cursor:null});
bad({...last,next_cursor:cursor});
bad({...first,next_cursor:'a%2Fb'});
bad({...first,next_cursor:'x'.repeat(401)});
bad({...first,next_cursor:''});
bad({...first,next_cursor:23});
bad({...first,balance_cents:9999});
bad({...first,token:'secret'});
bad({...first,bank_reconciled:true});
bad({...first,complete_ledger_verified:true});
bad({...first,financial_closing_authorized:true});
bad({...first,entries:[]});
bad({...first,entries:[...many,entry(49)]});
bad({...first,entries:many.map((e,i)=>i===1?many[0]:e)});
bad({...last,entries:[{...entry(10),amount_cents:-1}]});
bad({...last,entries:[{...entry(10),entry_type:'ZZ'}]});
bad({...last,entries:[{...entry(10),amount_brl:'999.00'}]});
bad({...last,entries:[{...entry(10),tenant_id:OTHER}]});
bad({...last,entries:[{...entry(10),transaction_id:'bad'}]});
bad(null);
bad([]);
const n1=initialJournalNavigation();
assert.equal(n1.page,1);
assert.deepEqual(n1.cursors,[null]);
assert.equal(previousJournalNavigation(n1).page,1);
const n2=nextJournalNavigation(n1,{has_more:true,next_cursor:cursor});
assert.equal(n2.page,2);
assert.deepEqual(n2.cursors,[null,cursor]);
assert.equal(previousJournalNavigation(n2).page,1);
const backAndForward=nextJournalNavigation(previousJournalNavigation(n2),
 {has_more:true,next_cursor:'bmV3'});
assert.equal(backAndForward.page,2);
assert.deepEqual(backAndForward.cursors,[null,'bmV3']);
assert.deepEqual(n2.cursors,[null,cursor]);
assert.equal(nextJournalNavigation(n2,{has_more:false,next_cursor:null}).page,2);
assert.equal(nextJournalNavigation(n1,{has_more:true,next_cursor:null}).page,1);
assert.equal(nextJournalNavigation({...n1,page:1000,cursors:Array(1000).fill(cursor)},
 {has_more:true,next_cursor:cursor}).page,1000);
const api=readFileSync('src/services/financialApiService.ts','utf8');
const ui=readFileSync('src/components/LedgerAccountEntries.tsx','utf8');
assert.match(api,/fetchLedgerAccountKeyset/);
assert.match(api,/parseLedgerKeysetPage\(raw,tenantId,accountId,pageSize\)/);
assert.match(ui,/isSessionSnapshotCurrent\(snapshot\)/);
assert.match(ui,/result\.key===key/);
assert.match(ui,/nextJournalNavigation/);
assert.match(ui,/previousJournalNavigation/);
assert.match(ui,/disabled=\{nav\.page<=1\}/);
assert.match(ui,/disabled=\{!current\.data\.has_more\|\|nav\.page>=1000\}/);
assert.match(ui,/Não comprova completude do Livro-Razão/);
console.log('FR_CAIXINHA_M360_KEYSET_FRONTEND=PASS');
