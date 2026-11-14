/* Pacote 11: revalidação em foreground com rede lenta/expiração/logout. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  createForegroundSessionGuard,ResumeAuthPort,
} from '../services/sessionResumeGuard';
import type {AuthSessionSnapshot,AuthenticatedUser} from '../services/authService';

const profile={id:'synthetic',name:'Conta CI',email:'ci@example.invalid',
 role:'MASTER' as const,tenantId:undefined};
let generation=0;
let token:string|null='test-only-1';
let calls=0;
let invalidations=0;
let resolveCurrent:(result:AuthenticatedUser|null)=>void=()=>undefined;
let rejectCurrent:(error:Error)=>void=()=>undefined;
let shouldReject=false;
const pending:boolean[]=[];
const auth:ResumeAuthPort={
 captureSession():AuthSessionSnapshot {return {token,generation};},
 checkCurrentUser():Promise<AuthenticatedUser|null>{
  calls++;
  return new Promise((resolve,reject)=>{
   resolveCurrent=resolve;
   rejectCurrent=reject;
  });
 },
 invalidateSessionIfCurrent(snapshot):boolean{
  if(snapshot.token!==token||snapshot.generation!==generation)return false;
  invalidations++;token=null;generation++;
  return true;
 },
};
const guard=createForegroundSessionGuard(auth,value=>pending.push(value));
async function main(){
 const request=guard.revalidate();
 const parallel=guard.revalidate();
 assert.equal(calls,1,'retorno e pageshow não fazem duas requisições simultâneas');
 assert.equal(request,parallel);
 assert.deepEqual(pending,[true],'dados protegidos ficam ocultos durante consulta');
 resolveCurrent(profile);
 await request;
 assert.deepEqual(pending,[true,false]);

 const slow=guard.revalidate();
 token='test-only-2';generation++;
 resolveCurrent(null);
 await slow;
 assert.equal(token,'test-only-2','consulta antiga não encerra login novo');
 assert.equal(invalidations,0);

 const error=guard.revalidate();
 rejectCurrent(new Error('Network offline CI'));
 await error;
 assert.equal(token,null,'falha da validação atual não libera acesso offline');
 assert.equal(invalidations,1);

 const callsBefore=calls;
 await guard.revalidate();
 assert.equal(calls,callsBefore,'sem token não consulta API');
 guard.dispose();
 token='test-only-3';generation++;
 await guard.revalidate();
 assert.equal(calls,callsBefore,'guard desmontado não usa rede');

 const source=readFileSync('src/App.tsx','utf8');
 assert.match(source,/document.addEventListener\('visibilitychange', onVisible\)/);
 assert.match(source,/window.addEventListener\('pageshow', onPageShow\)/);
 assert.match(source,/event.persisted/);
 assert.match(source,/resumeValidationPending && \(/);
 assert.match(source,/aria-hidden=\{resumeValidationPending\}/);
 assert.match(source,/inert=\{resumeValidationPending\}/);
 assert.doesNotMatch(source,/if \(resumeValidationPending\)\s*\{\s*return\s*\(/,
   'foreground não pode desmontar o formulário em edição');
 assert.match(source,/role="status"/);
 assert.match(source,/else if \(!authService.getUser\(\)\)/);
 assert.match(source,/const bootstrap = authService.captureSession\(\)/);
 assert.match(source,/resumeGuard.dispose\(\)/);

 // Mudança de perfil durante a checagem de inicialização não pode
 // apagar um usuário já autenticado; o bloco de App precisa ter gate.
 const boot=source.slice(source.indexOf('const bootstrap = authService.captureSession()'),
   source.indexOf('const unsubscribeAuth = authService.subscribe'));
 assert(boot.includes('authService.isSessionSnapshotCurrent(bootstrap)'));
 assert(!boot.includes('else {\n        setAuthenticatedUser(null)'));

 console.log('PACOTE_11_REVALIDACAO_FOREGROUND_CI=PASS');
}
main().catch(err=>{console.error(err);process.exitCode=1;});
