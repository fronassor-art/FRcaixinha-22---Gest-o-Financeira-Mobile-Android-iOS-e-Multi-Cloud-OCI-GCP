import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {probeMobileBackendHealth} from '../services/mobileBackendProbe';

const health={status:'ONLINE',app:'FR Finance',framework:'FastAPI (Python)',
  database_configured:true,environment:'sandbox-development'};
type Mode='ok'|'offline'|'html'|'huge'|'wrong'|'503'|'invalid';
const make=(payload:unknown=health,status=200,contentType='application/json')=>
  new Response(typeof payload==='string'?payload:JSON.stringify(payload),{
    status,headers:{'content-type':contentType},
  });
async function probe(mode:Mode, native=true, base='https://staging.frfinance.com.br'){
  const calls:{url:string,options:RequestInit}[]=[];
  const request=(async(url:RequestInfo|URL,options?:RequestInit)=>{
    calls.push({url:String(url),options:options||{}});
    if(mode==='offline')throw new TypeError('offline test secret');
    if(mode==='html')return make('<html>oops</html>',200,'text/html');
    if(mode==='huge')return make('x'.repeat(2300));
    if(mode==='wrong')return make({...health,app:'OTHER'});
    if(mode==='503')return make({detail:'offline'},503);
    if(mode==='invalid')return make('{ invalid json ');
    return make(health);
  }) as typeof fetch;
  const result=await probeMobileBackendHealth(native,base,request);
  return {result,calls};
}
async function main(){
  for(const bad of [
    'https://api.frfinance.com.br/path',
    'https://user:pw@api.frfinance.com.br',
    'http://api.frfinance.com.br','https://localhost:8000','',
  ]) {
    const check=await probe('ok',true,bad);
    assert.equal(check.result.code,'URL_BLOCKED');
    assert.equal(check.calls.length,0,'URL bloqueada não pode fazer rede');
    assert(!check.result.message.includes('pw'));
  }
  const success=await probe('ok');
  assert.equal(success.result.code,'BACKEND_WITH_DB_DECLARED');
  assert.equal(success.result.databaseConfigured,true);
  assert.equal(success.calls.length,1);
  assert.equal(success.calls[0].url,'https://staging.frfinance.com.br/api/health');
  assert.equal(success.calls[0].options.credentials,'omit');
  assert.equal(success.calls[0].options.cache,'no-store');
  assert.equal(success.calls[0].options.redirect,'error');
  assert.equal(success.calls[0].options.method,'GET');
  assert(!JSON.stringify(success.calls[0].options).includes('Authorization'));
  const local=await probe('ok',true,'http://127.0.0.1:8000');
  assert.equal(local.result.code,'BACKEND_WITH_DB_DECLARED');
  const web=await probe('ok',false,'');
  assert.equal(web.calls[0].url,'/api/health');
  for(const [mode,expected] of [
    ['offline','NETWORK_ERROR'],['html','INVALID_RESPONSE'],
    ['huge','INVALID_RESPONSE'],['wrong','INVALID_RESPONSE'],
    ['503','HTTP_ERROR'],['invalid','INVALID_RESPONSE'],
  ] as const){
    const p=await probe(mode);
    assert.equal(p.result.code,expected,mode);
    assert.equal(p.result.ok,false);
  }
  const noDb=(async()=>make({...health,database_configured:false})) as typeof fetch;
  const noDbResult=await probeMobileBackendHealth(true,'https://staging.frfinance.com.br',noDb);
  assert.equal(noDbResult.code,'BACKEND_ONLY');
  assert.equal(noDbResult.databaseConfigured,false);
  assert.match(noDbResult.message,/não configurado/);
  for(const malformed of [
    {...health,database_configured:'true'},
    {...health,database_configured:null},
    {...health,status:'READY'},
    {...health,framework:'Express'},
    {...health,app:'FR Caixinha 2.2'},
  ]){
    const result=await probeMobileBackendHealth(true,
      'https://staging.frfinance.com.br',(async()=>make(malformed)) as typeof fetch);
    assert.equal(result.code,'INVALID_RESPONSE');
  }
  const login=readFileSync('src/components/LoginView.tsx','utf8');
  const main=readFileSync('backend/app/main.py','utf8');
  assert(login.includes('probeMobileBackendHealth(isNativeMobilePlatform(),getApiBaseUrl())'));
  assert(login.includes('authService.checkAuthStatus()'));
  assert(main.includes('if request.url.path.startswith(("/api/v1/", "/api/health")):'));
  console.log('M37980-M37986 public health probe and fail-closed Android UI PASS');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
