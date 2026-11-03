/* Pacote 17: feedback de simulação sem vazamento ou ativação financeira. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {authService} from '../services/authService';
import {financialApi,FinancialApiHttpError,FinancialBackendUnavailableError,
 SessionBoundaryError} from '../services/financialApiService';
import {ApiResponseIntegrityError} from '../services/apiResponsePolicy';
import {loanSimulationFailureMessage} from '../services/loanSimulationFeedback';
const A='00000000-0000-4000-8000-000000000001';
const U='00000000-0000-4000-8000-000000000002';
const cases: Array<[number,string,string]>=[
  [409,'Não há ciclo aberto autorizado para simulação.','ciclo ABERTO'],
  [409,'A política financeira vigente não está configurada.','política financeira ACTIVE'],
  [409,'Detalhe arbitrário','condição contratual'],
  [422,'Prazo excede o limite da política vigente da caixinha.','prazo escolhido'],
  [422,'Erro desconhecido','calendário'],
  [404,'Erro de proxy','não foi encontrada'],
];
for(const [status,detail,fragment] of cases){
 const feedback=loanSimulationFailureMessage(new FinancialApiHttpError(detail as string,status as number));
 assert(feedback.includes(fragment as string),feedback);
 assert(feedback.includes('Nenhuma operação financeira foi realizada.'));
 assert(!feedback.includes('Detalhe arbitrário'));
}
assert.match(loanSimulationFailureMessage(new FinancialBackendUnavailableError('unsafe','NETWORK_CONNECTION_FAILED')),
 /não está disponível/);
assert.match(loanSimulationFailureMessage(new ApiResponseIntegrityError()),/resposta inválida/);
assert.match(loanSimulationFailureMessage(new SessionBoundaryError('expired','SESSION_REQUIRED')),/sessão/);
assert.doesNotMatch(loanSimulationFailureMessage(new Error('token secret: do not show')),/token|secret/);

const component=readFileSync('src/components/ServerLoansView.tsx','utf8');
assert.match(component,/loanSimulationFailureMessage\(error\)/);
assert.match(component,/requestId !== simulationRequestId\.current/);
const script=readFileSync('backend/scripts/aistudio_price_diagnose_readonly.sh','utf8');
assert.match(script,/BEGIN READ ONLY;/);
assert.match(script,/ROLLBACK;/);
assert.doesNotMatch(script,/\b(?:INSERT|UPDATE|DELETE|GRANT|CREATE|ALTER|TRUNCATE)\b/i);
assert.match(script,/5433/);
assert.match(script,/frcaixinha_aistudio_dev/);

const oldFetch=globalThis.fetch,oldWindow=(globalThis as any).window;
const oldEvent=(globalThis as any).CustomEvent;
(globalThis as any).window={setTimeout:()=>1,clearTimeout:()=>undefined,
 dispatchEvent:()=>true};
(globalThis as any).CustomEvent=class{constructor(public type:string){}};
let code=409,detail='Não há ciclo aberto autorizado para simulação.',requestCount=0;
const reply=(body:unknown,status=200)=>new Response(JSON.stringify(body),{
 status,headers:{'content-type':'application/json'}
});
globalThis.fetch=(async(url:any)=>{
 const path=String(url);
 if(path.endsWith('/login'))return reply({
  token:'synthetic-no-real-login',
  user:{id:U,name:'Pessoa CI',email:'ci@example.invalid',
    role:'TENANT_MEMBER',tenant_id:A},
  expires_at:new Date(Date.now()+900000).toISOString(),
 });
 if(path.endsWith('/logout'))return reply({success:true});
 if(path.endsWith('/simulate')){requestCount++;return reply({detail},code);}
 throw Error('Unexpected route '+path);
}) as typeof fetch;
async function main(){
 try{
  await authService.login('ci@example.invalid','synthetic','TENANT_MEMBER');
  for(const [status,errMessage,fragment] of cases){
   code=status as number;detail=errMessage as string;
   await assert.rejects(financialApi.simulateLoan(A,{principal:500,term_months:5}),
      (error:any)=>error instanceof FinancialApiHttpError &&
       loanSimulationFailureMessage(error).includes(fragment as string));
  }
  assert.equal(requestCount,cases.length,'Sem retry e sem criação de empréstimos');
  console.log('PACOTE_17_PRICE_DIAGNOSTICO_SEGURANCA_CI=PASS');
 }finally{
  await authService.logout();
  globalThis.fetch=oldFetch;
  (globalThis as any).window=oldWindow;
  (globalThis as any).CustomEvent=oldEvent;
 }
}
main().catch(err=>{console.error(err);process.exitCode=1;});
