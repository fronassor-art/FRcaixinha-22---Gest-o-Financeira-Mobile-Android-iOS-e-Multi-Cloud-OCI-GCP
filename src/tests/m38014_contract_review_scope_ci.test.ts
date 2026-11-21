/** M38014-M38029 — contract text must not appear across login contexts. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {contractReviewScopeKey,createContractReviewSequence}
  from '../services/contractReviewBoundary';
import type {AuthenticatedUser} from '../services/authService';

const t1='00000000-0000-4000-8000-0000000000a1';
const t2='00000000-0000-4000-8000-0000000000b2';
const u1='00000000-0000-4000-8000-0000000000c3';
const u2='00000000-0000-4000-8000-0000000000d4';
const admin:AuthenticatedUser={id:u1,name:'Administrador sintético',email:'a@example.invalid',role:'TENANT_ADMIN',tenantId:t1};
const master:AuthenticatedUser={id:u1,name:'Master sintético',email:'m@example.invalid',role:'MASTER'};
const member:AuthenticatedUser={...admin,role:'TENANT_MEMBER'};
const valid=contractReviewScopeKey('TENANT_ADMIN',t1,admin,2);
assert.equal(typeof valid,'string');
assert.equal(contractReviewScopeKey('TENANT_ADMIN',t1.toUpperCase(),admin,2),valid);
assert.notEqual(contractReviewScopeKey('TENANT_ADMIN',t1,{...admin,id:u2},2),valid);
assert.notEqual(contractReviewScopeKey('TENANT_ADMIN',t1,admin,3),valid);
assert.equal(contractReviewScopeKey('TENANT_ADMIN',t2,admin,2),null);
assert.equal(contractReviewScopeKey('TENANT_ADMIN',t1,member,2),null);
assert.equal(contractReviewScopeKey('TENANT_ADMIN',t1,master,2),null);
assert.equal(contractReviewScopeKey('MASTER',t1,admin,2),null);
assert.equal(contractReviewScopeKey('MASTER',t1,master,2)!==null,true);
assert.notEqual(contractReviewScopeKey('MASTER',t1,master,2),contractReviewScopeKey('MASTER',t2,master,2));
assert.equal(contractReviewScopeKey('MASTER',t1,{...master,tenantId:t1},2),null);
for(const invalid of [null,undefined,0,NaN,1.5,-1] as unknown[]){
 assert.equal(contractReviewScopeKey('MASTER',t1,master,invalid as number),null);
}
for(const invalid of ['', 'not-a-uuid','00000000-0000-0000-0000-000000000000']){
 assert.equal(contractReviewScopeKey('TENANT_ADMIN',invalid,admin,2),null);
}
assert.equal(contractReviewScopeKey('MASTER',t1,{...master,id:'not-uuid'},2),null);
assert.equal(contractReviewScopeKey('MASTER',t1,null,2),null);
assert.equal(contractReviewScopeKey('TENANT_MEMBER' as any,t1,member,2),null);

const fence=createContractReviewSequence();
const one=fence.next(),two=fence.next();
assert(!fence.isCurrent(one));
assert(fence.isCurrent(two));
fence.invalidate();
assert(!fence.isCurrent(two));
assert(fence.isCurrent(fence.next()));
assert(!fence.isCurrent(NaN));

const ui=readFileSync('src/components/ContractReviewPanel.tsx','utf8');
for(const term of [
 'authService.subscribe(reset)','authService.isSessionSnapshotCurrent(snapshot)',
 'scopeRef.current===expected', 'sequence.current !== request',
 'dataScope===scope', 'visibleCatalog', 'visibleBody',
 'visibleResult', 'visibleCanonical', 'visibleError',
 'setCatalog(null);setDocumentId', 'setDataScope(null)',
]){
 assert(ui.includes(term),'missing contract UI guard: '+term);
}
assert(!/localStorage|sessionStorage|createInvitation|recordAcceptance|register\(/.test(ui));
console.log('M38014 contract preflight recipient and session isolation PASS');
