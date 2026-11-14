/** FR Finance M39048 — integração de autenticação/tenant/Android offline.
 * Sem fetch real: todos os acessos são respondidos por adaptador de CI.
 */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  requestSpecialCredit, scopedCreditPath, assertSandboxCreditCapabilities,
  type SpecialCreditTransport,
} from '../services/specialCreditRequestBoundary';
import type {AuthenticatedUser} from '../services/authService';

const A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const B = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const ORIGIN = 'https://api.frfinance.com.br';
const SCOPE = '/api/v1/tenants/' + A + '/special-credit';

function makeTestHarness() {
  let user:AuthenticatedUser | null = {
    id:'11111111-1111-4111-8111-111111111111',
    name:'Pessoa Sintética',email:'ci@example.invalid',
    role:'TENANT_ADMIN',tenantId:A,
  };
  let current=true, invalidations=0;
  let response:Response = Response.json({sandbox_enabled:false},{status:200});
  const sent:Array<{url:string;options:RequestInit}>=[];
  const transport:SpecialCreditTransport={
    origin:()=>ORIGIN,
    captureSession:()=>({token:'never-real-credential',generation:1}),
    isCurrent:()=>current,
    getUser:()=>user,
    invalidateIfCurrent:()=>{invalidations++;return true;},
    send:async (url,options)=>{sent.push({url,options});return response.clone();},
  };
  return {
    transport,sent,
    setUser:(v:AuthenticatedUser|null)=>{user=v;},
    setCurrent:(v:boolean)=>{current=v;},
    setResponse:(v:Response)=>{response=v;},
    invalidations:()=>invalidations,
  };
}

async function testSessionAndTenantBoundaries(){
  for(const id of ['', '../b', 'wrong', 'a'.repeat(36)]){
    assert.throws(()=>scopedCreditPath(id),/caixinha inválido/);
  }
  assert.equal(scopedCreditPath(A),SCOPE);

  const h=makeTestHarness();
  await assert.rejects(
    requestSpecialCredit(h.transport,B,'/capabilities'),/não corresponde/);
  assert.equal(h.sent.length,0,'tenant errado nunca consulta a rede');

  h.setUser({...h.transport.getUser()!,role:'MASTER',tenantId:undefined});
  await assert.rejects(requestSpecialCredit(h.transport,A,'/grants'),/Acesso recusado/);
  assert.equal(h.sent.length,0,'MASTER nao acessa dados financeiros');

  h.setUser(null);
  await assert.rejects(requestSpecialCredit(h.transport,A,'/grants'),/Entre novamente/);
  assert.equal(h.sent.length,0);

  h.setUser({id:'22222222-2222-4222-8222-222222222222',
    name:'Pessoa CI',email:'ci@example.invalid',role:'TENANT_MEMBER',tenantId:A});
  await assert.rejects(requestSpecialCredit(h.transport,A,'//outside'),/Caminho/);
  assert.equal(h.sent.length,0);

  const result=await requestSpecialCredit<{sandbox_enabled:boolean}>(
    h.transport,A,'/capabilities');
  assert.equal(result.sandbox_enabled,false);
  assert.equal(h.sent.length,1);
  assert.equal(h.sent[0].url,ORIGIN+SCOPE+'/capabilities');
  const req=h.sent[0].options;
  assert.equal(req.method,'GET');
  assert.equal(req.cache,'no-store');
  assert.equal(req.credentials,'include');
  assert.equal((req.headers as Record<string,string>).Authorization,
    'Bearer never-real-credential');

  await requestSpecialCredit(h.transport,A,'/preferences',{channel:'PUSH',opted_in:false});
  assert.equal(h.sent[1].options.method,'POST');
  assert.deepEqual(JSON.parse(h.sent[1].options.body as string),
    {channel:'PUSH',opted_in:false});
  assert.equal(h.invalidations(),0);
  console.log('M39048_SESSION_TENANT_AND_BEARER=PASS');
}

