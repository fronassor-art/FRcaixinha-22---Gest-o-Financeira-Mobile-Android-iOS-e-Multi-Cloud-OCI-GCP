/* FRcaixinha AI Studio — M220: fronteiras contábeis sintéticas. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseLedgerAccounts,parseLedgerTransactions,validateLedgerAccountLinks} from '../services/ledgerDetailBoundary';
const A='00000000-0000-4000-8000-000000000001',B='00000000-0000-4000-8000-000000000002';
const AC='00000000-0000-4000-8000-000000000010',BC='00000000-0000-4000-8000-000000000011';
const X='00000000-0000-4000-8000-000000000021',ED='00000000-0000-4000-8000-000000000031';
const EC='00000000-0000-4000-8000-000000000032';
const account={id:AC,tenant_id:A,account_code:'1.1.1',account_name:'Caixa',account_type:'ASSET',
 balance_cents:5000,balance_brl:'50.00'};
const counterpart={...account,id:BC,account_code:'1.2.1',account_name:'Crédito',balance_cents:0,balance_brl:'0.00'};
const tx={id:X,tenant_id:A,description:'Lançamento sintético',transaction_date:'2027-01-10T12:00:00+00:00',
 reference_id:'CI:only',entries:[
 {id:ED,account_id:AC,account_name:'Caixa',entry_type:'DR',amount_cents:500,amount_brl:'5.00'},
 {id:EC,account_id:BC,account_name:'Crédito',entry_type:'CR',amount_cents:500,amount_brl:'5.00'}]};
let checks=0;
const ok=(f:()=>void)=>{f();checks++};
const reject=(f:()=>unknown)=>ok(()=>assert.throws(f));
const accounts=parseLedgerAccounts([account,counterpart],A);
const transactions=parseLedgerTransactions([tx],A);
ok(()=>assert.equal(accounts.length,2));
ok(()=>assert.equal(transactions[0].entries.length,2));
ok(()=>validateLedgerAccountLinks(accounts,transactions));
reject(()=>parseLedgerAccounts([{...account,tenant_id:B}],A));
reject(()=>parseLedgerAccounts([{...account,cpf:'private'}],A));
reject(()=>parseLedgerAccounts([{...account,balance_cents:5001}],A));
reject(()=>parseLedgerAccounts([{...account,balance_cents:Infinity}],A));
reject(()=>parseLedgerAccounts([{...account,balance_cents:1.1}],A));
reject(()=>parseLedgerAccounts([{...account,balance_brl:'NaN'}],A));
reject(()=>parseLedgerAccounts([account,account],A));
reject(()=>parseLedgerAccounts([account,{...account,id:BC}],A));
reject(()=>parseLedgerAccounts(Array(501).fill(account),A));
reject(()=>parseLedgerTransactions([{...tx,tenant_id:B}],A));
reject(()=>parseLedgerTransactions([{...tx,pix_key:'hidden'}],A));
reject(()=>parseLedgerTransactions([{...tx,entries:[]}],A));
reject(()=>parseLedgerTransactions([{...tx,entries:[tx.entries[0]]}],A));
reject(()=>parseLedgerTransactions([{...tx,entries:[tx.entries[0],tx.entries[0]]}],A));
reject(()=>parseLedgerTransactions([{...tx,entries:[tx.entries[0],{...tx.entries[1],amount_cents:501}]}],A));
reject(()=>parseLedgerTransactions([{...tx,entries:[tx.entries[0],{...tx.entries[1],entry_type:'DR'}]}],A));
reject(()=>parseLedgerTransactions([{...tx,entries:[tx.entries[0],{...tx.entries[1],amount_cents:0,amount_brl:'0.00'}]}],A));
reject(()=>parseLedgerTransactions([{...tx,entries:[tx.entries[0],{...tx.entries[1],token:'private'}]}],A));
reject(()=>parseLedgerTransactions([{...tx,transaction_date:'2027-99-99T15:30:00Z'}],A));
reject(()=>parseLedgerTransactions([{...tx,transaction_date:'2027-02-30T15:30:00Z'}],A));
reject(()=>parseLedgerTransactions([{...tx,reference_id:null}],A));
reject(()=>parseLedgerTransactions([tx,tx],A));
reject(()=>parseLedgerTransactions(Array(501).fill(tx),A));
reject(()=>validateLedgerAccountLinks(accounts,parseLedgerTransactions([{...tx,entries:[
 {...tx.entries[0],account_id:B},tx.entries[1]]}],A)));
reject(()=>validateLedgerAccountLinks(accounts,parseLedgerTransactions([{...tx,entries:[
 {...tx.entries[0],account_name:'Forjada'},tx.entries[1]]}],A)));
const api=readFileSync('src/services/financialApiService.ts','utf8');
const view=readFileSync('src/components/LedgerView.tsx','utf8');
assert.match(api,/parseLedgerAccounts\(raw,tenantId\)/);
assert.match(api,/parseLedgerTransactions\(raw,tenantId\)/);
assert.match(view,/validateLedgerAccountLinks\(accounts,transactions\)/);
assert.match(view,/authService\.isSessionSnapshotCurrent\(snapshot\)/);
console.log('MACROPACOTE_220_LEDGER_BOUNDARY_CI=PASS',checks);
