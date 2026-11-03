/* Concorrência e resposta Master sem seleção explícita: sempre falhar fechado. */
import assert from 'node:assert/strict';
import {authService} from '../services/authService';

const oldFetch=globalThis.fetch, oldWindow=(globalThis as any).window;
const oldEvent=(globalThis as any).CustomEvent;
(globalThis as any).window={
  setTimeout:()=>1, clearTimeout:()=>undefined, dispatchEvent:()=>true
};
(globalThis as any).CustomEvent=class{constructor(public type:string){}};
const reply=(d:unknown,status=200)=>new Response(JSON.stringify(d),{
  status,headers:{'content-type':'application/json'}
});
const owner={id:'ci-owner',name:'Owner CI',email:'ci@example.invalid',
  role:'MASTER',tenant_id:null};
let count=0;
let role:'MASTER'|'TENANT_ADMIN'='MASTER';
let allowed=true, held=false;
let resolveLogin:(response:Response)=>void=()=>undefined;
const revoked:string[]=[];
globalThis.fetch=(async(path:any,options?:RequestInit)=>{
  const url=String(path);
  if(url.endsWith('/login')){
    count++;
    if(held)return new Promise<Response>(done=>{resolveLogin=done;});
    return reply({token:'ci-token-'+count,user:{...owner,role},
      expires_at:new Date(Date.now()+900000).toISOString()});
  }
  if(url.endsWith('/owner-access'))return allowed
    ?reply({verified:true,role:'MASTER',scope:'PLATFORM_GOVERNANCE_ONLY'})
    :reply({detail:'denied'},403);
  if(url.endsWith('/logout')){
    revoked.push(String((options?.headers as Record<string,string>)?.Authorization));
    return reply({success:true});
  }
  throw Error('Unexpected request '+url);
}) as typeof fetch;
async function main(){
  const login=()=>authService.login(owner.email,'ci-only','MASTER');
  try{
    await assert.rejects(authService.login(owner.email,'ci-only'),
      /perfil de acesso solicitado/);
    assert.equal(authService.getToken(),null);
    assert.equal(revoked.length,1);
    role='TENANT_ADMIN';
    await assert.rejects(login(),/perfil de acesso solicitado/);
    assert.equal(revoked.length,2);
    role='MASTER';
    allowed=false;
    await assert.rejects(login(),/não confirmado pelo servidor/);
    assert.equal(revoked.length,3);
    allowed=true;
    held=true;
    const first=login();
    await assert.rejects(login(),/tentativa de login está em andamento/);
    assert.equal(count,4);
    await authService.logout();
    held=false;
    resolveLogin(reply({token:'stale-ci-token',user:owner,
      expires_at:new Date(Date.now()+900000).toISOString()}));
    await assert.rejects(first,/login cancelada/);
    assert.equal(authService.getToken(),null);
    assert(revoked.includes('Bearer stale-ci-token'));
    assert.equal((await login()).role,'MASTER');
    await authService.logout();
    assert.equal(authService.getToken(),null);
    console.log('MASTER_LOGIN_HARDENING_CI=PASS');
  }finally{
    await authService.logout();
    globalThis.fetch=oldFetch;
    (globalThis as any).window=oldWindow;
    (globalThis as any).CustomEvent=oldEvent;
  }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
