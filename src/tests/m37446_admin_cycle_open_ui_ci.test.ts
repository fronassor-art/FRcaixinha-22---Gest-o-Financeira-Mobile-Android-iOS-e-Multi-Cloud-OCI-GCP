import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseCyclePriceInput} from '../services/cyclePriceBoundary';
import {parseCycleOpeningPreview,openingPreviewMatchesForm} from '../services/cycleOpeningBoundary';
import {authService} from '../services/authService';
import {financialApi,SessionBoundaryError,FinancialBackendUnavailableError} from '../services/financialApiService';

const TENANT='00000000-0000-4000-8000-0000000000a1';
const OTHER='00000000-0000-4000-8000-0000000000a9';
const USER='00000000-0000-4000-8000-0000000000a2';
const REASON='Valor declarado pelo administrador para novo ciclo';
const nextYear=2030;
const preview={
 contract:'AI_STUDIO_M20800_CYCLE_OPENING_PREVIEW_V1',
 source:'POSTGRESQL_RLS_AUTHENTICATED_ADMIN',tenant_id:TENANT,year:nextYear,
 start_date:'2030-01-01',end_date:'2030-12-31',
 amount_cents:20000,minimum_amount_cents:15000,
 price_explicitly_entered:true,historical_obligations_unchanged:true,
 blocked_reasons:[],preconditions_satisfied:true,cycle_creation_enabled:false,
 financial_effect:false,reason_recorded:false,
};
for(const [raw,cents] of ([['150',15000],['200,00',20000],['325.00',32500]] as const))
 assert.equal(parseCyclePriceInput(raw),cents);
for(const raw of ['100','149,99','0','10000,01'])
 assert.throws(()=>parseCyclePriceInput(raw));
const valid=parseCycleOpeningPreview(preview,TENANT);
const intent={tenantId:TENANT,year:nextYear,amountCents:20000,reason:REASON};
assert(openingPreviewMatchesForm(valid,intent,intent));
for(const differing of [
 {...intent,reason:REASON+' alterado'}, {...intent,year:2031},
 {...intent,amountCents:32500},{...intent,tenantId:OTHER},
])
 assert(!openingPreviewMatchesForm(valid,intent,differing));
