/* Uma unica identidade, tres contextos no cliente (mesma logica do APK).
   Dados sinteticos: sem senhas de usuarios reais nem requests externos. */
import assert from 'node:assert/strict';
import { authService, contextLabel, parseServerContexts } from '../services/authService';

const id='f6c38125-483d-4acc-bfe9-21dc400ef7a2';
const tenant='f2df18c9-0345-46e8-9da1-c5d07c6d5a4c';
const other='ef3c4a72-74cd-4b53-9780-407d8b7dc799';
const owner='master-owner-ci@example.com';
const name='Proprietario CI';
const contexts=[
  {role:'MASTER',tenant_id:null,tenant_name:null},
  {role:'TENANT_ADMIN',tenant_id:tenant,tenant_name:'Caixinha inaugural CI'},
  {role:'TENANT_MEMBER',tenant_id:tenant,tenant_name:'Caixinha inaugural CI'},
] as const;
let active:'MASTER'|'TENANT_ADMIN'|'TENANT_MEMBER'='MASTER';
let activeTenant:string|null=null;
let tokenActive=false;
const paths:string[]=[];
const originalFetch=globalThis.fetch;
const originalWindow=(globalThis as any).window;
const originalEvent=(globalThis as any).CustomEvent;
(globalThis as any).window={
  setTimeout:()=>1,clearTimeout:()=>undefined,dispatchEvent:()=>true,
};
(globalThis as any).CustomEvent=class {constructor(public readonly type:string){}};
const result=(data:unknown,status=200):Response=>new Response(JSON.stringify(data),{
  status,headers:{'content-type':'application/json'},
});
function user(){
  return {id,name,email:owner,is_master:true,role:active,tenant_id:activeTenant};
}
globalThis.fetch=(async(path:RequestInfo|URL,options?:RequestInit)=>{
  const url=String(path);
  paths.push(url);
  if(url.endsWith('/login')){
    const request=JSON.parse(String(options?.body));
    if(request.usernameOrEmail!==owner||request.password!=='test-only-private-ci')
      return result({detail:'Nao autorizado'},401);
    active='MASTER';activeTenant=null;tokenActive=true;
    return result({
      token:'ci-temporary-token-no-real-user',
      expires_at:new Date(Date.now()+900000).toISOString(),user:user(),
    });
  }
  if(url.endsWith('/logout')){tokenActive=false;return result({success:true});}
  if(!tokenActive)return result({detail:'Sem sessao'},401);
  if(url.endsWith('/me'))return result(user());
  if(url.endsWith('/contexts'))return result(contexts);
  if(url.endsWith('/switch-context')){
    if(!options?.headers||
       !JSON.stringify(options.headers).includes('Bearer ci-temporary-token-no-real-user'))
      return result({detail:'Token ausente'},401);
    const body=JSON.parse(String(options.body));
    if(!contexts.some(c=>c.role===body.target_role &&
        c.tenant_id===body.target_tenant_id))return result({detail:'Sem vinculo'},403);
    active=body.target_role;activeTenant=body.target_tenant_id;
    return result(user());
  }
  throw Error('Rota nao esperada: '+url);
}) as typeof fetch;
try{
  assert.deepEqual(parseServerContexts(contexts).map(c=>c.role),
    ['MASTER','TENANT_ADMIN','TENANT_MEMBER']);
  assert.match(contextLabel(contexts[1]),/Administrador/);
  assert.match(contextLabel(contexts[2]),/Membro/);
  const signed=await authService.login(owner,'test-only-private-ci');
  assert.equal(signed.id,id);
  assert.equal(signed.role,'MASTER');
  assert.equal((await authService.listContexts()).length,3);
  for(const role of ['TENANT_ADMIN','TENANT_MEMBER','MASTER'] as const){
    const context=contexts.find(c=>c.role===role)!;
    const switched=await authService.switchContext(context);
    assert.equal(switched.id,id);
    assert.equal(switched.email,owner);
    assert.equal(switched.role,role);
    assert.equal(switched.tenantId??null,context.tenant_id);
    assert.equal((await authService.checkCurrentUser())?.role,role);
    assert.equal((await authService.listContexts()).length,3);
    if(role==='TENANT_MEMBER'){
      await assert.rejects(
        authService.switchContext({
          role:'TENANT_ADMIN',tenant_id:other,
          tenant_name:'Caixinha sem vinculo',
        }),/não autorizado|indisponível/i);
      assert.equal(authService.getUser()?.role,'TENANT_MEMBER');
    }
  }
  assert.equal(paths.filter(p=>p.endsWith('/login')).length,1,
    'Tres papeis nao devem criar tres logins');
  await authService.logout();
  assert.equal(authService.getUser(),null);
  assert.equal(authService.getToken(),null);
  console.log('PASS: mesma identidade Master/Admin/Membro, selecao, negacao e logout');
} finally {
  await authService.logout();
  globalThis.fetch=originalFetch;
  (globalThis as any).window=originalWindow;
  (globalThis as any).CustomEvent=originalEvent;
}
