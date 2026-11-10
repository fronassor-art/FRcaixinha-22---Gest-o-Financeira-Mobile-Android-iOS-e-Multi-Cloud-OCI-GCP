/* Pacote 13: integridade das contribuições e isolamento de sessão em CI. */
import assert from 'node:assert/strict';
import {authService} from '../services/authService';
import {financialApi,FinancialBackendUnavailableError,SessionBoundaryError}
  from '../services/financialApiService';
import {normalizeContributions} from '../services/contributionsData';

const A='00000000-0000-4000-8000-000000000001';
const B='00000000-0000-4000-8000-000000000002';
const U='00000000-0000-4000-8000-000000000003';
const C='00000000-0000-4000-8000-000000000004';
const M='00000000-0000-4000-8000-000000000005';
const CY='00000000-0000-4000-8000-000000000006';
const item={
 id:C,tenant_id:A,cycle_id:CY,membership_id:M,
 competence:'2027-03',due_date:'2027-03-10',
 amount_due:'150.00',amount_paid:'0.00',
 payment_status:'PENDENTE',due_status:'NO_PRAZO',
 member_name:'Pessoa CI',paid_at:null,
};
assert.equal(normalizeContributions([item],A)[0].amount_due,150);
assert.equal(normalizeContributions([item],A)[0].due_status,'A_VENCER');
assert.equal(normalizeContributions([{...item,amount_paid:0.1}],A)[0].amount_paid,0.1);
const minimal=normalizeContributions([{...item,debug_information:'EXTRA'}],A)[0] as unknown as Record<string,unknown>;
assert(!('debug_information' in minimal));
for(const broken of [
 [{...item,tenant_id:B}],
 [{...item,id:'bad id'}],
 [item,item],
 [{...item,due_date:'2027-02-30'}],
 [{...item,competence:'2027-13'}],
 [{...item,amount_due:'3.005'}],
 [{...item,amount_due:'100.00'}],
 [{...item,amount_due:1.005}],
 [{...item,amount_due:NaN}],
 [{...item,amount_paid:151}],
 [{...item,amount_paid:'-1'}],
 [{...item,amount_paid:Infinity}],
 [{...item,payment_status:'QUITADA'}],
 [{...item,paid_at:'invalid'}],
 [{...item,member_name:'X'.repeat(201)}],
 [{...item,cpf:'sensitive'}],
 [{...item,pix_key:'sensitive'}],
 {source:'LOCAL_SEED',items:[item]},
 Array(1001).fill(item),
])assert.throws(()=>normalizeContributions(broken,A));

const originalFetch=globalThis.fetch;
const oldWindow=(globalThis as any).window,oldEvent=(globalThis as any).CustomEvent;
(globalThis as any).window={
 setTimeout:()=>1,clearTimeout:()=>undefined,dispatchEvent:()=>true,
};
(globalThis as any).CustomEvent=class {constructor(public type:string){}};
let role:'MASTER'|'TENANT_ADMIN'|'TENANT_MEMBER'='MASTER';
let mode:'ok'|'invalid'|'503'|'offline'|'pending'='ok';
let resolvePending:(value:Response)=>void=()=>undefined;
let loginCount=0;
const calls:string[]=[];
const reply=(v:unknown,status=200)=>new Response(JSON.stringify(v),{
 status,headers:{'Content-Type':'application/json'}
});
globalThis.fetch=(async(url:any)=>{
 const path=String(url);calls.push(path);
 if(path.endsWith('/login'))return reply({
  token:'test-session-'+(++loginCount),
  user:{id:U,name:'Pessoa CI',email:'ci@example.invalid',
    role,tenant_id:role==='MASTER'?null:A},
  expires_at:new Date(Date.now()+900000).toISOString(),
 });
 if(path.endsWith('/logout'))return reply({success:true});
 if(path.endsWith('/owner-access'))return reply({
   verified:true,role:'MASTER',scope:'PLATFORM_GOVERNANCE_ONLY',
 });
 if(path.endsWith('/contributions')){
  if(mode==='offline')throw Error('offline synthetic');
  if(mode==='pending')return new Promise<Response>(resolve=>{resolvePending=resolve;});
  if(mode==='503')return reply({detail:'unavailable'},503);
  return reply(mode==='invalid'?[{...item,tenant_id:B}]:[item]);
 }
 throw Error('Unexpected route '+path);
}) as typeof fetch;

async function run(){
 try{
  role='MASTER';
  await authService.login('ci@example.invalid','synthetic','MASTER');
  let before=calls.length;
  await assert.rejects(financialApi.fetchContributions(A),/fora do perfil/);
  assert.equal(calls.length,before);
  await authService.logout();

  role='TENANT_ADMIN';
  await authService.login('ci@example.invalid','synthetic','TENANT_ADMIN');
  assert.equal((await financialApi.fetchContributions(A))[0].amount_due,150);
  before=calls.length;
  await assert.rejects(financialApi.fetchContributions(B),/fora do perfil/);
  assert.equal(calls.length,before);
  mode='invalid';
  await assert.rejects(financialApi.fetchContributions(A),/inconsistentes/);
  mode='503';
  await assert.rejects(financialApi.fetchContributions(A),FinancialBackendUnavailableError);
  mode='offline';
  await assert.rejects(financialApi.fetchContributions(A),(e:any)=>
   e instanceof FinancialBackendUnavailableError&&e.code==='NETWORK_CONNECTION_FAILED');
  mode='pending';
  const old=financialApi.fetchContributions(A);
  await authService.logout();
  role='TENANT_MEMBER';
  await authService.login('ci@example.invalid','synthetic','TENANT_MEMBER');
  resolvePending(reply([item]));
  await assert.rejects(old,(e:any)=>e instanceof SessionBoundaryError&&
   e.code==='SESSION_CHANGED_DURING_REQUEST');
  mode='ok';
  assert.equal((await financialApi.fetchContributions(A))[0].tenant_id,A);
  console.log('PACOTE_13_CONTRIBUICOES_INTEGRIDADE_CI=PASS');
 }finally{
  await authService.logout();
  globalThis.fetch=originalFetch;
  (globalThis as any).window=oldWindow;
  (globalThis as any).CustomEvent=oldEvent;
 }
}
run().catch(e=>{console.error(e);process.exitCode=1;});
