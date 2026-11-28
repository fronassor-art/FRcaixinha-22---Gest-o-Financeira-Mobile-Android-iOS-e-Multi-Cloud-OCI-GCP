/** M25400 — canonical UTF-8 integrity on client; no user consent. */
import assert from 'node:assert/strict';
import {createHash, webcrypto} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {parseCanonicalContractBody} from '../services/invitationContractReview';

const subtle = globalThis.crypto?.subtle ?? webcrypto.subtle;
assert.ok(subtle, 'Secure SHA-256 hashing is mandatory');
const body='Contrato aprovado — somente dados sintéticos.\n';
const digest=createHash('sha256').update(Buffer.from(body,'utf8')).digest('hex');
const doc='00000000-0000-4000-8000-000000000002';
const raw={
  source:'PUBLISHED_CONTRACT_VERIFIED',
  scope:'AI_STUDIO_CANONICAL_CONTRACT_BODY',
  document_id:doc,version:'2026.11',sha256:digest,
  published_at:'2026-11-07T13:00:00+00:00',
  contract_text:body,integrity_verified:true,body_available:true,
  acceptance_recorded:false,invitation_created:false,
  activation_authorized:false,writes_performed:false,
};
assert.equal((await parseCanonicalContractBody(raw,doc,digest)).contract_text,body);
for (const mutation of [
  {...raw,contract_text:body+' '},
  {...raw,contract_text:body.replace('\n','\r\n')},
  {...raw,contract_text:body.replace('aprovado','não aprovado')},
  {...raw,acceptance_recorded:true},
  {...raw,activation_authorized:true},
  {...raw,invitation_created:true},
  {...raw,integrity_verified:false},
  {...raw,body_available:false},
  {...raw,sha256:'a'.repeat(64)},
]) {
  await assert.rejects(()=>parseCanonicalContractBody(mutation,doc,digest));
}
await assert.rejects(()=>parseCanonicalContractBody(raw,doc,'a'.repeat(64)));
await assert.rejects(()=>parseCanonicalContractBody(raw,'00000000-0000-4000-8000-000000000003',digest));

const service=readFileSync('src/services/financialApiService.ts','utf8');
const panel=readFileSync('src/components/ContractReviewPanel.tsx','utf8');
const backend=readFileSync('backend/app/routers/invitations.py','utf8');
assert.match(service,/invitations\/preflight\/contract-content/);
assert.match(service,/parseCanonicalContractBody\(raw, documentId, expectedSha256\)/);
assert.match(panel,/Carregar texto canônico verificado do servidor/);
assert.match(panel,/setCanonicalVerified\(true\)/);
assert.match(panel,/sequence\.current !== request/);
assert.doesNotMatch(panel,/localStorage|sessionStorage/);
assert.doesNotMatch(panel,/recordAcceptance|createInvitation|confirmAcceptance/);
assert.match(backend,/@router\.post\("\/preflight\/contract-content"\)/);
console.log('M25400_CANONICAL_CONTRACT_CLIENT=PASS');
