/* Pacote 10: inventário com dados sintéticos e resiliência a troca de sessão. */
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {parseServerSessionInventory} from '../services/sessionInventory';
import {authService} from '../services/authService';
import {SessionSecurityPanel} from '../components/SessionSecurityPanel';

const A='00000000-0000-4000-8000-000000000001';
const B='00000000-0000-4000-8000-000000000002';
const S1='00000000-0000-4000-8000-000000000003';
const S2='00000000-0000-4000-8000-000000000004';
const U='00000000-0000-4000-8000-000000000005';
const now=Date.now();
const first={id:S1,role:'TENANT_ADMIN',tenant_id:A,
  created_at:new Date(now-60000).toISOString(),
  expires_at:new Date(now+600000).toISOString(),current:true};
const second={...first,id:S2,role:'TENANT_MEMBER',current:false};
const inventory=(sessions:unknown[])=>({source:'POSTGRESQL_AUTH',sessions});
const expected={role:'TENANT_ADMIN' as const,tenantId:A};
assert.equal(parseServerSessionInventory(inventory([first,second]),expected).length,2);
for(const invalid of [
 inventory([]),
 inventory([first,first]),
 inventory([first,{...first,id:S2,current:true}]),
 inventory([{...first,current:false},second]),
 inventory([{...first,role:'MASTER'}]),
 inventory([{...first,tenant_id:B}]),
 inventory([{...first,tenant_id:null}]),
 inventory([{...first,id:'not-uuid'}]),
 inventory([{...first,created_at:'2026-11-03'}]),
 inventory([{...first,created_at:'not-date'}]),
 inventory([{...first,created_at:new Date(now+700000).toISOString()}]),
 inventory([{...first,token_hash:'secret'}]),
 inventory([{...first,email:'private@example.invalid'}]),
 inventory([first,{...second,tenant_id:null}]),
 {source:'SEED',sessions:[first]},
])assert.throws(()=>parseServerSessionInventory(invalid,expected));
assert.throws(()=>parseServerSessionInventory(inventory([first]),
  {role:'TENANT_MEMBER',tenantId:A}));
assert.throws(()=>parseServerSessionInventory(inventory([first]),
  {role:'MASTER',tenantId:undefined}));
const view=renderToStaticMarkup(React.createElement(SessionSecurityPanel,{
  onClose:()=>undefined,
}));
assert.match(view,/Sessões da minha conta/);
assert.match(view,/Atualizar sessões/);
assert.match(view,/revogação remota/);

const oldFetch=globalThis.fetch;
const oldWindow=(globalThis as any).window;
const oldEvent=(globalThis as any).CustomEvent;
(globalThis as any).window={setTimeout:()=>1,clearTimeout:()=>undefined,
  dispatchEvent:()=>true};
(globalThis as any).CustomEvent=class{constructor(public type:string){}};
let body:unknown=inventory([first,second]);
let status=200,held=false;
let resolveList:(value:Response)=>void=()=>undefined;
const calls:string[]=[];
const reply=(data:unknown,code=200)=>new Response(JSON.stringify(data),{
 status:code,headers:{'content-type':'application/json'},
});
globalThis.fetch=(async(url:any,options?:RequestInit)=>{
 const path=String(url);calls.push(path);
 if(path.endsWith('/login'))return reply({
   token:'ci-session-'+calls.length,
   user:{id:U,name:'Pessoa CI',email:'ci@example.invalid',
     role:'TENANT_ADMIN',tenant_id:A},
   expires_at:new Date(Date.now()+900000).toISOString(),
 });
 if(path.endsWith('/logout'))return reply({success:true});
 if(path.endsWith('/sessions')){
   if(held)return new Promise<Response>(resolve=>{resolveList=resolve;});
   return reply(body,status);
 }
 if(path.endsWith('/revoke'))return reply({success:true,
   session_id:S2,current_revoked:false});
 throw Error('Rota inesperada '+path);
}) as typeof fetch;

async function main(){
 try{
   await authService.login('ci@example.invalid','synthetic-only','TENANT_ADMIN');
   assert.equal((await authService.listSessions()).length,2);
   body=inventory([{...first,tenant_id:B}]);
   await assert.rejects(authService.listSessions(),/Sessão atual não corresponde/);
   assert(authService.isAuthenticated());
   body=inventory([first,second]);
   await assert.rejects(authService.revokeSession('1'.repeat(36)),/ID de sessão inválido/);
   assert.equal(await authService.revokeSession(S2),false);
   status=503;
   await assert.rejects(authService.listSessions(),/indisponíveis/);
   assert(authService.isAuthenticated(),'503 não deve revogar sessão local');
   status=200;

   held=true;
   const pending=authService.listSessions();
   await authService.logout();
   await authService.login('ci@example.invalid','synthetic-only','TENANT_ADMIN');
   resolveList(reply(inventory([first,second])));
   assert.deepEqual(await pending,[],'Inventário antigo não chega a novo login');
   assert(authService.isAuthenticated());
   held=false;
   status=401;
   await assert.rejects(authService.listSessions(),/Sessão expirada/);
   assert.equal(authService.getToken(),null);
   console.log('PACOTE_10_SESSOES_INVENTARIO_CI=PASS');
 }finally{
   await authService.logout();
   globalThis.fetch=oldFetch;
   (globalThis as any).window=oldWindow;
   (globalThis as any).CustomEvent=oldEvent;
 }
}
main().catch(err=>{console.error(err);process.exitCode=1;});