async function testExpiredAndStaleSessions(){
  const h=makeTestHarness();
  h.setResponse(Response.json({detail:'expired'},{status:401}));
  await assert.rejects(requestSpecialCredit(h.transport,A,'/grants'),/Sessão expirada/);
  assert.equal(h.invalidations(),1);

  const stale=makeTestHarness();
  stale.setCurrent(false);
  await assert.rejects(requestSpecialCredit(stale.transport,A,'/grants'),/Entre novamente/);
  assert.equal(stale.sent.length,0);
  assert.equal(stale.invalidations(),0);

  const during=makeTestHarness();
  const prior=during.transport.send;
  during.transport.send=async(url,options)=>{
    const res=await prior(url,options);
    during.setCurrent(false);
    return res;
  };
  during.setResponse(Response.json({detail:'expired'},{status:401}));
  await assert.rejects(requestSpecialCredit(during.transport,A,'/grants'),/A sessão mudou/);
  assert.equal(during.invalidations(),0,'401 tardio nunca invalida novo login');

  const parsing=makeTestHarness();
  parsing.transport.send=async(url,options)=>{
    const res=await Response.json({items:[]},{status:200});
    parsing.setCurrent(false);
    return res;
  };
  await assert.rejects(requestSpecialCredit(parsing.transport,A,'/opportunities'),
    /A sessão mudou/);
  assert.equal(parsing.invalidations(),0);

  const unavailable=makeTestHarness();
  unavailable.setResponse(Response.json({detail:'off'},{status:503}));
  await assert.rejects(requestSpecialCredit(unavailable.transport,A,'/grants'),
    /Módulo em preparação/);
  assert.equal(unavailable.invalidations(),0);
  console.log('M39048_STALE_SESSION_AND_HTTP_FAIL_CLOSED=PASS');
}

function testNoRealFinanceOrExternalChannel(){
  const safe={
    sandbox_enabled:true, grants_allow_request_only:true,
    real_credit_enabled:false, pix_real_enabled:false,
    channels:Object.fromEntries(['PUSH','EMAIL','WHATSAPP','SMS'].map(
      ch=>[ch,{code_present:true,real_delivery_enabled:false}]))
  };
  assert.deepEqual(assertSandboxCreditCapabilities(safe),safe);
  assert.throws(()=>assertSandboxCreditCapabilities({
    ...safe,real_credit_enabled:true}),/Ativação financeira inesperada/);
  assert.throws(()=>assertSandboxCreditCapabilities({
    ...safe,pix_real_enabled:true}),/Ativação financeira inesperada/);
  assert.throws(()=>assertSandboxCreditCapabilities({
    ...safe,grants_allow_request_only:false}),/Ativação financeira inesperada/);
  assert.throws(()=>assertSandboxCreditCapabilities({
    ...safe,channels:{...safe.channels,PUSH:{code_present:true,real_delivery_enabled:true}}}),
    /Canal externo/);
  assert.throws(()=>assertSandboxCreditCapabilities({...safe,channels:{}}),/Canal externo/);
  assert.throws(()=>assertSandboxCreditCapabilities(null),/Contrato/);
  console.log('M39048_REAL_FINANCE_CHANNELS_FAIL_CLOSED=PASS');
}

function testProductionWiringContract(){
  const api=readFileSync('src/services/specialCreditApi.ts','utf8');
  const boundary=readFileSync('src/services/specialCreditRequestBoundary.ts','utf8');
  const ui=readFileSync('src/components/SpecialCreditView.tsx','utf8');
  const backend=readFileSync('backend/app/routers/special_credit.py','utf8');
  assert.match(api,/requestSpecialCredit<T>/);
  assert.match(api,/assertSandboxCreditCapabilities/);
  assert.match(api,/invalidateSessionIfCurrent/);
  assert.match(api,/authService.getUser\(\)/);
  assert.match(ui,/authService.isSessionSnapshotCurrent\(snapshot\)/);
  assert.match(ui,/!cap.sandbox_enabled/);
  assert.match(backend,/_authorize\(tenant_id, session/);
  assert.match(backend,/FR_FINANCE_SPECIAL_CREDIT_SANDBOX/);
  assert.match(boundary,/user.tenantId.toLowerCase\(\) !== tenantId.toLowerCase\(\)/);
  assert.doesNotMatch(api,/localStorage|sessionStorage|pix\/transfer/);
  assert.doesNotMatch(boundary,/localStorage|sessionStorage|pix\/transfer/);
  console.log('M39048_ANDROID_API_WIRING=PASS');
}

await testSessionAndTenantBoundaries();
await testExpiredAndStaleSessions();
testNoRealFinanceOrExternalChannel();
testProductionWiringContract();
console.log('M39048_CLIENT_AUTH_ISOLATION=PASS_CI_OFFLINE');
