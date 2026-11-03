/* Pacote 7: requisicoes tardias, expiracao, revogacao e rede sem dados falsos. */
import assert from 'node:assert/strict';
import {authService} from '../services/authService';
import {
  financialApi, FinancialBackendUnavailableError, SessionBoundaryError
} from '../services/financialApiService';

const TENANT='00000000-0000-4000-8000-000000000001';
const USER='00000000-0000-4000-8000-000000000002';
const SID='00000000-0000-4000-8000-000000000003';
const nativeWindow={
  setTimeout:(_:unknown,_delay:unknown)=>1,
  clearTimeout:(_:unknown)=>undefined,
  dispatchEvent:(_:unknown)=>true,
};
(globalThis as any).window=nativeWindow;
(globalThis as any).CustomEvent=class {constructor(public type:string) {}};
const originalFetch=globalThis.fetch;
const reply=(body:unknown,status=200)=>new Response(JSON.stringify(body),{
  status,headers:{'Content-Type':'application/json'},
});
const user={id:USER,name:'CI',email:'ci@example.invalid',
  role:'TENANT_ADMIN',tenant_id:TENANT};
const dashboard={source:'POSTGRESQL_RLS',tenant_id:TENANT,role:'TENANT_ADMIN',
  quota_count_visible:0,contribution_count_visible:0,
  loan_count_visible:0,financial_operations:'DISABLED'};
let logins=0;
let mode:'pending'|'ok'|'401'|'403'|'503'|'network'='ok';
let resolvePending:(response:Response)=>void=()=>undefined;
let resolveRevoke:(response:Response)=>void=()=>undefined;
let pendingRevoke=false;
const calls:string[]=[];
globalThis.fetch=(async (url:any,_opts?:RequestInit)=>{
  const path=String(url);
  calls.push(path);
  if(path.endsWith('/login'))return reply({
    token:'CI-only-session-'+(++logins),user,
    expires_at:new Date(Date.now()+900000).toISOString(),
  });
  if(path.endsWith('/logout'))return reply({success:true});
  if(path.endsWith('/me'))return reply(user);
  if(path.endsWith('/dashboard')){
    if(mode==='pending')return new Promise<Response>(resolve=>{resolvePending=resolve;});
    if(mode==='network')throw new TypeError('Network offline CI');
    if(mode==='401')return reply({detail:'revogada'},401);
    if(mode==='403')return reply({detail:'sem acesso'},403);
    if(mode==='503')return reply({detail:'backend indisponível'},503);
    return reply(dashboard);
  }
  if(path.endsWith('/loans/request')){
    if(mode==='network')throw new TypeError('Network offline CI');
    return reply({status:'DISABLED'});
  }
  if(path.endsWith('/revoke')){
    if(pendingRevoke)return new Promise<Response>(resolve=>{resolveRevoke=resolve;});
    return reply({success:true,session_id:SID,current_revoked:true});
  }
  if(path.endsWith('/sessions'))return reply({source:'POSTGRESQL_AUTH',sessions:[]});
  throw Error('Unexpected fake route: '+path);
}) as typeof fetch;

const login=async()=>authService.login('ci@example.invalid','only-ci','TENANT_ADMIN');
const dashboardCall=()=>financialApi.fetchTenantOverview(TENANT);
async function main(){
  try{
    await login();
    const first=authService.captureSession();
    assert(first.token&&authService.isSessionSnapshotCurrent(first));
    mode='pending';
    const old401=dashboardCall();
    await authService.logout();
    await login();
    const newer=authService.captureSession();
    assert.notEqual(newer.token,first.token);
    resolvePending(reply({detail:'old unauthorized'},401));
    await assert.rejects(old401,(err:any)=>
      err instanceof SessionBoundaryError &&
      err.code==='SESSION_CHANGED_DURING_REQUEST');
    assert(authService.isSessionSnapshotCurrent(newer),
      '401 do usuário antigo jamais derruba a sessão nova');

    mode='pending';
    const oldSuccess=dashboardCall();
    await authService.logout();
    await login();
    resolvePending(reply({...dashboard,tenant_id:'TENANT_ANTERIOR'}));
    await assert.rejects(oldSuccess,(err:any)=>
      err instanceof SessionBoundaryError &&
      err.code==='SESSION_CHANGED_DURING_REQUEST');

    mode='403';
    await assert.rejects(dashboardCall(),/sem acesso/);
    assert(authService.isAuthenticated(),'403 não revoga sessão atual');

    mode='503';
    const before503=calls.length;
    await assert.rejects(dashboardCall(),(err:any)=>
      err instanceof FinancialBackendUnavailableError);
    assert.equal(calls.length,before503+1,'503 não causa retry automático');
    assert(authService.isAuthenticated(),'503 não inventa revogação');

    mode='network';
    const beforeOffline=calls.length;
    await assert.rejects(dashboardCall(),(err:any)=>
      err instanceof FinancialBackendUnavailableError &&
      err.code==='NETWORK_CONNECTION_FAILED');
    assert.equal(calls.length,beforeOffline+1,'GET não faz retry automático');
    const beforeWrite=calls.length;
    await assert.rejects(financialApi.requestLoan(TENANT,{
      principal:100,term_months:1,
    }),FinancialBackendUnavailableError);
    assert.equal(calls.length,beforeWrite+1,
      'POST financeiro não pode ser repetido automaticamente');

    mode='ok';
    assert.equal((await dashboardCall()).source,'POSTGRESQL_RLS');
    mode='401';
    await assert.rejects(dashboardCall(),(err:any)=>
      err instanceof SessionBoundaryError && err.code==='SESSION_REQUIRED');
    assert.equal(authService.getToken(),null,'401 atual encerra sessão');

    await assert.rejects(dashboardCall(),(err:any)=>
      err instanceof SessionBoundaryError && err.code==='SESSION_REQUIRED');
    await login();

    // Resposta de revogação de uma sessão antiga não pode finalizar novo login.
    pendingRevoke=true;
    const lateRevoke=authService.revokeSession(SID);
    await authService.logout();
    await login();
    resolveRevoke(reply({success:true,session_id:SID,current_revoked:true}));
    await assert.rejects(lateRevoke,/Sessão alterada durante revogação/);
    assert(authService.isAuthenticated(),'revogação anterior não afeta login novo');

    // /me malformado: fail closed sem continuar com token armazenado.
    const currentFetch=globalThis.fetch;
    globalThis.fetch=(async(url:any,opts?:RequestInit)=>{
      if(String(url).endsWith('/me'))return reply({unexpected:'malformed'});
      return currentFetch(url,opts);
    }) as typeof fetch;
    assert.equal(await authService.checkCurrentUser(),null);
    assert.equal(authService.getToken(),null,
      '/me sem identidade confirmada não mantém sessão local');
    globalThis.fetch=currentFetch;
    console.log('PACOTE_7_SESSOES_RESILIENCIA_FRONTEND=PASS');
  }finally{
    await authService.logout();
    globalThis.fetch=originalFetch;
  }
}
main().catch(err=>{console.error(err);process.exitCode=1;});
