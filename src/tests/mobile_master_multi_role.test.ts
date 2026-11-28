/* Mesma identidade com tres papeis; cada papel EXIGE novo login apos logout.
   Somente dados e credenciais sinteticos de CI. */
import assert from 'node:assert/strict';
import { authService, contextLabel, parseServerContexts } from '../services/authService';

const id='f6c38125-483d-4acc-bfe9-21dc400ef7a2';
const tenant='f2df18c9-0345-46e8-9da1-c5d07c6d5a4c';
const otherTenant='eb816c04-929a-4465-a8a5-405e5fc1c1d6';
const owner='master-owner-ci@example.com';
const name='Proprietario CI';
const contexts=[
  {role:'MASTER',tenant_id:null,tenant_name:null},
  {role:'TENANT_ADMIN',tenant_id:tenant,tenant_name:'Caixinha inaugural CI'},
  {role:'TENANT_MEMBER',tenant_id:tenant,tenant_name:'Caixinha inaugural CI'},
] as const;
type Role=typeof contexts[number]['role'];
let active:Role='MASTER';
let activeTenant:string|null=null;
let tokenActive=false;
const paths:string[]=[];
const originalFetch=globalThis.fetch;
const originalWindow=(globalThis as any).window;
const originalEvent=(globalThis as any).CustomEvent;
(globalThis as any).window={setTimeout:()=>1,clearTimeout:()=>undefined,dispatchEvent:()=>true};
(globalThis as any).CustomEvent=class {constructor(public readonly type:string){}};
const result=(data:unknown,status=200):Response=>new Response(JSON.stringify(data),{
  status,headers:{'content-type':'application/json'},
});
const user=()=>({id,name,email:owner,is_master:true,role:active,tenant_id:activeTenant});
globalThis.fetch=(async(path:RequestInfo|URL,options?:RequestInit)=>{
  const url=String(path);
  paths.push(url);
  if(url.endsWith('/login')){
    const request=JSON.parse(String(options?.body));
    const choice=contexts.find(c=>c.role===request.requestedRole);
    if(request.usernameOrEmail!==owner||request.password!=='test-only-private-ci'||!choice)
      return result({detail:'Credenciais invalidas ou acesso indisponivel'},401);
    if(tokenActive)return result({detail:'Saia da conta'},409);
    if(request.requestedTenantId && request.requestedTenantId!==otherTenant)
      return result({detail:'Caixinha invalida'},401);
    active=choice.role;activeTenant=request.requestedTenantId??choice.tenant_id;tokenActive=true;
    return result({token:'ci-temporary-token-no-real-user',
      expires_at:new Date(Date.now()+900000).toISOString(),user:user()});
  }
  if(url.endsWith('/logout')){tokenActive=false;return result({success:true});}
  if(!tokenActive)return result({detail:'Sem sessao'},401);
  if(url.endsWith('/owner-access')) return active==='MASTER'
    ? result({verified:true,role:'MASTER',scope:'PLATFORM_GOVERNANCE_ONLY'})
    : result({detail:'Negado'},403);
  if(url.endsWith('/me'))return result(user());
  if(url.endsWith('/contexts'))return result([contexts.find(c=>c.role===active)]);
  if(url.endsWith('/switch-context'))return result({detail:'Troca bloqueada'},403);
  throw Error('Rota nao esperada: '+url);
}) as typeof fetch;
try {
  assert.deepEqual(parseServerContexts(contexts).map(c=>c.role),
    ['MASTER','TENANT_ADMIN','TENANT_MEMBER']);
  assert.match(contextLabel(contexts[1]),/Administrador/);
  assert.match(contextLabel(contexts[2]),/Membro/);
  for(const role of ['MASTER','TENANT_ADMIN','TENANT_MEMBER'] as const){
    assert.equal(authService.getUser(),null);
    const signed=await authService.login(owner,'test-only-private-ci',role);
    assert.equal(signed.id,id);
    assert.equal(signed.email,owner);
    assert.equal(signed.role,role);
    assert.equal(signed.tenantId??null,contexts.find(c=>c.role===role)!.tenant_id);
    assert.equal((await authService.checkCurrentUser())?.role,role);
    const visible=await authService.listContexts();
    assert.equal(visible.length,1);
    assert.equal(visible[0].role,role);
    await assert.rejects(authService.switchContext(contexts.find(c=>c.role!==role)!),/Saia da conta/);
    await assert.rejects(authService.login(owner,'test-only-private-ci',
      role==='MASTER'?'TENANT_ADMIN':'MASTER'),/Saia da conta/);
    assert.equal(authService.getUser()?.role,role);
    await authService.logout();
    assert.equal(authService.getUser(),null);
    assert.equal(authService.getToken(),null);
  }
  assert.equal(paths.filter(p=>p.endsWith('/login')).length,3,
    'Cada novo papel exige login novo com senha.');
  const chosen=await authService.login(owner,'test-only-private-ci','TENANT_MEMBER',otherTenant);
  assert.equal(chosen.tenantId,otherTenant);
  await authService.logout();
  assert.equal(paths.filter(p=>p.endsWith('/switch-context')).length,0,
    'Cliente nao pode chamar endpoint de troca dentro da sessao.');
  console.log('PASS: mesma identidade, 3 perfis isolados, novo login apos logout');
} finally {
  await authService.logout();
  globalThis.fetch=originalFetch;
  (globalThis as any).window=originalWindow;
  (globalThis as any).CustomEvent=originalEvent;
}
