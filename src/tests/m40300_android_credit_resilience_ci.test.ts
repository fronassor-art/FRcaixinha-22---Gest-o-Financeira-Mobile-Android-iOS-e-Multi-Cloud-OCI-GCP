/** M40300 — um app e uma sessão, sem rede real/PIX/FCM.
 * Segurança de rotas do Crédito Especial, offline sem retry e UI foreground.
 */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  requestSpecialCredit, type SpecialCreditTransport,
} from '../services/specialCreditRequestBoundary';
import type {AuthenticatedUser,AuthSessionSnapshot} from '../services/authService';

const A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const GRANT='11111111-1111-4111-8111-111111111111';
const ORIGIN='https://api.frfinance.com.br';
const makeUser=(role:AuthenticatedUser['role'],tenantId:string|null=A):AuthenticatedUser=>({
  id:'22222222-2222-4222-8222-222222222222',
  name:'Pessoa Sintética',email:'ci@example.invalid',role,
  tenantId:tenantId??undefined,
});
function fakeTransport(role:AuthenticatedUser['role']='TENANT_MEMBER') {
  let user:AuthenticatedUser|null=makeUser(role);
  let current=true;
  let invalidated=0;
  const requests:Array<{url:string;options:RequestInit}>=[];
  let sendImpl=async(_url:string,_options:RequestInit)=>
    Response.json({source:'SYNTHETIC'}, {status:200});
  const snapshot:AuthSessionSnapshot={token:'SYNTHETIC_NOT_VALID',generation:11};
  const transport:SpecialCreditTransport={
    origin:()=>ORIGIN,captureSession:()=>snapshot,isCurrent:()=>current,
    getUser:()=>user,invalidateIfCurrent:()=>{invalidated++;return true;},
    send:async(url,options)=>{requests.push({url,options});return sendImpl(url,options);},
  };
  return {transport,requests,
    setUser:(next:AuthenticatedUser|null)=>{user=next;},
    setCurrent:(value:boolean)=>{current=value;},
    setSend:(func:typeof sendImpl)=>{sendImpl=func;},
    invalidations:()=>invalidated,
  };
}

async function routing() {
  const h=fakeTransport('TENANT_MEMBER');
  const badPaths=[
    '/../master', '/%2e%2e/master','/grants/../../admin','/grants//revoke',
    '/opportunities/NO_UUID/reply','/campaigns/'+GRANT+'/publish',
    '/api/v1/master/owner-access','//api/v1/master','/grants?x=1',
    '/preferences#fragment','/capabilities/..','/capabilities%2f..',
  ];
  for(const path of badPaths) {
    await assert.rejects(requestSpecialCredit(h.transport,A,path),/Caminho|perfil/);
    await assert.rejects(requestSpecialCredit(h.transport,A,path,{}),/Caminho|perfil/);
  }
  assert.equal(h.requests.length,0,'caminhos proibidos não fazem fetch');

  const admin=fakeTransport('TENANT_ADMIN');
  for(const forbidden of ['/opportunities','/preferences']){
    await assert.rejects(requestSpecialCredit(admin.transport,A,forbidden),/Caminho|perfil/);
  }
  await assert.rejects(requestSpecialCredit(admin.transport,A,'/simulate',{}),/Caminho|perfil/);
  assert.equal(admin.requests.length,0);
  const mem=fakeTransport('TENANT_MEMBER');
  for(const forbidden of ['/members','/campaigns','/cycle-readiness']){
    await assert.rejects(requestSpecialCredit(mem.transport,A,forbidden),/Caminho|perfil/);
  }
  await assert.rejects(requestSpecialCredit(mem.transport,A,'/campaigns',{}),/Caminho|perfil/);
  await assert.rejects(requestSpecialCredit(mem.transport,B,'/opportunities'),/caixinha não corresponde/);
  assert.equal(mem.requests.length,0);
  assert.equal(mem.invalidations(),0);

  await requestSpecialCredit(mem.transport,A,'/opportunities/'+GRANT+'/reply',
                            {status:'DECLINED'});
  assert.equal(mem.requests.length,1);
  assert.equal(mem.requests[0].options.method,'POST');
  assert.equal(mem.requests[0].options.cache,'no-store');
  assert.equal(mem.invalidations(),0);
  await requestSpecialCredit(admin.transport,A,'/campaigns/'+GRANT+'/cancel',{});
  assert.equal(admin.requests.length,1);
  assert.equal(admin.requests[0].options.method,'POST');
  console.log('M40300_CREDIT_ROUTE_ALLOWLIST=PASS');
}

async function suspendedTermuxDoesNotMeanDataLoss() {
  const h=fakeTransport('TENANT_MEMBER');
  h.setSend(async()=>{
    throw new TypeError('SIMULATED_ANDROID_KILLED_TERMUX_CONNECTION');
  });
  for(const [path,body] of [
    ['/opportunities',undefined],
    ['/opportunities/'+GRANT+'/reply',{status:'INTERESTED'}],
  ] as const){
    const before=h.requests.length;
    await assert.rejects(requestSpecialCredit(h.transport,A,path,body),
      err=>err instanceof Error && err.message.includes('FastAPI e PostgreSQL') &&
           err.message.includes('não indica perda do banco') &&
           !err.message.includes('SIMULATED_ANDROID_KILLED'));
    assert.equal(h.requests.length,before+1,'SEM replay automático de GET ou POST');
    assert.equal(h.invalidations(),0,'sem HTTP 401 não declarar revogação');
  }
  const late=fakeTransport('TENANT_MEMBER');
  late.setSend(async()=>{late.setCurrent(false);throw new Error('offline');});
  await assert.rejects(requestSpecialCredit(late.transport,A,'/opportunities'),
                       /sessão mudou/);
  assert.equal(late.invalidations(),0,'falha antiga não derruba sessão nova');
  console.log('M40300_ANDROID_TERMINAL_SUSPENSION_NOT_DB_LOSS=PASS');
}

function staticUiAndSessions() {
  const source=readFileSync('src/components/SpecialCreditView.tsx','utf8');
  assert(source.includes('const operationEpoch=useRef(0);'));
  assert(source.includes('operationEpoch.current++;setBusy(false);'));
  assert(source.includes('const operation=++operationEpoch.current;'));
  assert(source.includes('if(operationEpoch.current===operation)setBusy(false);'));
  assert(source.includes('authService.isSessionSnapshotCurrent(snapshot)'));
  assert(source.includes("PUSH:false,EMAIL:false,WHATSAPP:false,SMS:false"));
  assert(source.includes('Nenhum valor aprovado ou liberado'));
  assert(source.includes('Nenhum empréstimo foi solicitado'));
  assert(source.includes('Nenhuma mensagem externa'));
  const app=readFileSync('src/App.tsx','utf8');
  assert(app.includes("window.addEventListener('pageshow', onPageShow)"));
  assert(app.includes("document.addEventListener('visibilitychange', onVisible)"));
  const config=readFileSync('capacitor.config.ts','utf8');
  assert(config.includes('FR_FINANCE_ANDROID_RELEASE_PROFILE'));
  assert(config.includes('M21700: release não aceita Termux.'));
  console.log('M40300_ANDROID_CONTEXT_UI_SOURCE=PASS');
}

await routing();
await suspendedTermuxDoesNotMeanDataLoss();
staticUiAndSessions();
console.log('M40300_FRONTEND_SECURITY_CREDIT_ANDROID=PASS_NO_REAL_IO');
