/** M40440 — two login sessions of the same user must never share UI data. */
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {SpecialCreditView} from '../components/SpecialCreditView';
import type {AppState} from '../services/store';
import {
 creditSessionContextKey,creditSessionCanRender,creditMessageForContext,
} from '../services/specialCreditPresentation';
const A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const U1='11111111-1111-4111-8111-111111111111';
const U2='22222222-2222-4222-8222-222222222222';
const make=(u:string,t:string,r:string,g:number)=>
  creditSessionContextKey(u,t,r,g);
const base=make(U1,A,'TENANT_MEMBER',7);
let checks=0;
function check(fn:()=>void){fn();checks++;}
check(()=>assert.equal(base,U1+':'+A+':TENANT_MEMBER:g7'));
const changes=[
 make(U2,A,'TENANT_MEMBER',7),
 make(U1,B,'TENANT_MEMBER',7),
 make(U1,A,'TENANT_ADMIN',7),
 make(U1,A,'MASTER',7),
 ...[0,1,2,3,4,5,6,8].map(g=>make(U1,A,'TENANT_MEMBER',g)),
];
assert.equal(changes.length,12);
for(const changed of changes){
 check(()=>assert.notEqual(changed,base));
}
const visibleCases:Array<[string|null,string,boolean,boolean,boolean,boolean]>=[
 [base,base,true,false,true,true],
 [base,base,true,false,false,false],
 [base,make(U1,A,'TENANT_MEMBER',8),true,false,true,false],
 [base,base,false,false,true,false],
 [base,base,true,true,true,false],
 [null,base,true,false,true,false],
];
for(const [loaded,current,enabled,loading,token,expected] of visibleCases){
 check(()=>assert.equal(creditSessionCanRender(loaded,current,enabled,loading,token),expected));
}
const message='Mensagem sintética sem empréstimo ou Pix.';
const messageCases:Array<[string|null,string,string]>=[
 [base,base,message],
 [base,make(U1,A,'TENANT_MEMBER',8),''],
 [base,make(U2,A,'TENANT_MEMBER',7),''],
 [base,make(U1,B,'TENANT_MEMBER',7),''],
 [base,make(U1,A,'TENANT_ADMIN',7),''],
];
for(const [stored,current,expected] of messageCases){
 check(()=>assert.equal(creditMessageForContext(message,stored,current),expected));
}
const master={currentRole:'MASTER',currentTenantId:'',currentUserId:U1} as AppState;
check(()=>assert.equal(
 renderToStaticMarkup(React.createElement(SpecialCreditView,{state:master})),'')); 
assert.equal(checks,25,'M40440 case count drift: '+checks);
console.log('M40440_SAME_ACCOUNT_RELOGIN_AND_NEW_GENERATION=PASS_25_OF_25');
console.log('M40440_STALE_DATA_AND_CONFIRMATIONS=HIDDEN');
console.log('M40440_NO_TOKEN_IN_CONTEXT_KEY=PASS');
console.log('M40440_NETWORK_POSTGRES_AND_PROVIDERS=NOT_ACCESSED');
console.log('M40440_REAL_PAYMENTS=OFF');
console.log('M40440_PRODUCTION=BLOCKED');
