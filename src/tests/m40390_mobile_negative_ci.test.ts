/** M40390: negative Android scenarios, fully offline mocks. No network or DB. */
import assert from 'node:assert/strict';
import {requestSpecialCredit,assertSandboxCreditCapabilities,type SpecialCreditTransport} from '../services/specialCreditRequestBoundary';
import {isRoleTabAllowed} from '../services/roleScope';
import type {AuthenticatedUser} from '../services/authService';
const A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const T='m40390-never-real-token';
const safe={sandbox_enabled:false,grants_allow_request_only:true,real_credit_enabled:false,pix_real_enabled:false,
 channels:Object.fromEntries(['PUSH','EMAIL','WHATSAPP','SMS'].map(c=>[c,{code_present:true,real_delivery_enabled:false}]))};
function harness(role:AuthenticatedUser['role']='TENANT_ADMIN',tenant:string|undefined=A){
 let current=true,token:string|null=T,invalidations=0,reply=Response.json(safe);
 let user:AuthenticatedUser|null={id:'11111111-1111-4111-8111-111111111111',name:'CI',email:'ci@example.invalid',role,tenantId:tenant};
 const sent:Array<{url:string;options:RequestInit}>=[];
 const transport:SpecialCreditTransport={
  origin:()=> 'http://127.0.0.1:8000',
  captureSession:()=>({token,generation:1}),isCurrent:()=>current,getUser:()=>user,
  invalidateIfCurrent:()=>{invalidations++;return true;},
  send:async(url,options)=>{sent.push({url,options});return reply.clone();},
 };
 return {transport,sent,setCurrent:(v:boolean)=>{current=v;},setToken:(v:string|null)=>{token=v;},
  setUser:(v:AuthenticatedUser|null)=>{user=v;},setReply:(r:Response)=>{reply=r;},invalidations:()=>invalidations};
}
let checks=0;
for(const role of ['TENANT_ADMIN','TENANT_MEMBER'] as const){
 const h=harness(role);
 await assert.rejects(requestSpecialCredit(h.transport,B,'/capabilities'),/caixinha não corresponde/);
 assert.equal(h.sent.length,0);checks++;
}
const master=harness('MASTER',undefined);
await assert.rejects(requestSpecialCredit(master.transport,A,'/capabilities'),/Acesso recusado/);
assert.equal(master.sent.length,0);checks++;
const noToken=harness();noToken.setToken(null);
await assert.rejects(requestSpecialCredit(noToken.transport,A,'/capabilities'),/Entre novamente/);
assert.equal(noToken.sent.length,0);checks++;
const member=harness('TENANT_MEMBER');
for(const path of ['/campaigns','/members','/cycle-readiness']){
 await assert.rejects(requestSpecialCredit(member.transport,A,path),/perfil não permitido/);checks++;
}
const admin=harness();
for(const path of ['/opportunities','/preferences']){
 await assert.rejects(requestSpecialCredit(admin.transport,A,path),/perfil não permitido/);checks++;
}
for(const [role,path] of [['TENANT_MEMBER','/campaigns'],['TENANT_ADMIN','/preferences']] as const){
 const h=harness(role);
 await assert.rejects(requestSpecialCredit(h.transport,A,path,{}),/perfil não permitido/);
 assert.equal(h.sent.length,0);checks++;
}
for(const path of ['//outside','/../grants','/grants?token=x','/grants#x','/api/v1/auth/login','/campaigns/'+B+'/publish']){
 const h=harness();
 await assert.rejects(requestSpecialCredit(h.transport,A,path),/Caminho|perfil não permitido/);
 assert.equal(h.sent.length,0);checks++;
}
for(const origin of ['http://192.0.2.40:8000','http://not-local.invalid','https://user:pass@example.com']){
 const h=harness();h.transport.origin=()=>origin;
 await assert.rejects(requestSpecialCredit(h.transport,A,'/capabilities'),/Servidor FR Finance não configurado/);
 assert.equal(h.sent.length,0);checks++;
}
for(const role of ['MASTER','TENANT_MEMBER','TENANT_ADMIN'] as const){
 assert.equal(isRoleTabAllowed(role,role==='TENANT_MEMBER'?'CAMPANHAS_MEMBROS':'MINHAS_OPORTUNIDADES'),false);
 checks++;
}
assert.equal(isRoleTabAllowed('MASTER','CAMPANHAS_MEMBROS'),false);checks++;
const expired=harness();expired.setReply(Response.json({detail:'expired'},{status:401}));
await assert.rejects(requestSpecialCredit(expired.transport,A,'/capabilities'),/Sessão expirada/);
assert.equal(expired.invalidations(),1);assert.equal(expired.sent.length,1);checks++;
const old=harness();
old.transport.send=async()=>{old.setCurrent(false);return Response.json({detail:'old'},{status:401});};
await assert.rejects(requestSpecialCredit(old.transport,A,'/capabilities'),/A sessão mudou/);
assert.equal(old.invalidations(),0);checks++;
const lost=harness();let attempts=0;
lost.transport.send=async()=>{attempts++;throw Error('network lost');};
await assert.rejects(requestSpecialCredit(lost.transport,A,'/campaigns',{title:'CI'}),/Não repita a operação automaticamente/);
assert.equal(attempts,1);assert.equal(lost.invalidations(),0);checks++;
const stale=harness();let staleAttempts=0;
stale.transport.send=async()=>{staleAttempts++;stale.setCurrent(false);throw Error('timeout');};
await assert.rejects(requestSpecialCredit(stale.transport,A,'/capabilities'),/A sessão mudou durante a consulta/);
assert.equal(staleAttempts,1);assert.equal(stale.invalidations(),0);checks++;
for(const [status,pattern] of [[403,/403/],[404,/não encontrada no backend/],[429,/429/],[500,/500/],[503,/Módulo em preparação/]] as const){
 const h=harness();h.setReply(Response.json({detail:'error'},{status}));
 await assert.rejects(requestSpecialCredit(h.transport,A,'/campaigns'),pattern);
 assert.equal(h.sent.length,1);assert.equal(h.invalidations(),0);checks++;
}
const absent=harness();absent.setReply(Response.json({}, {status:404}));
await assert.rejects(requestSpecialCredit(absent.transport,A,'/capabilities'),/API em execução está desatualizada/);checks++;
assert.deepEqual(assertSandboxCreditCapabilities(safe),safe);checks++;
for(const bad of [
 {...safe,real_credit_enabled:true},{...safe,pix_real_enabled:true},
 {...safe,grants_allow_request_only:false},
 {...safe,channels:{...safe.channels,PUSH:{code_present:true,real_delivery_enabled:true}}},
 {...safe,channels:{...safe.channels,SMS:{code_present:false,real_delivery_enabled:false}}},
 {...safe,channels:{}},{...safe,sandbox_enabled:'YES'},null,[],
]){
 assert.throws(()=>assertSandboxCreditCapabilities(bad));checks++;
}
assert.equal(checks,44,'M40390 count drift: '+checks);
console.log('M40390_MOBILE_NEGATIVE_CASES=PASS_44_OF_44');
console.log('M40390_CLIENT_TENANT_ROLE_MASTER=DENIED');
console.log('M40390_SESSION_EXPIRED_NETWORK_POST_RETRY=DENIED');
console.log('M40390_CREDIT_AND_EXTERNAL_DELIVERY=OFF');
console.log('M40390_REQUESTS=MOCK_ONLY');
console.log('M40390_TERMUX_DATABASE=NOT_CONNECTED');
