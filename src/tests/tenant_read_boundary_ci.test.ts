/* Checkpoint 170: valida painel e lista por perfil com dados sintéticos. */
import assert from 'node:assert/strict';
import {
  assertTenantReadScope,parseTenantDashboard,parseTenantMembers,
} from '../services/tenantReadBoundary';
import {isRoleTabAllowed} from '../services/roleScope';
import {authService} from '../services/authService';
import {financialApi} from '../services/financialApiService';

const A='00000000-0000-4000-8000-000000000001';
const B='00000000-0000-4000-8000-000000000002';
const M='00000000-0000-4000-8000-000000000003';
const member={
  id:M,name:'Pessoa sintética',role:'TENANT_MEMBER',
  status:'ATIVA',joined_at:'2026-11-03T08:00:00+00:00',
};
const dashboard=(role:'TENANT_MEMBER'|'TENANT_ADMIN',tenant=A)=>({
  source:'POSTGRESQL_RLS',tenant_id:tenant,role,
  quota_count_visible:0,contribution_count_visible:0,loan_count_visible:0,
  ...(role==='TENANT_ADMIN'?{member_count_visible:2}:{}),
  financial_operations:'PENDING_BANK_RECONCILIATION',
});
const u=(role:string,tenantId:string|null)=>({role,tenantId});
assert.throws(()=>assertTenantReadScope(u('MASTER',null),A,'DASHBOARD'));
assert.throws(()=>assertTenantReadScope(u('TENANT_MEMBER',A),A,'MEMBERS'));
assert.throws(()=>assertTenantReadScope(u('TENANT_ADMIN',A),B,'MEMBERS'));
assert.equal(assertTenantReadScope(u('TENANT_ADMIN',A),A,'MEMBERS'),'TENANT_ADMIN');
assert.equal(assertTenantReadScope(u('TENANT_MEMBER',A),A,'DASHBOARD'),'TENANT_MEMBER');

assert.equal(parseTenantDashboard(dashboard('TENANT_ADMIN'),A,'TENANT_ADMIN').member_count_visible,2);
const onlyMine=parseTenantDashboard(dashboard('TENANT_MEMBER'),A,'TENANT_MEMBER');
assert(!('member_count_visible' in onlyMine));
assert.throws(()=>parseTenantDashboard(dashboard('TENANT_ADMIN'),A,'TENANT_MEMBER'));
assert.throws(()=>parseTenantDashboard(dashboard('TENANT_MEMBER'),B,'TENANT_MEMBER'));
assert.throws(()=>parseTenantDashboard({...dashboard('TENANT_MEMBER'),member_count_visible:2},
  A,'TENANT_MEMBER'));
assert.throws(()=>parseTenantDashboard({...dashboard('TENANT_ADMIN'),quota_count_visible:-1},
  A,'TENANT_ADMIN'));
assert.throws(()=>parseTenantDashboard({...dashboard('TENANT_ADMIN'),
  financial_operations:'ENABLED'},A,'TENANT_ADMIN'));
const protectedDashboard=parseTenantDashboard({...dashboard('TENANT_ADMIN'),cpf:'PROIBIDO'},
 A,'TENANT_ADMIN') as Record<string,unknown>;
assert(!('cpf' in protectedDashboard));

const members={source:'POSTGRESQL_RLS',tenant_id:A,members:[member]};
assert.equal(parseTenantMembers(members,A).members.length,1);
assert.throws(()=>parseTenantMembers({...members,tenant_id:B},A));
assert.throws(()=>parseTenantMembers({...members,members:[{...member,cpf:'000'}]},A));
assert.throws(()=>parseTenantMembers({...members,members:[member,member]},A));
assert.throws(()=>parseTenantMembers({...members,members:[{...member,name:''}]},A));

for(const tab of ['CAIXINHAS','ADMINISTRADORES','ONBOARDING','LICENCAS']){
  assert(!isRoleTabAllowed('TENANT_ADMIN',tab));
  assert(!isRoleTabAllowed('TENANT_MEMBER',tab));
}
assert(!isRoleTabAllowed('MASTER','MEU_EMPRESTIMO'));
assert(!isRoleTabAllowed('TENANT_MEMBER','MEMBROS'));

const oldFetch=globalThis.fetch;
const oldWindow=(globalThis as any).window;
const oldEvent=(globalThis as any).CustomEvent;
(globalThis as any).window={
  setTimeout:()=>1,clearTimeout:()=>undefined,dispatchEvent:()=>true
};
(globalThis as any).CustomEvent=class{constructor(public type:string){}};
let active:'MASTER'|'TENANT_ADMIN'|'TENANT_MEMBER'='MASTER';
let requests:string[]=[];
const reply=(body:unknown,status=200)=>new Response(JSON.stringify(body),{
  status,headers:{'content-type':'application/json'},
});
globalThis.fetch=(async(url:any,opts?:RequestInit)=>{
  const path=String(url);requests.push(path);
  if(path.endsWith('/login'))return reply({
    token:'test-only-'+active,expires_at:new Date(Date.now()+900000).toISOString(),
    user:{id:M,name:'Pessoa sintética',email:'ci@example.invalid',
      role:active,tenant_id:active==='MASTER'?null:A},
  });
  if(path.endsWith('/owner-access'))return reply({
    verified:true,role:'MASTER',scope:'PLATFORM_GOVERNANCE_ONLY',
  });
  if(path.endsWith('/logout'))return reply({success:true});
  if(path.endsWith('/dashboard'))return reply(dashboard(active as 'TENANT_MEMBER'|'TENANT_ADMIN'));
  if(path.endsWith('/members'))return reply(members);
  throw Error('Unexpected test endpoint: '+path);
}) as typeof fetch;

async function main(){
  try{
    active='MASTER';
    await authService.login('ci@example.invalid','test-only','MASTER');
    let before=requests.length;
    await assert.rejects(financialApi.fetchTenantOverview(A),/fora do perfil/);
    assert.equal(requests.length,before,'Master não consulta painel de tenant no cliente');
    await authService.logout();

    active='TENANT_ADMIN';
    await authService.login('ci@example.invalid','test-only','TENANT_ADMIN');
    assert.equal((await financialApi.fetchTenantOverview(A)).role,'TENANT_ADMIN');
    assert.equal((await financialApi.fetchTenantMembers(A)).members[0].id,M);
    before=requests.length;
    await assert.rejects(financialApi.fetchTenantMembers(B),/fora do perfil/);
    assert.equal(requests.length,before,'Admin de A não consulta B');
    await authService.logout();

    active='TENANT_MEMBER';
    await authService.login('ci@example.invalid','test-only','TENANT_MEMBER');
    assert.equal((await financialApi.fetchTenantOverview(A)).role,'TENANT_MEMBER');
    before=requests.length;
    await assert.rejects(financialApi.fetchTenantMembers(A),/fora do perfil/);
    assert.equal(requests.length,before,'Membro não consulta relação de membros');
    await authService.logout();
    console.log('PACOTE_9_ISOLAMENTO_LEITURAS_CI=PASS');
  }finally{
    await authService.logout();
    globalThis.fetch=oldFetch;
    (globalThis as any).window=oldWindow;
    (globalThis as any).CustomEvent=oldEvent;
  }
}
main().catch(err=>{console.error(err);process.exitCode=1;});
