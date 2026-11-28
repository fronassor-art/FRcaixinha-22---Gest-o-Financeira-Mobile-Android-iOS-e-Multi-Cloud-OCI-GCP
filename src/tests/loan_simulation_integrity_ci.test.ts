/* Validação sintética de Price no checkpoint Android 180. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {authService} from '../services/authService';
import {financialApi,FinancialBackendUnavailableError,SessionBoundaryError}
 from '../services/financialApiService';
import {parseLoanSimulation,validateSimulationRequest} from '../services/loanSimulationBoundary';
const A='00000000-0000-4000-8000-000000000001';
const B='00000000-0000-4000-8000-000000000002';
const U='00000000-0000-4000-8000-000000000003';
const amort=[67.19,80.63,96.75,116.10,139.33];
const interest=[100,86.56,70.44,51.09,27.87];
const opening=[500,432.81,352.18,255.43,139.33];
const closing=[432.81,352.18,255.43,139.33,0];
const schedule=amort.map((part,i)=>({
 installment_number:i+1,
 due_date:'2027-'+String(i+1).padStart(2,'0')+'-10',
 opening_balance:opening[i].toFixed(2),
 interest_portion:interest[i].toFixed(2),
 amortization_portion:part.toFixed(2),
 monthly_payment:(part+interest[i]).toFixed(2),
 closing_balance:closing[i].toFixed(2),is_cents_adjusted:i===4,
}));
const result={principal:'500.00',monthly_rate:'0.20',term_months:5,
 uniform_payment:'167.19',last_payment:'167.20',
 total_interest:'335.96',total_payable:'835.96',
 is_irregular_first_period:false,first_period_days:null,
 effective_first_rate:'0.20000000',schedule};
const req={principal:500,term_months:5};
const valid=parseLoanSimulation(result,req);
assert.equal(valid.total_payable,835.96);
assert.equal(valid.schedule[4].closing_balance,0);
assert.equal(valid.schedule[4].monthly_payment,167.20);
for(const invalid of [
 {...result,principal:'501.00'},{...result,total_payable:'835.95'},
 {...result,total_interest:'335.95'},{...result,monthly_rate:'Infinity'},
 {...result,term_months:6},{...result,schedule:[]},
 {...result,schedule:schedule.map((r,i)=>i===2?{...r,closing_balance:'0.00'}:r)},
 {...result,schedule:schedule.map((r,i)=>i===1?{...r,due_date:'2027-02-30'}:r)},
 {...result,schedule:schedule.map((r,i)=>i===1?{...r,due_date:'2027-04-10'}:r)},
 {...result,schedule:schedule.map((r,i)=>i===1?{...r,interest_portion:'90.00'}:r)},
 {...result,schedule:schedule.map((r,i)=>i===1?{...r,installment_number:1}:r)},
 {...result,schedule:schedule.map((r,i)=>i===1?{...r,token:'sensitive'}:r)},
 {...result,cpf:'private'}, {...result,first_period_days:-1},
 ])assert.throws(()=>parseLoanSimulation(invalid,req));
for(const invalid of [
 {principal:500.001,term_months:5},{principal:500,term_months:7},
 {principal:-1,term_months:5},{principal:Infinity,term_months:2},
 {principal:500,term_months:1.5},
 ])assert.throws(()=>validateSimulationRequest(invalid));
const src=readFileSync('src/components/ServerLoansView.tsx','utf8');
assert.match(src,/simulationRequestId\.current\+\+/);
assert.match(src,/requestId !== simulationRequestId\.current/);
assert.match(src,/setSimulation\(null\)/);

const oldFetch=globalThis.fetch,oldWindow=(globalThis as any).window;
const oldEvent=(globalThis as any).CustomEvent;
(globalThis as any).window={setTimeout:()=>1,clearTimeout:()=>undefined,dispatchEvent:()=>true};
(globalThis as any).CustomEvent=class{constructor(public type:string){}};
let role:'MASTER'|'TENANT_ADMIN'|'TENANT_MEMBER'='MASTER';
let mode:'ok'|'bad'|'503'|'deferred'='ok';
let finish:(v:Response)=>void=()=>undefined;
let calls:string[]=[];let logins=0;
const reply=(body:unknown,status=200)=>new Response(JSON.stringify(body),{
 status,headers:{'Content-Type':'application/json'},
});
globalThis.fetch=(async(url:any)=>{
 const path=String(url);calls.push(path);
 if(path.endsWith('/login'))return reply({
  token:'ci-token-'+(++logins),
  user:{id:U,name:'Pessoa CI',email:'ci@example.invalid',role,
    tenant_id:role==='MASTER'?null:A},
  expires_at:new Date(Date.now()+900000).toISOString(),
 });
 if(path.endsWith('/owner-access'))return reply({
  verified:true,role:'MASTER',scope:'PLATFORM_GOVERNANCE_ONLY',
 });
 if(path.endsWith('/logout'))return reply({success:true});
 if(path.endsWith('/simulate')){
  if(mode==='deferred')return new Promise<Response>(resolve=>{finish=resolve;});
  if(mode==='503')return reply({detail:'unavailable'},503);
  return reply(mode==='bad'?{...result,total_payable:'0.00'}:result);
 }
 throw Error('Unexpected endpoint '+path);
}) as typeof fetch;
async function run(){
 try{
  role='MASTER';await authService.login('ci@example.invalid','CI','MASTER');
  let before=calls.length;
  await assert.rejects(financialApi.simulateLoan(A,req),/fora do perfil/);
  assert.equal(calls.length,before);
  await authService.logout();
  role='TENANT_ADMIN';await authService.login('ci@example.invalid','CI','TENANT_ADMIN');
  assert.equal((await financialApi.simulateLoan(A,req)).total_payable,835.96);
  before=calls.length;
  await assert.rejects(financialApi.simulateLoan(B,req),/fora do perfil/);
  await assert.rejects(financialApi.simulateLoan(A,{principal:1.001,term_months:5}));
  assert.equal(calls.length,before,'Requisições inválidas são barradas antes da rede');
  mode='bad';
  await assert.rejects(financialApi.simulateLoan(A,req),/Totais|incompatíveis|divergente/);
  mode='503';await assert.rejects(financialApi.simulateLoan(A,req),FinancialBackendUnavailableError);
  mode='deferred';
  const previous=financialApi.simulateLoan(A,req);
  await authService.logout();
  role='TENANT_MEMBER';await authService.login('ci@example.invalid','CI','TENANT_MEMBER');
  finish(reply(result));
  await assert.rejects(previous,(e:any)=>e instanceof SessionBoundaryError&&
    e.code==='SESSION_CHANGED_DURING_REQUEST');
  mode='ok';
  assert.equal((await financialApi.simulateLoan(A,req)).total_interest,335.96);
  await authService.logout();
  console.log('PACOTE_15_PRICE_CHECKPOINT_180_CI=PASS');
 }finally{
  await authService.logout();
  globalThis.fetch=oldFetch;
  (globalThis as any).window=oldWindow;
  (globalThis as any).CustomEvent=oldEvent;
 }
}
run().catch(err=>{console.error(err);process.exitCode=1;});
