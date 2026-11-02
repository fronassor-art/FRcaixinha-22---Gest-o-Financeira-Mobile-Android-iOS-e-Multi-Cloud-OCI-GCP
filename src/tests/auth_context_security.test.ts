import assert from 'node:assert/strict';
import { authService, parseServerContexts, contextLabel } from '../services/authService';

const A='123e4567-e89b-42d3-a456-426614174000';
const B='423e4567-e89b-42d3-a456-426614174001';
const USER='723e4567-e89b-42d3-a456-426614174002';
const SID1='823e4567-e89b-42d3-a456-426614174003';
const SID2='923e4567-e89b-42d3-a456-426614174004';
const rawContexts=[
  {role:'MASTER',tenant_id:null,tenant_name:null},
  {role:'TENANT_ADMIN',tenant_id:A,tenant_name:'Caixinha Pará'},
  {role:'TENANT_MEMBER',tenant_id:A,tenant_name:'Caixinha Pará'},
  {role:'TENANT_MEMBER',tenant_id:B,tenant_name:'Caixinha Maranhão'},
];

const fakeWindow={
  setTimeout:() => 1,
  clearTimeout:() => undefined,
  dispatchEvent:() => true,
};
(globalThis as any).window=fakeWindow;
(globalThis as any).CustomEvent=class {
  constructor(public name:string) {}
};
const oldFetch=globalThis.fetch;
function response(body:unknown,status=200):Response {
  return new Response(JSON.stringify(body),{
    status,
    headers:{'content-type':'application/json'},
  });
}
const initialUser={id:USER,name:'Pessoa CI',email:'ci@example.com',
                   role:'TENANT_MEMBER',tenant_id:A};

