import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {classifyApiOrigin} from '../services/apiOriginPolicy';
import {inspectMobileBackend} from '../services/mobileBackendDiagnostics';

for(const [input,kind,origin] of [
  ['http://127.0.0.1:8000','LOCAL_DEBUG','http://127.0.0.1:8000'],
  ['http://localhost:8000/','LOCAL_DEBUG','http://localhost:8000'],
  ['http://[::1]:8000','LOCAL_DEBUG','http://[::1]:8000'],
  ['https://staging.frfinance.com.br','REMOTE_HTTPS','https://staging.frfinance.com.br'],
  ['https://api.frfinance.com.br:8443/','REMOTE_HTTPS','https://api.frfinance.com.br:8443'],
  ['https://frfinance.com.br:443/','REMOTE_HTTPS','https://frfinance.com.br'],
] as const){
 const result=classifyApiOrigin(input);
 assert.equal(result.kind,kind,input);
 assert.equal(result.origin,origin,input);
 assert.equal(inspectMobileBackend(true,input).kind,kind,input);
}
for(const bad of [
 null,undefined,42,'',' ',' https://staging.frfinance.com.br',
 'https://staging.frfinance.com.br ',
 'https://user:pass@staging.frfinance.com.br',
 'https://user@staging.frfinance.com.br',
 'https://staging.frfinance.com.br/api/v1',
 'https://staging.frfinance.com.br/?token=secret',
 'https://staging.frfinance.com.br/#secret',
 'https://staging.frfinance.com.br\\@evil.example',
 'https://staging.frfinance.com.br\\api',
 'https://localhost:8000','https://127.0.0.1:8000',
 'http://192.0.2.12:8000','http://frfinance.com.br',
 'https://192.168.1.1','https://10.0.0.1',
 'https://internal.local','https://staging.example',
 'https://staging.invalid','https://staging.internal',
 'javascript:alert(1)','file:///etc/passwd',
 'https://staging.frfinance.com.br\nHost:evil',
]) {
 assert.equal(classifyApiOrigin(bad).kind,'BLOCKED',String(bad));
 assert.equal(classifyApiOrigin(bad).origin,'',String(bad));
 assert.equal(inspectMobileBackend(true,String(bad)).kind,'BLOCKED',String(bad));
}
const auth=readFileSync('src/services/authService.ts','utf8');
const client=readFileSync('src/services/notificationInbox.ts','utf8');
assert(auth.includes('classifyApiOrigin(declared).origin'));
assert(!auth.includes('return candidate'));
assert(client.includes('authService.isSessionSnapshotCurrent(snapshot)'));
assert(client.includes('Resposta inválida do servidor de notificações.'));
console.log('M37974-M37976: API origin and notification response guard PASS');