assert(!openingPreviewMatchesForm(
 parseCycleOpeningPreview({...preview,amount_cents:32500},TENANT),
 intent,intent
));
assert(!openingPreviewMatchesForm(
 parseCycleOpeningPreview({...preview,year:2031},TENANT),
 intent,intent
));
const component=readFileSync('src/components/CycleOpeningPreviewPanel.tsx','utf8');
assert.match(component,/onChange=\{e=>\{invalidate\(\);setReason\(e\.target\.value\)/);
assert.match(component,/approved\.current=null/);
assert.match(component,/revision\.current/);
assert.match(component,/openingPreviewMatchesForm/);
assert.match(component,/disabled=\{opening\} value=\{reason\}/);
assert.doesNotMatch(component,/useState\(['"]150/);
assert.doesNotMatch(component,/defaultValue=['"]150/);

(globalThis as any).window={
 setTimeout:(_:unknown,_delay:unknown)=>1,clearTimeout:(_:unknown)=>undefined,
 dispatchEvent:(_:unknown)=>true,
};
(globalThis as any).CustomEvent=class{constructor(public type:string){}};
const savedFetch=globalThis.fetch;
let role:'TENANT_ADMIN'|'TENANT_MEMBER'='TENANT_ADMIN';
let sent=0;
let mode:'ok'|'pending'|'error'='ok';
let resolvePending:(r:Response)=>void=()=>undefined;
let requests:{url:string;body:any;auth:string}[]=[];
const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{
 status,headers:{'Content-Type':'application/json'}
});
globalThis.fetch=(async(url:any,options?:RequestInit)=>{
 const endpoint=String(url);
 if(endpoint.endsWith('/login')){
  return response({token:'m37446-'+role+'-synthetic-token',
   user:{id:USER,name:'CI',email:'test@example.invalid',role,tenant_id:TENANT},
   expires_at:new Date(Date.now()+800000).toISOString()});
 }
 if(endpoint.endsWith('/logout'))return response({success:true});
 if(endpoint.endsWith('/opening-preview')||endpoint.endsWith('/opening')){
  sent++;
  const body=JSON.parse(String(options?.body||'{}'));
  requests.push({url:endpoint,body,auth:String((options?.headers as any)?.Authorization??'')});
  if(mode==='pending')return new Promise<Response>(resolve=>{resolvePending=resolve});
  if(mode==='error')return response({detail:'server blocked'},503);
  if(endpoint.endsWith('/opening-preview'))return response({...preview,amount_cents:body.amount_cents});
  return response({
    contract:'FR_FINANCE_M37423_CYCLE_OPENING_V1',
    source:'POSTGRESQL_AUTHENTICATED_ADMIN_M044',tenant_id:TENANT,
    opened_cycle_id:'00000000-0000-4000-8000-0000000000b1',
    opened_policy_id:'00000000-0000-4000-8000-0000000000b2',
    year:body.year,amount_cents:body.amount_cents,
    opening_status:'CREATED',opening_audit_persisted:true,
    existing_contributions_repriced:false,payments_executed:false,
  });
 }
 throw Error('Unexpected CI-only path '+endpoint);
}) as typeof fetch;
const login=async()=>authService.login('test@example.invalid','ci','TENANT_ADMIN');
async function run(){
 try{
  await login();
  for(const cents of [15000,20000,32500]){
   const got=await financialApi.previewCycleOpening(TENANT,nextYear,cents,REASON);
   assert.equal(got.amount_cents,cents);
   assert.equal(got.financial_effect,false);
  }
  assert.deepEqual(requests.map(x=>x.body.amount_cents),[15000,20000,32500]);
  assert(requests.every(x=>x.auth.startsWith('Bearer ')));
  const receipt=await financialApi.openCycle(TENANT,nextYear,32500,REASON,
   '00000000-0000-4000-8000-0000000000c1');
  assert.equal(receipt.amount_cents,32500);
  assert.equal(receipt.payments_executed,false);
  assert.equal(receipt.existing_contributions_repriced,false);
  assert.equal(requests.at(-1)?.body.idempotency_key,'00000000-0000-4000-8000-0000000000c1');
  const total=sent;
  await assert.rejects(financialApi.openCycle(OTHER,nextYear,20000,REASON,
   '00000000-0000-4000-8000-0000000000c2'));
  assert.equal(sent,total,'Wrong tenant cannot reach network');
  mode='error';
  await assert.rejects(financialApi.openCycle(TENANT,nextYear,20000,REASON,
   '00000000-0000-4000-8000-0000000000c2'),FinancialBackendUnavailableError);
  assert.equal(sent,total+1,'503 must not trigger automatic retry');
  mode='pending';
  const oldPreview=financialApi.previewCycleOpening(TENANT,nextYear,20000,REASON);
  await authService.logout();
  resolvePending(response(preview));
  await assert.rejects(oldPreview,(error:any)=>
   error instanceof SessionBoundaryError && error.code==='SESSION_CHANGED_DURING_REQUEST');
  role='TENANT_MEMBER';
  await authService.login('test@example.invalid','ci','TENANT_MEMBER');
  const memberTotal=sent;
  await assert.rejects(financialApi.previewCycleOpening(TENANT,nextYear,20000,REASON));
  await assert.rejects(financialApi.openCycle(TENANT,nextYear,20000,REASON,
   '00000000-0000-4000-8000-0000000000c2'));
  assert.equal(sent,memberTotal,'TENANT_MEMBER cannot invoke opening HTTP endpoints');
  console.log('M37446_MOBILE_ADMIN_PREVIEW_OPEN_SESSION_SCOPE=PASS');
 }finally{
  await authService.logout();
  globalThis.fetch=savedFetch;
 }
}
run().catch(err=>{console.error(err);process.exitCode=1});
