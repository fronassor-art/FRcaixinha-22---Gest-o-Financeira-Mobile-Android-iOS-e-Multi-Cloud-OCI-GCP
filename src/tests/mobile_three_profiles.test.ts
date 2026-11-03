/* Tres perfis no cliente que o APK usa; dados exclusivamente sinteticos. */
import assert from 'node:assert/strict';
import {authService} from '../services/authService';
const tenant='eab1fdf4-3f75-435d-99c0-e1c1b2c11452';
const profiles=[
  {email:'master-ci@example.invalid',role:'MASTER',id:'master-ci',name:'Master CI',tenant_id:null},
  {email:'admin-ci@example.invalid',role:'TENANT_ADMIN',id:'admin-ci',name:'Admin CI',tenant_id:tenant},
  {email:'member-ci@example.invalid',role:'TENANT_MEMBER',id:'member-ci',name:'Membro CI',tenant_id:tenant},
] as const;
(globalThis as any).window={setTimeout:()=>1,clearTimeout:()=>{},dispatchEvent:()=>true};
(globalThis as any).CustomEvent=class {constructor(public readonly name:string){}};
const savedFetch=globalThis.fetch;
let current:typeof profiles[number]|undefined, signed=false;
const response=(data:unknown,status=200)=>new Response(JSON.stringify(data),{
  status,headers:{'content-type':'application/json'}});
globalThis.fetch=(async(path:RequestInfo|URL,options?:RequestInit)=>{
  const route=String(path);
  if(route.endsWith('/login')){
    const payload=JSON.parse(String(options?.body));
    const found=profiles.find(p=>p.email===payload.usernameOrEmail);
    if(!found||payload.password!=='synthetic-CI-pass-123'||payload.requestedRole!==found.role)
      return response({detail:'Credenciais inválidas'},401);
    current=found;signed=true;
    return response({user:found,token:'CI-ONLY-RAM-TOKEN',
      expires_at:new Date(Date.now()+900000).toISOString()});
  }
  if(route.endsWith('/owner-access')) return signed&&current?.role==='MASTER'
    ? response({verified:true,role:'MASTER',scope:'PLATFORM_GOVERNANCE_ONLY'})
    : response({detail:'Negado'},403);
  if(route.endsWith('/me'))
    return signed&&current?response(current):response({detail:'Sem sessao'},401);
  if(route.endsWith('/contexts'))
    return signed&&current?response([{role:current.role,
      tenant_id:current.tenant_id,
      tenant_name:current.role==='MASTER'?null:'Caixinha CI'}]):response({},401);
  if(route.endsWith('/logout')){signed=false;return response({success:true});}
  throw new Error('Rota inesperada: '+route);
}) as typeof fetch;
try{
  for(const person of profiles){
    assert.equal(authService.getUser(),null);
    await assert.rejects(authService.login(person.email,'invalida'),/Credenciais inválidas/);
    assert.equal(authService.isAuthenticated(),false);
    const user=await authService.login(person.email,'synthetic-CI-pass-123',person.role);
    assert.equal(user.role,person.role);
    assert.equal(user.id,person.id);
    assert.equal((await authService.checkCurrentUser())?.role,person.role);
    assert.equal((await authService.listContexts())[0]?.role,person.role);
    await authService.logout();
    assert.equal(authService.getUser(),null);
    assert.equal(authService.getToken(),null);
  }
  console.log('PASS: cliente Master Admin Membro login logout');
} finally {await authService.logout();globalThis.fetch=savedFetch;}