async function main(){
  assert.equal(parseServerContexts(rawContexts).length,4);
  assert.match(contextLabel(rawContexts[3] as any),/Membro.*Caixinha Maranhão/);
  assert.equal(contextLabel(rawContexts[0] as any),'Administrador Master — Plataforma');
  for (const invalid of [
    [{role:'MASTER',tenant_id:A}],
    [{role:'MASTER',tenant_id:null,tenant_name:'Caixinha proibida'}],
    [{role:'TENANT_MEMBER',tenant_id:A,tenant_name:''}],
    [{role:'TENANT_MEMBER',tenant_id:null}],
    [{role:'TENANT_MEMBER',tenant_id:'nao-uuid'}],
    [{role:'OUTRO',tenant_id:A}],
    [{role:'TENANT_MEMBER',tenant_id:A},{role:'TENANT_MEMBER',tenant_id:A}],
    {contexts:rawContexts},
  ]) assert.throws(() => parseServerContexts(invalid));

  let responseContext='TENANT_MEMBER';
  let responseTenant=A;
  let activeUserId=USER;
  let routeCalls:string[]=[];
  let pendingMe:((v:Response)=>void)|null=null;
  let pendingContext:((v:Response)=>void)|null=null;
  let revokedIds=new Set<string>();
  globalThis.fetch=(async (path:any, opts?:RequestInit) => {
    const route=String(path);
    routeCalls.push(route);
    if (route.endsWith('/login')) return response({
      token:'ci-token-not-real', user:initialUser,
      expires_at:new Date(Date.now()+900_000).toISOString(),
    });
    if (route.endsWith('/contexts')) return response(rawContexts);
    if (route.endsWith('/sessions'))return response({
      source:'POSTGRESQL_AUTH',
      sessions:[SID1,SID2].filter(id=>!revokedIds.has(id)).map(id=>({
        id,role:id===SID1?'TENANT_MEMBER':'TENANT_ADMIN',
        tenant_id:id===SID1?A:B,
        created_at:new Date(Date.now()-30_000).toISOString(),
        expires_at:new Date(Date.now()+900_000).toISOString(),
        current:id===SID1,
      })),
    });
    if (route.endsWith('/revoke')) {
      const sid=route.split('/').at(-2);
      if(!sid || (sid!==SID1 && sid!==SID2))return response({detail:'Not found'},404);
      revokedIds.add(sid);
      return response({success:true,session_id:sid,current_revoked:sid===SID1});
    }
    if (route.endsWith('/switch-context')){
      const payload=JSON.parse(String(opts?.body));
      responseContext=payload.target_role;
      responseTenant=payload.target_tenant_id;
      return response({ ...initialUser,id:activeUserId,role:responseContext,
                        tenant_id:responseTenant});
    }
    if (route.endsWith('/me')) {
      if(pendingMe)return new Promise<Response>(resolve=>pendingMe=resolve);
      return response({...initialUser,role:responseContext,
                       tenant_id:responseTenant});
    }
    if (route.endsWith('/forgot-password'))return response({
      detail:'Recuperação por e-mail ainda não implementada.',
    },503);
    if (route.endsWith('/logout')) return response({success:true});
    throw new Error('Unexpected endpoint '+route);
  }) as typeof fetch;
  try {
    await authService.login('ci@example.com','senha-de-testes-ci');
    assert(authService.isAuthenticated());
    const expiry=authService.getExpiresAt()!;
    assert.equal((await authService.listContexts()).length,4);
    assert.equal((await authService.listSessions()).length,2);
    await assert.rejects(authService.revokeSession('not-an-id'),/inválido/);
    assert.equal(await authService.revokeSession(SID2),false);
    assert.equal((await authService.listSessions()).length,1);
    assert.equal((await authService.switchContext({
      role:'TENANT_MEMBER',tenant_id:B,
    })).tenantId,B);
    assert.equal(authService.getUser()?.id,USER);
    assert.equal((await authService.switchContext({
      role:'TENANT_ADMIN',tenant_id:A,
    })).role,'TENANT_ADMIN');
    await authService.checkCurrentUser();
    assert.equal(authService.getExpiresAt(),expiry,
      'Consultar /me não pode ampliar validade da sessão no cliente');

    await assert.rejects(
      authService.requestPasswordReset('ci@example.com'),
      /Recuperação por e-mail ainda não implementada/
    );
    assert(routeCalls.includes('/api/v1/auth/forgot-password'),
      'Rota de recuperação precisa coincidir com FastAPI');

    activeUserId='another-person';
    await assert.rejects(authService.switchContext({
      role:'TENANT_MEMBER',tenant_id:A,
    }),/incompatível/);
    assert.equal(authService.getUser(),null,
      'Resposta incompatível deve encerrar sessão local');

    activeUserId=USER;
    await authService.login('ci@example.com','senha-de-testes-ci');
    pendingMe=(_v:Response)=>{}; // ativa espera artificial
    const oldRequest=authService.checkCurrentUser();
    await authService.logout();
    (pendingMe as (v:Response)=>void)(response({...initialUser,role:'MASTER',tenant_id:null}));
    assert.equal(await oldRequest,null,'Resposta /me antiga não pode reabrir sessão');
    assert.equal(authService.getUser(),null);
    pendingMe=null;

    await authService.login('ci@example.com','senha-de-testes-ci');
    // Dados antigos de contextos não podem aparecer após logout
    let resolveContexts:(value:Response)=>void=()=>{};
    const regularMockFetch=globalThis.fetch;
    globalThis.fetch=(async (path:any,opts?:RequestInit)=>{
      const route=String(path);
      if(route.endsWith('/contexts'))return new Promise<Response>(r=>{resolveContexts=r;});
      if(route.endsWith('/logout'))return response({success:true});
      throw new Error('Unexpected '+route);
    }) as typeof fetch;
    const oldContexts=authService.listContexts();
    await authService.logout();
    resolveContexts(response(rawContexts));
    assert.deepEqual(await oldContexts,[]);
    assert.equal(authService.getUser(),null);

    // O logout antigo não pode encerrar um NOVO login quando sua resposta
    // chegar atrasada pela rede.
    globalThis.fetch=regularMockFetch;
    await authService.login('ci@example.com','senha-de-testes-ci');
    let completeOldLogout:(response:Response)=>void=()=>{};
    globalThis.fetch=(async (path:any,opts?:RequestInit)=>{
      if(String(path).endsWith('/logout'))return new Promise<Response>(resolve=>{
        completeOldLogout=resolve;
      });
      return regularMockFetch(path,opts);
    }) as typeof fetch;
    const slowLogout=authService.logout();
    assert.equal(authService.getUser(),null,'Logout encerra contexto imediatamente');
    await authService.login('ci@example.com','senha-de-testes-ci');
    completeOldLogout(response({success:true}));
    await slowLogout;
    assert.equal(authService.getUser()?.id,USER,
      'Resposta do logout anterior não pode apagar uma sessão nova');
    assert.equal(await authService.revokeSession(SID1),true,
      'Revogação da sessão atual precisa encerrar o login local');
    assert.equal(authService.getUser(),null);
    globalThis.fetch=regularMockFetch;
    console.log('PASS: identidade única, troca de perfil, recuperação, sessão e concorrência');
  } finally {
    await authService.logout();
    globalThis.fetch=oldFetch;
  }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
