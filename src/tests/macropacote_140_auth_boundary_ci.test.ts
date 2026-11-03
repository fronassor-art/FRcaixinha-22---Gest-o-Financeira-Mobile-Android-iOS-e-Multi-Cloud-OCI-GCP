/* Macropacote 140 — segurança de identidades/contexts com dados sintéticos. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {parseServerContexts,contextLabel,authService} from '../services/authService';
import {parseServerSessionInventory} from '../services/sessionInventory';
import {sessionRoleLabel,sessionTenantLabel} from '../services/sessionPresentation';
import {SessionSecurityPanel} from '../components/SessionSecurityPanel';

const T='8baf3294-c65b-499f-b286-4566e76922a1';
const U='cf185bde-7f6c-41da-b6d3-cc82745d0a26';
const SID='51622eb2-45da-4dc9-b36f-c9ec7fdad9f0';
const current={role:'TENANT_ADMIN',tenant_id:T,tenant_name:'Caixinha A'};
const now=Date.now();
const session={id:SID,role:'TENANT_ADMIN',tenant_id:T,current:true,
  created_at:new Date(now-60000).toISOString(),
  expires_at:new Date(now+500000).toISOString()};
const inv=(rows:unknown[])=>({source:'POSTGRESQL_AUTH',sessions:rows});
const expected={role:'TENANT_ADMIN' as const,tenantId:T};
const expectCtxRejected=(v:unknown)=>assert.throws(()=>parseServerContexts(v));
const expectSessionRejected=(v:unknown)=>assert.throws(()=>parseServerSessionInventory(v,expected));
let checks=0;const check=(test:()=>void)=>{test();checks++};

// 20 negative and positive invariants; no real account or bank is contacted.
check(()=>assert.equal(parseServerContexts([current]).length,1));
check(()=>assert.equal(contextLabel(current as any),'Administrador — Caixinha A'));
check(()=>assert.equal(parseServerContexts([{role:'MASTER',tenant_id:null,tenant_name:null}])[0].role,'MASTER'));
check(()=>expectCtxRejected([{...current,email:'private@example.invalid'}]));
check(()=>expectCtxRejected([{...current,token:'never'}]));
check(()=>expectCtxRejected([{...current,role:7}]));
check(()=>expectCtxRejected([{...current,tenant_id:null}]));
check(()=>expectCtxRejected([{role:'MASTER',tenant_id:T}]));
check(()=>expectCtxRejected([{role:'MASTER',tenant_id:null,tenant_name:'Caixinha A'}]));
check(()=>expectCtxRejected([current,{...current,tenant_id:T.toUpperCase()}]));
check(()=>expectCtxRejected([current,current]));
check(()=>expectCtxRejected({contexts:[current]}));
check(()=>assert.equal(parseServerSessionInventory(inv([session]),expected).length,1));
check(()=>expectSessionRejected(inv([{...session,ip:'192.0.2.1'}])));
check(()=>expectSessionRejected(inv([{...session,extra:'another field'}])));
check(()=>expectSessionRejected(inv([{...session,current:false}])));
check(()=>expectSessionRejected(inv([session,session])));
check(()=>expectSessionRejected(inv([{...session,role:'MASTER'}])));
check(()=>assert.equal(sessionRoleLabel('TENANT_ADMIN'),'Administrador da caixinha'));
check(()=>assert.equal(sessionTenantLabel(T),'Caixinha '+T.slice(0,8).toUpperCase()));
assert.equal(sessionTenantLabel('not-a-uuid'),'Caixinha não identificada');
assert.equal(checks,20);
const ui=renderToStaticMarkup(React.createElement(SessionSecurityPanel,{onClose:()=>undefined}));
assert.match(ui,/Sessões da minha conta/);
const uiCode=readFileSync('src/components/SessionSecurityPanel.tsx','utf8');
assert.match(uiCode,/sessionRoleLabel\(item\.role\)/);
assert.match(uiCode,/sessionTenantLabel\(item\.tenant_id\)/);
assert.match(uiCode,/isSessionSnapshotCurrent\(snapshot\)/);
assert.match(readFileSync('src/services/authService.ts','utf8'),/Saia da conta e entre novamente/);
assert.match(readFileSync('backend/app/routers/auth.py','utf8'),/Troca de perfil bloqueada/);

// Resposta de vínculo estranho do servidor não altera o perfil atual.
const oldFetch=globalThis.fetch;
const oldWindow=(globalThis as any).window;
const oldCustom=(globalThis as any).CustomEvent;
(globalThis as any).window={setTimeout:()=>1,clearTimeout:()=>undefined,dispatchEvent:()=>true};
(globalThis as any).CustomEvent=class{constructor(public type:string){}};
let responseMode:'ok'|'extra'|'different'|'unauthorized'='ok';
const reply=(data:unknown,status=200):Response=>new Response(JSON.stringify(data),{status});
globalThis.fetch=(async(url:any)=>{
 const path=String(url);
 if(path.endsWith('/login'))return reply({
   token:'ci-synthetic-only',user:{id:U,name:'CI',email:'ci@example.invalid',
    role:'TENANT_ADMIN',tenant_id:T},expires_at:new Date(Date.now()+900000).toISOString()
 });
 if(path.endsWith('/logout'))return reply({success:true});
 if(path.endsWith('/contexts')){
   if(responseMode==='unauthorized')return reply({detail:'revoked'},401);
   if(responseMode==='different')return reply([{role:'TENANT_MEMBER',tenant_id:T,tenant_name:'Caixinha A'}]);
   if(responseMode==='extra')return reply([current,{role:'TENANT_MEMBER',tenant_id:T,tenant_name:'Caixinha A'}]);
   return reply([current]);
 }
 throw Error('Unexpected mock route '+path);
}) as typeof fetch;
async function integration(){
 try{
  await authService.login('ci@example.invalid','only-ci','TENANT_ADMIN');
  assert.equal((await authService.listContexts()).length,1);
  responseMode='extra';
  await assert.rejects(authService.listContexts(),/exclusivamente/);
  assert.equal(authService.getUser()?.role,'TENANT_ADMIN');
  responseMode='different';
  await assert.rejects(authService.listContexts(),/exclusivamente/);
  assert.equal(authService.getUser()?.role,'TENANT_ADMIN');
  responseMode='unauthorized';
  assert.deepEqual(await authService.listContexts(),[]);
  assert.equal(authService.getToken(),null);
  console.log('MACROPACOTE_140_CONTEXTO_SESSOES_FRONTEND=PASS');
 }finally{
  await authService.logout();
  globalThis.fetch=oldFetch;
  (globalThis as any).window=oldWindow;
  (globalThis as any).CustomEvent=oldCustom;
 }
}
integration().catch(err=>{console.error(err);process.exitCode=1;});
