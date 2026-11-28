import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {inspectMobileBackend,interpretAuthenticationStatus} from '../services/mobileBackendDiagnostics';

assert.equal(inspectMobileBackend(false,'').kind,'WEB');
assert.equal(inspectMobileBackend(true,'').kind,'BLOCKED');
const local=inspectMobileBackend(true,'http://127.0.0.1:8000');
assert.equal(local.kind,'LOCAL_DEBUG');
assert.match(local.description,/próprio celular/);
assert.match(local.description,/OCI/);
const remote=inspectMobileBackend(true,'https://staging.frfinance.com.br');
assert.equal(remote.kind,'REMOTE_HTTPS');
for(const invalid of [
 'http://192.0.2.33:8000','http://example.com',
 'https://username:password@staging.frfinance.com.br',
 'ftp://staging.frfinance.com.br',
 'https://staging.frfinance.com.br/api/v1',
 'https://staging.frfinance.com.br?token=secret',
 'javascript:alert(1)','file:///tmp/server',
]){
 const p=inspectMobileBackend(true,invalid);
 assert.equal(p.kind,'BLOCKED',invalid);
 assert(!p.label.includes('secret')&&!p.description.includes('secret'));
}
for(const fail of [
 null,[],{}, {configured:false,requiresAuthentication:true},
 {status:'BLOCKED_PENDING_CONFIG',configured:true,requiresAuthentication:true},
 {status:'OK',configured:true,requiresAuthentication:false},
]){
 const r=interpretAuthenticationStatus(fail);
 assert(!r.includes('homologado com sucesso'));
}
assert.match(interpretAuthenticationStatus({configured:true,requiresAuthentication:true,status:'READY'}),/ainda precisam ser testados/);
const login=readFileSync('src/components/LoginView.tsx','utf8');
for(const item of [
 'getApiBaseUrl','isNativeMobilePlatform','inspectMobileBackend',
 'interpretAuthenticationStatus','authService.checkAuthStatus()',
 'Diagnóstico do servidor móvel','Verificar conexão com a API',
 'backendProfile.mobile','backendCheckBusy',
])assert(login.includes(item),item);
assert(login.includes('onClick={() => {void verifyBackend();}}'));
const ci=readFileSync('.github/workflows/validacao-atualizacao.yml','utf8');
const staging=readFileSync('.github/workflows/fr-finance-oci-staging-apk.yml','utf8');
assert(ci.includes("VITE_API_URL: http://127.0.0.1:8000"));
assert(ci.includes("FRCAIXINHA_ANDROID_LOCAL_TEST: '1'"));
assert(staging.includes("FR_FINANCE_ANDROID_RELEASE_PROFILE: '1'"));
assert(staging.includes("VITE_API_URL: \${{ inputs.api_https_url }}"));
assert(staging.includes("if grep -RlF 'http://127.0.0.1:8000' dist/assets"));
console.log('M37447_MOBILE_API_PROFILE_AND_LOGIN_DIAGNOSTIC=PASS');
