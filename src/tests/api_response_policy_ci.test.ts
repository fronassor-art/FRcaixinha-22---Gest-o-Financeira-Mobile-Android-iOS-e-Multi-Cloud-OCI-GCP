/* Pacote 14: respostas de API não confiáveis nunca viram dados financeiros. */
import assert from 'node:assert/strict';
import {authService} from '../services/authService';
import {financialApi,FinancialBackendUnavailableError,SessionBoundaryError}
 from '../services/financialApiService';
import {ApiResponseIntegrityError,parseApiErrorEnvelope}
 from '../services/apiResponsePolicy';

const T='00000000-0000-4000-8000-000000000001';
const U='00000000-0000-4000-8000-000000000002';
const validUser={id:U,name:'Pessoa CI',email:'ci@example.invalid',
 role:'TENANT_ADMIN',tenant_id:T};
const dashboard={
 source:'POSTGRESQL_RLS',tenant_id:T,role:'TENANT_ADMIN',
 quota_count_visible:0,contribution_count_visible:0,
 loan_count_visible:0,member_count_visible:0,
 financial_operations:'PENDING_BANK_RECONCILIATION',
};
for(const value of [
 {detail:{detail:{credit_card:'unsafe'}},message:{object:'unsafe'}},
 {message:'Traceback: dangerous',detail:'<script>alert(1)</script>'},
 {message:'Authorization Bearer synthetic-secret'},
 {detail:'X'.repeat(400),code:'bad code!'},
 'plain text',null,[],
]){
 const parsed=parseApiErrorEnvelope(value);
 assert.equal(parsed.message,undefined);
 assert.equal(parsed.detail,undefined);
 assert.equal(parsed.code,undefined);
}
assert.equal(parseApiErrorEnvelope({detail:{message:'Sem permissão CI'}}).detail,
 'Sem permissão CI');
assert.deepEqual(parseApiErrorEnvelope({message:'Servidor indisponível',code:'API_UNAVAILABLE'}),
 {message:'Servidor indisponível',detail:undefined,code:'API_UNAVAILABLE'});

const oldWindow=(globalThis as any).window,oldEvent=(globalThis as any).CustomEvent;
const oldFetch=globalThis.fetch;
(globalThis as any).window={setTimeout:()=>1,clearTimeout:()=>undefined,
 dispatchEvent:()=>true};
(globalThis as any).CustomEvent=class{constructor(public type:string){}};
let body:unknown=dashboard;
let status=200;
let invalidSuccess=false;
let delayedError=false;
let settleError:(response:Response)=>void=()=>undefined;
let loginCount=0;
const paths:string[]=[];
const response=(value:unknown,code=200)=>new Response(JSON.stringify(value),{
 status:code,headers:{'Content-Type':'application/json'},
});
globalThis.fetch=(async(url:any)=>{
 const path=String(url);paths.push(path);
 if(path.endsWith('/login'))return response({
  token:'synthetic-'+(++loginCount),user:validUser,
  expires_at:new Date(Date.now()+900000).toISOString(),
 });
 if(path.endsWith('/logout'))return response({success:true});
 if(path.endsWith('/dashboard')){
  if(delayedError)return new Promise<Response>(resolve=>{settleError=resolve;});
  if(invalidSuccess)return new Response('<html>bad success</html>',{
   status:200,headers:{'content-type':'text/html'},
  });
  return response(body,status);
 }
 if(path.endsWith('/loans/request'))return response(body,status);
 throw Error('Unexpected CI route '+path);
}) as typeof fetch;

async function main(){
 try {
  await authService.login('ci@example.invalid','CI-synthetic','TENANT_ADMIN');
  assert.equal((await financialApi.fetchTenantOverview(T)).tenant_id,T);

  invalidSuccess=true;
  await assert.rejects(financialApi.fetchTenantOverview(T),(e:any)=>
    e instanceof ApiResponseIntegrityError &&
    e.code==='INVALID_BACKEND_RESPONSE');
  invalidSuccess=false;

  body={detail:{message:'Acesso negado CI'}};
  status=403;
  await assert.rejects(financialApi.fetchTenantOverview(T),/Acesso negado CI/);
  assert(authService.isAuthenticated(),'403 não revoga identidade');
  body={detail:{sensitive:'secret'},message:{unsafe:true}};
  await assert.rejects(financialApi.fetchTenantOverview(T),(e:any)=>
   e instanceof Error&&e.message.includes('Acesso negado')&&
   !e.message.includes('[object Object]'));

  status=503;
  const before=paths.length;
  await assert.rejects(financialApi.fetchTenantOverview(T),(e:any)=>
   e instanceof FinancialBackendUnavailableError &&
   e.code==='FASTAPI_BACKEND_UNAVAILABLE');
  assert.equal(paths.length,before+1,'503 não faz retry');
  body={message:'Servidor indisponível',code:'API_UNAVAILABLE'};
  await assert.rejects(financialApi.fetchTenantOverview(T),(e:any)=>
   e instanceof FinancialBackendUnavailableError && e.code==='API_UNAVAILABLE');
  assert(authService.isAuthenticated());

  status=500;body={detail:'<script>alert(1)</script>',message:'Traceback secrets'};
  await assert.rejects(financialApi.fetchTenantOverview(T),(e:any)=>
    e instanceof Error&&!e.message.includes('<script>')&&!e.message.includes('Traceback'));
  body={detail:'Falha interna do processamento CI'};
  await assert.rejects(financialApi.fetchTenantOverview(T),/Falha interna do processamento CI/);

  status=503;body={detail:'NÃO AUTORIZADO',code:'API_UNAVAILABLE'};
  const beforeWrite=paths.length;
  await assert.rejects(financialApi.requestLoan(T,{principal:500,term_months:5}),
    FinancialBackendUnavailableError);
  assert.equal(paths.length,beforeWrite+1,'POST não é repetido automaticamente');

  status=401;body={detail:'invalid'};
  await assert.rejects(financialApi.fetchTenantOverview(T),(e:any)=>
   e instanceof SessionBoundaryError&&e.code==='SESSION_REQUIRED');
  assert.equal(authService.getToken(),null,'401 revoga somente a sessão corrente');

  await authService.login('ci@example.invalid','CI-synthetic','TENANT_ADMIN');
  delayedError=true;
  const stale=financialApi.fetchTenantOverview(T);
  await authService.logout();
  await authService.login('ci@example.invalid','CI-synthetic','TENANT_ADMIN');
  settleError(response({detail:'older denial'},401));
  await assert.rejects(stale,(e:any)=>e instanceof SessionBoundaryError&&
    e.code==='SESSION_CHANGED_DURING_REQUEST');
  assert(authService.isAuthenticated(),'401 anterior não derruba login novo');
  delayedError=false;
  console.log('PACOTE_14_ERROS_HTTP_JSON_CI=PASS');
 }finally {
  await authService.logout();
  globalThis.fetch=oldFetch;
  (globalThis as any).window=oldWindow;
  (globalThis as any).CustomEvent=oldEvent;
 }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
