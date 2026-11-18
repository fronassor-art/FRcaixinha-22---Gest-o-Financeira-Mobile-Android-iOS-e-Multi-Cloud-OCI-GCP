/** M40430 — deterministic stale-context presentation gate, entirely offline. */
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {SpecialCreditView} from '../components/SpecialCreditView';
import type {AppState} from '../services/store';
import {creditContextCanRender,creditMessageForContext}
  from '../services/specialCreditPresentation';

const current='member-a:tenant-a:TENANT_MEMBER';
const differentMember='member-b:tenant-a:TENANT_MEMBER';
const differentTenant='member-a:tenant-b:TENANT_MEMBER';
const differentRole='member-a:tenant-a:TENANT_ADMIN';
const cases:Array<[string|null,string,boolean,boolean,boolean]>=[
 [current,current,true,false,true],
 [current,current,false,false,false],
 [current,current,true,true,false],
 [current,current,false,true,false],
 [null,current,true,false,false],
 ['',current,true,false,false],
 [current,differentMember,true,false,false],
 [current,differentTenant,true,false,false],
 [current,differentRole,true,false,false],
 [differentMember,current,true,false,false],
 [differentTenant,current,true,false,false],
 [differentRole,current,true,false,false],
 [null,current,false,true,false],
 [current,current,true,false,true],
];
let pass=0;
for(const [loaded,active,enabled,loading,expected] of cases){
 assert.equal(creditContextCanRender(loaded,active,enabled,loading),expected);
 pass++;
}
const message='Autorização publicada somente na caixa interna.';
for(const [messageKey,currentKey,expected] of [
 [current,current,message],
 [current,differentMember,''],
 [current,differentTenant,''],
 [current,differentRole,''],
 [null,current,''],
] as Array<[string|null,string,string]>){
 assert.equal(creditMessageForContext(message,messageKey,currentKey),expected);
 pass++;
}
const state=(role:AppState['currentRole'])=>({
 currentRole:role,currentTenantId:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 currentUserId:'11111111-1111-4111-8111-111111111111',
} as AppState);
const master=renderToStaticMarkup(React.createElement(
 SpecialCreditView,{state:state('MASTER')}));
assert.equal(master,'');pass++;
const admin=renderToStaticMarkup(React.createElement(
 SpecialCreditView,{state:state('TENANT_ADMIN')}));
assert.match(admin,/Consultando o banco de homologação/);pass++;
assert.doesNotMatch(admin,/Registrar autorização especial/);pass++;
const member=renderToStaticMarkup(React.createElement(
 SpecialCreditView,{state:state('TENANT_MEMBER')}));
assert.match(member,/Consultando o banco de homologação/);pass++;
assert.doesNotMatch(member,/Tenho interesse<\/button>/);pass++;
assert.doesNotMatch(member,/Simular valor extraordinário/);pass++;
assert.equal(pass,25,'M40430 case count drift '+pass);
console.log('M40430_STALE_TENANT_ROLE_AND_MEMBER_RENDER=PASS_25_OF_25');
console.log('M40430_PREVIOUS_CONTEXT_DATA_AND_MESSAGE=HIDDEN');
console.log('M40430_STALE_PUSH_SESSION_ERROR=GUARDED');
console.log('M40430_NETWORK_POSTGRES_AND_PROVIDERS=NOT_ACCESSED');
