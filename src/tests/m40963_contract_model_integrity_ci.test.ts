/** M40963: verify local draft bytes against public server-pinned digests. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {contractModelsV22} from '../services/contractModelsV22';
import {fetchAndVerifyContractModelV22} from '../services/contractModelIntegrityV22';

const digest=(text:string)=>Promise.resolve(createHash('sha256').update(text,'utf8').digest('hex'));
const seen:Array<{url:string,init:RequestInit}>=[];
const makeFetch=(sha256:string):typeof fetch=>(async(input,init)=>{
  seen.push({url:String(input),init:init||{}});
  return {ok:true,status:200,json:async()=>({schema:'FR_FINANCE_CONTRACT_MODEL_MANIFEST_V22',
    version:'2.2',state:'DRAFT_ONLY',acceptance_enabled:false,kind:'SAAS_LICENSE',sha256})} as Response;
}) as typeof fetch;

const master=readFileSync('docs/FR_Finance_Caderno_Mestre_V2_2_2026-11-24.md','utf8');
const a=master.indexOf('## CONTRATO A — ');
const b=master.indexOf('## CONTRATO B — ');
const end=master.indexOf('## Matriz de responsabilidades contratuais');
assert.ok(a>=0&&a<b&&b<end);
assert.equal(contractModelsV22.SAAS_LICENSE,master.slice(a,b));
assert.equal(contractModelsV22.MEMBER_ADHESION,master.slice(b,end));

const license=contractModelsV22.SAAS_LICENSE;
const correct=await digest(license);
assert.equal(await fetchAndVerifyContractModelV22('SAAS_LICENSE',license,makeFetch(correct),digest,'https://api.example.test/'),'verified');
assert.equal(await fetchAndVerifyContractModelV22('SAAS_LICENSE',license+' ',makeFetch(correct),digest,'https://api.example.test'),'mismatch');
assert.equal(await fetchAndVerifyContractModelV22('SAAS_LICENSE',license,makeFetch(correct.toUpperCase()),digest,'https://api.example.test'),'unavailable');
assert.equal(await fetchAndVerifyContractModelV22('SAAS_LICENSE',license,async()=>{throw Error('offline')},digest,'https://api.example.test'),'unavailable');
assert.equal(seen[0].url,'https://api.example.test/api/v1/public/contract-models/v2.2/SAAS_LICENSE');
assert.equal(seen[0].init.method,'GET');
assert.equal(seen[0].init.credentials,'omit');
assert.equal(seen[0].init.cache,'no-store');
assert.equal(seen[0].init.redirect,'error');
assert.doesNotMatch(JSON.stringify(seen[0].init),/Authorization|Cookie|acceptance/i);

const login=readFileSync('src/components/LoginView.tsx','utf8');
const panel=readFileSync('src/components/ContractReviewPanel.tsx','utf8');
const component=readFileSync('src/components/ContractModelPreviewV22.tsx','utf8');
assert.match(login,/<ContractModelPreviewV22 kind="SAAS_LICENSE"/);
assert.match(panel,/scope && <ContractModelPreviewV22 kind=\{memberInvite\?'MEMBER_ADHESION':'SAAS_LICENSE'\}/);
assert.match(component,/fetchAndVerifyContractModelV22/);
assert.match(component,/Divergência de integridade/);
assert.doesNotMatch(component,/localStorage|sessionStorage|dangerouslySetInnerHTML|onSubmit|recordAcceptance/);
console.log('M40963_V22_MODEL_DIGEST_BINDING_AND_FAIL_CLOSED_UI=PASS');
