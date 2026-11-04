/** M2200: regressão offline de paginação dos extratos; NÃO homologa o aparelho. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
 initialJournalNavigation,previousJournalNavigation,
 nextJournalNavigation,canAdvanceJournalNavigation,
} from '../services/ledgerJournalCursorNavigation';
const noMore={has_more:false,next_cursor:null};

let state=initialJournalNavigation();
for(let i=1;i<1000;i++){
 const cursor='c'+i.toString(36);
 assert.equal(canAdvanceJournalNavigation(state,{has_more:true,next_cursor:cursor}),true);
 const old=state;
 state=nextJournalNavigation(state,{has_more:true,next_cursor:cursor});
 assert.equal(state.page,i+1);
 assert.equal(state.cursors.length,i+1);
 assert.notEqual(state,old);
 assert.equal(canAdvanceJournalNavigation(state,{has_more:true,next_cursor:cursor}),false);
 assert.equal(nextJournalNavigation(state,noMore),state);
}
assert.equal(state.page,1000);
assert.equal(canAdvanceJournalNavigation(state,{has_more:true,next_cursor:'c1000'}),false);
assert.equal(nextJournalNavigation(state,{has_more:true,next_cursor:'c1000'}),state);
for(let i=1000;i>1;i--){
 state=previousJournalNavigation(state);
 assert.equal(state.page,i-1);
}
assert.equal(state.page,1);
assert.equal(state.cursors[0],null);
assert.equal(previousJournalNavigation(state),state);
assert.equal(canAdvanceJournalNavigation(state,{has_more:true,next_cursor:'c1'}),true);
state=nextJournalNavigation(state,{has_more:true,next_cursor:'cREPLACED'});
assert.equal(state.page,2);
assert.equal(state.cursors[1],'cREPLACED');
assert.equal(canAdvanceJournalNavigation(state,{has_more:true,next_cursor:'cREPLACED'}),false);
assert.equal(canAdvanceJournalNavigation(state,{has_more:true,next_cursor:'..'}),false);
assert.equal(canAdvanceJournalNavigation(state,{has_more:true,next_cursor:'x'.repeat(401)}),false);
assert.equal(canAdvanceJournalNavigation(state,{has_more:true,next_cursor:'abcd='}),false);

const ui=readFileSync('src/components/LedgerAccountEntries.tsx','utf8');
const parent=readFileSync('src/components/LedgerView.tsx','utf8');
const api=readFileSync('src/services/financialApiService.ts','utf8');
assert.match(ui,/canAdvanceJournalNavigation\(nav,current\.data\)/);
assert.match(ui,/disabled=\{!canMoveNext\}/);
assert.match(ui,/cursor repetido ou inválido/);
assert.match(ui,/isSessionSnapshotCurrent\(snapshot\)/);
assert.match(ui,/Tentar novamente/);
assert.match(ui,/Não comprova completude do Livro-Razão/);
assert.match(parent,/Ver extrato da conta/);
assert.match(parent,/setSelectedAccountId\(null\)/);
assert.match(api,/this\.assertLedgerAdmin\(tenantId\)/);
assert.match(api,/parseLedgerKeysetPage\(raw,tenantId,accountId,pageSize\)/);
console.log('M2200_LEDGER_1000_PAGE_NAVIGATION=PASS');
