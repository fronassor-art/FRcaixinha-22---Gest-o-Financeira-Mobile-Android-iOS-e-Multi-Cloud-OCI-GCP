import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {allowedKinds,prepareV23,bindPolicyPreview,prepareCycleOpening,reuseAttempt,exerciseCandidate,cents,type Fields} from '../services/productTransactionalFormsV23';
import type {Scope} from '../services/productTransactionalBoundaryV23';
const id=(n:number)=>'aaaaaaaa-aaaa-4aaa-8aaa-'+String(n).padStart(12,'0');
const a:Scope={userId:id(1),tenantId:id(2),role:'TENANT_ADMIN'},m:Scope={...a,userId:id(3),role:'TENANT_MEMBER'};
const request=id(4),f:Fields={start:'2026-12-10',first_due:'2026-12-10',last_due:'2027-11-10',closing:'2027-12-20',quota:'50,01',admin_pct:'13,25',late_days:'75',late_competences:'2',mode:'HYBRID',document_id:id(5),cycle_id:id(6),policy_hash:'b'.repeat(64),joined:'2027-01-10',quotas:'2',membership_id:id(7),contribution_id:id(8),amount:'10,50',method:'PIX_EXTERNO',occurred:'2027-01-10',reference:'CI-ref',evidence_ref:'CI-evidence',receipt_id:id(9),reason:'CI reserva gerencial',related_hold:id(10)};
assert.equal(cents('0,01'),1);for(const v of ['0','-1','1,234','1e2','NaN',' 1'])assert.throws(()=>cents(v));
assert.deepEqual(allowedKinds(m),['CONSENT','CONTEST']);
assert.throws(()=>prepareV23(m,'POLICY',f,request,true));
assert.throws(()=>prepareV23(a,'CONTEST',f,request,true));
assert.throws(()=>prepareV23(a,'POLICY',f,request,false));
assert.throws(()=>prepareV23(a,'POLICY',{...f,last_due:'2027-11-09'},request,true));
const p=prepareV23(a,'POLICY',f,request,true);
assert.equal(p.body.quota_cents,5001);assert.equal(p.body.admin_bps,1325);
const proof=bindPolicyPreview(p,{policy_hash:'a'.repeat(64)});
assert.throws(()=>prepareCycleOpening(p,proof,false));
assert.throws(()=>prepareCycleOpening(prepareV23(a,'POLICY',{...f,quota:'55'},request,true),proof,true));
const opened=prepareCycleOpening(p,proof,true);assert.equal(opened.path,'/cycles');assert.equal(opened.body.accepted,true);
assert.equal(reuseAttempt(p,prepareV23(a,'POLICY',f,id(11),true)),p);
assert.throws(()=>reuseAttempt(p,prepareV23(a,'POLICY',{...f,quota:'55'},id(11),true)));
let calls=0;
await assert.rejects(exerciseCandidate(p,m,async()=>{calls++;return {}; }));assert.equal(calls,0);
const preview=await exerciseCandidate(p,a,async(path,body)=>{assert.equal(path,'/policies/preview');assert.deepEqual(body,p.body);return {policy_hash:'a'.repeat(64)};});
assert.deepEqual(preview,proof);
for(const [kind,scope,path,result] of [
 ['CONSENT',m,'/cycles/'+f.cycle_id+'/policy-acceptance',{consent_id:id(20)}],
 ['ADMIT',a,'/cycles/'+f.cycle_id+'/admissions',{obligations:11}],
 ['RECEIPT',a,'/manual-receipts',{receipt_id:id(20)}],
 ['CONFIRM',a,'/manual-receipts/'+f.receipt_id+'/CONFIRM',{state:'CONFIRMED'}],
 ['REVERSE',a,'/manual-receipts/'+f.receipt_id+'/REVERSE',{state:'REVERSED'}],
 ['CONTEST',m,'/manual-receipts/'+f.receipt_id+'/CONTEST',{state:'CONTESTED'}],
 ['HOLD',a,'/cycles/'+f.cycle_id+'/reserves',{event_id:id(20)}],
 ['RELEASE',a,'/cycles/'+f.cycle_id+'/reserves',{event_id:id(20)}],
] as const){
 const q=prepareV23(scope,kind,f,request,true);
 await exerciseCandidate(q,scope,async(p,b)=>{assert.equal(p,path);assert.deepEqual(b,q.body);return result;});
 await assert.rejects(exerciseCandidate(q,scope,async()=>({success:true})));
}
await exerciseCandidate(opened,a,async(path)=>{assert.equal(path,'/cycles');return {cycle_id:id(20)};});
const ui=readFileSync('src/components/ProductTransactionalFormsV23.tsx','utf8');
assert.match(ui,/api.capabilities\(scope\)/);assert.doesNotMatch(ui,/exerciseCandidate|fetch\(|localStorage|sessionStorage/);
console.log('M41370_V23_FORM_PREPARATION_POLICY_BINDING_ROLE_RETRY_CANDIDATE=PASS');
