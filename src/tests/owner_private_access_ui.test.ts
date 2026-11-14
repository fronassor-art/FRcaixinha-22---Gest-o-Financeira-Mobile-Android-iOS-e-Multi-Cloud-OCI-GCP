/* Acesso reservado: Master oculto publicamente e confirmado pelo servidor. */
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { readFileSync } from 'node:fs';
import { LoginView } from '../components/LoginView';
import { authService } from '../services/authService';
const html = renderToStaticMarkup(React.createElement(LoginView,{onLoginSuccess:()=>undefined}));
assert.match(html,/Administrador/);
assert.match(html,/Membro/);
assert.doesNotMatch(html,/Administrador Master|Dono da plataforma/);
const code=readFileSync('src/components/LoginView.tsx','utf8');
assert.match(code,/openReservedAccess/);
assert.match(code,/count !== 7/);
assert.doesNotMatch(code,/role:'MASTER' as const, title:/);
const oldFetch=globalThis.fetch,oldWindow=(globalThis as any).window;
const oldEvent=(globalThis as any).CustomEvent;
(globalThis as any).window={setTimeout:()=>1,clearTimeout:()=>{},dispatchEvent:()=>true};
(globalThis as any).CustomEvent=class {constructor(public readonly type:string){}};
const owner={id:'owner-ci',name:'Proprietario CI',email:'owner@example.invalid',role:'MASTER',tenant_id:null};
let allowed=true;
const calls:string[]=[];
const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{
  status,headers:{'content-type':'application/json'}});
globalThis.fetch=(async(url:RequestInfo|URL,opts?:RequestInit)=>{
  const path=String(url);
  calls.push(path);
  if(path.endsWith('/login')){
    const data=JSON.parse(String(opts?.body));
    assert.equal(data.requestedRole,'MASTER');
    return response({token:'ci-owner-test-only',
      expires_at:new Date(Date.now()+900000).toISOString(),user:owner});
  }
  if(path.endsWith('/owner-access')){
    assert.match(String((opts?.headers as Record<string,string>)?.Authorization),/^Bearer /);
    return allowed
      ? response({verified:true,role:'MASTER',scope:'PLATFORM_GOVERNANCE_ONLY'})
      : response({detail:'Acesso negado'},403);
  }
  if(path.endsWith('/logout'))return response({success:true});
  throw new Error('Rota inesperada: '+path);
}) as typeof fetch;
try{
  const user=await authService.login(owner.email,'senha-ci','MASTER');
  assert.equal(user.role,'MASTER');
  assert.equal(authService.getUser()?.role,'MASTER');
  await authService.logout();
  allowed=false;
  await assert.rejects(authService.login(owner.email,'senha-ci','MASTER'),
    /não confirmado pelo servidor/);
  assert.equal(authService.getUser(),null);
  assert.equal(authService.getToken(),null);
  assert.equal(calls.filter(c=>c.endsWith('/owner-access')).length,2);
  assert.equal(calls.filter(c=>c.endsWith('/logout')).length,2);
  console.log('OWNER_PRIVATE_ACCESS_UI=PASS');
}finally{
  await authService.logout();
  globalThis.fetch=oldFetch;
  (globalThis as any).window=oldWindow;
  (globalThis as any).CustomEvent=oldEvent;
}
