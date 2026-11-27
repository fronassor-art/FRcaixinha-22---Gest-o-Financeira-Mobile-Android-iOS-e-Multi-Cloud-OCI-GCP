import assert from 'node:assert/strict';
import {parseOnboardingGate,readOnboardingGate,onboardingSteps} from '../services/onboardingBoundaryV23';
const payload={contract:'FR_FINANCE_V23_ONBOARDING_V1',available:false,invites_enabled:false,registration_enabled:false,checkout_enabled:false,contract_acceptance_enabled:false,real_payments_enabled:false,production_authorized:false};
assert.equal(parseOnboardingGate(payload),'BLOCKED');
for(const key of Object.keys(payload).filter(k=>k!=='contract')){
 assert.throws(()=>parseOnboardingGate({...payload,[key]:true}));
 assert.throws(()=>parseOnboardingGate({...payload,[key]:'false'}));
}
assert.throws(()=>parseOnboardingGate({...payload,extra:'unexpected'}));
assert.throws(()=>parseOnboardingGate(null));
let sends=0;
const send=async(url:string,options:RequestInit)=>{
 sends++;assert.equal(url,'https://api.frfinance.com.br/api/v1/v23/onboarding/capabilities');
 assert.equal(options.method,'GET');assert.equal(options.redirect,'error');
 assert.equal(options.credentials,'omit');assert.equal(options.cache,'no-store');
 assert.equal(new Headers(options.headers).has('authorization'),false);
 assert.equal(options.body,undefined);return Response.json(payload);
};
assert.equal(await readOnboardingGate('https://api.frfinance.com.br',send),'BLOCKED');
await assert.rejects(readOnboardingGate('http://example.com',send));assert.equal(sends,1);
await assert.rejects(readOnboardingGate('https://api.frfinance.com.br',async()=>new Response('',{status:503})));
await assert.rejects(readOnboardingGate('https://api.frfinance.com.br',async()=>Response.json({...payload,available:true})));
assert.ok(onboardingSteps.TENANT_ADMIN[1].includes('conciliado'));
assert.equal(onboardingSteps.MASTER.length,2);
console.log('M41420_ONBOARDING_MOBILE_CAPABILITY_FAIL_CLOSED=PASS');
