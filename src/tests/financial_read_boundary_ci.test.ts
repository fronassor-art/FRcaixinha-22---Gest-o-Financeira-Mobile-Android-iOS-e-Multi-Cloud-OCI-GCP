/* Pacote 12: testagem adversarial das leituras financeiras em homologação. */
import assert from 'node:assert/strict';
import {authService} from '../services/authService';
import {financialApi} from '../services/financialApiService';
import {parseTenantLoans} from '../services/loanReadBoundary';

const A='00000000-0000-4000-8000-000000000001';
const B='00000000-0000-4000-8000-000000000002';
const U='00000000-0000-4000-8000-000000000003';
const L='00000000-0000-4000-8000-000000000004';
const I='00000000-0000-4000-8000-000000000005';
const example={
 id:L,tenant_id:A,borrower_name:'Pessoa CI',principal:'500.00',
 term_months:5,monthly_payment:'150.00',total_interest:'250.00',
 status:'SOLICITADO',installments:[
  {id:I,installment_number:1,due_date:'2027-02-10',status:'PENDENTE'}
 ],
};
assert.equal(parseTenantLoans([example],A)[0].principal,500);
assert.equal(parseTenantLoans([{...example,monthly_rate:'0.20'}],A)[0].installments.length,1);
const clean=parseTenantLoans([{...example,monthly_rate:'0.20'}],A)[0] as Record<string,unknown>;
assert(!('monthly_rate' in clean),'O cliente exibe somente campos do painel');
for(const bad of [
 [{...example,tenant_id:B}],
 [{...example,principal:'Infinity'}],
 [{...example,principal:-3}],
 [{...example,total_interest:'-10'}],
 [{...example,term_months:7}],
 [{...example,installments:[...example.installments,example.installments[0]]}],
 [{...example,installments:[{...example.installments[0],due_date:'2050-99-99'}]}],
 [{...example,installments:[{...example.installments[0],token:'confidential'}]}],
 [{...example,cpf:'confidential'}],
 [example,example],
 Array(501).fill(example),
]){
 assert.throws(()=>parseTenantLoans(bad,A));
}
const oldFetch=globalThis.fetch,oldWindow=(globalThis as any).window;
const oldEvent=(globalThis as any).CustomEvent;
(globalThis as any).window={setTimeout:()=>1,clearTimeout:()=>undefined,dispatchEvent:()=>true};
(globalThis as any).CustomEvent=class{constructor(public type:string){}};
let role:'MASTER'|'TENANT_ADMIN'|'TENANT_MEMBER'='MASTER';
let calls:string[]=[];
let wrongTenant=false;
const reply=(data:unknown,status=200)=>new Response(JSON.stringify(data),{
 status,headers:{'content-type':'application/json'}
});
globalThis.fetch=(async(url:any)=>{
 const path=String(url);calls.push(path);
 if(path.endsWith('/login'))return reply({
  token:'test-only-'+calls.length,
  user:{id:U,name:'Synthetic',email:'ci@example.invalid',
   role,tenant_id:role==='MASTER'?null:A},
  expires_at:new Date(Date.now()+900000).toISOString()
 });
 if(path.endsWith('/owner-access'))return reply({
  verified:true,role:'MASTER',scope:'PLATFORM_GOVERNANCE_ONLY'
 });
 if(path.endsWith('/logout'))return reply({success:true});
 if(path.endsWith('/loans'))return reply([{...example,tenant_id:wrongTenant?B:A}]);
 if(path.endsWith('/contributions'))return reply([]);
 if(path.endsWith('/simulate'))return reply({schedule:[]});
 throw Error('CI unexpected URL '+path);
}) as typeof fetch;

async function test(){
 try{
  role='MASTER';
  await authService.login('ci@example.invalid','synthetic','MASTER');
  let before=calls.length;
  await assert.rejects(financialApi.fetchLoans(A),/fora do perfil/);
  await assert.rejects(financialApi.fetchContributions(A),/fora do perfil/);
  await assert.rejects(financialApi.simulateLoan(A,{principal:500,term_months:5}),/fora do perfil/);
  assert.equal(calls.length,before,'Master nunca consulta dados financeiros do tenant');
  await authService.logout();

  role='TENANT_ADMIN';
  await authService.login('ci@example.invalid','synthetic','TENANT_ADMIN');
  assert.equal((await financialApi.fetchLoans(A))[0].id,L);
  assert.deepEqual(await financialApi.fetchContributions(A),[]);
  before=calls.length;
  await assert.rejects(financialApi.fetchLoans(B),/fora do perfil/);
  await assert.rejects(financialApi.fetchContributions(B),/fora do perfil/);
  assert.equal(calls.length,before,'Admin não consulta outra caixinha');
  wrongTenant=true;
  await assert.rejects(financialApi.fetchLoans(A),/fora da caixinha/);
  wrongTenant=false;
  await authService.logout();

  role='TENANT_MEMBER';
  await authService.login('ci@example.invalid','synthetic','TENANT_MEMBER');
  assert.equal((await financialApi.fetchLoans(A))[0].id,L);
  assert.deepEqual(await financialApi.fetchContributions(A),[]);
  await authService.logout();
  console.log('PACOTE_12_LEITURAS_FINANCEIRAS_CI=PASS');
 }finally{
  await authService.logout();
  globalThis.fetch=oldFetch;
  (globalThis as any).window=oldWindow;
  (globalThis as any).CustomEvent=oldEvent;
 }
}
test().catch(e=>{console.error(e);process.exitCode=1;});
