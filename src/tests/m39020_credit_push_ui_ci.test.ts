/** M39020 — client & Android push static contract; no device registration. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseCreditPricePreview} from '../services/specialCreditPresentation';

const read=(path:string)=>readFileSync(path,'utf8');
const deps=JSON.parse(read('package.json'));
const lock=JSON.parse(read('package-lock.json'));
const ui=read('src/components/SpecialCreditView.tsx');
const api=read('src/services/specialCreditApi.ts');
const native=read('src/services/specialCreditPushNative.ts');
const root=read('src/components/ServerLoansView.tsx');
const gitignore=read('.gitignore');

assert.equal(deps.dependencies['@capacitor/push-notifications'],'8.1.2');
assert.equal(lock.packages[''].dependencies['@capacitor/push-notifications'],'8.1.2');
assert.equal(lock.packages['node_modules/@capacitor/push-notifications'].version,'8.1.2');
assert.ok(native.includes('Capacitor.isNativePlatform()'));
assert.ok(native.includes('Capacitor.getPlatform()'));
assert.ok(native.includes('VITE_FR_FINANCE_PUSH_DIAGNOSTIC'));
assert.ok(native.includes('PushNotifications.requestPermissions()'));
assert.ok(native.includes('PushNotifications.addListener'));
assert.ok(native.includes('PushNotifications.register()'));
assert.ok(native.includes("TOKEN_RECEIVED_NOT_STORED"));
assert.ok(!native.includes('console.log('));
assert.ok(!native.includes('localStorage.'));
assert.ok(!native.includes('sessionStorage.'));
assert.ok(!native.includes('fetch('));
assert.ok(gitignore.includes('android/app/google-services.json'));
assert.ok(ui.includes('selectedMembers') && ui.includes('selectedGrants'));
assert.ok(ui.includes('setSelectedMembers') && ui.includes('setSelectedGrants'));
assert.ok(ui.includes("setSimulation("));
assert.ok(ui.includes("'Simulação concluída sem movimento financeiro.',false"));
assert.ok(ui.includes('Minhas Oportunidades'));
assert.ok(ui.includes('Diagnosticar permissão push no Android'));
assert.ok(ui.includes('prefs.PUSH'));
assert.ok(root.includes('<SpecialCreditView state={state}/>'));
assert.ok(api.includes('authService.isSessionSnapshotCurrent(snapshot)'));
assert.ok(!api.includes('pix/transfer'));
assert.ok(!native.includes('FCM_OAUTH2_SCOPED_BEARER'));

console.log('M39020_ANDROID_PUSH_AND_CAMPAIGN_UI=PASS_CI_ONLY');


// M40953: Decimal JSON strings from FastAPI and exact financial preview checks.
const grant='11111111-1111-4111-8111-111111111111';
const simulation={principal:'1000.00',monthly_rate:'0.20',term_months:2,
  uniform_payment:'654.55',last_payment:'654.54',total_interest:'309.09',total_payable:'1309.09'};
const preview={grant_id:grant,approved:false,reserved:false,disbursed:false,simulation};
assert.equal(parseCreditPricePreview(preview,grant,'1000.00',2).simulation.total_payable,1309.09);
for(const patch of [{approved:true},{reserved:true},{disbursed:true},
  {grant_id:'22222222-2222-4222-8222-222222222222'},{approved:undefined},
  {simulation:{...simulation,term_months:3}},
  {simulation:{...simulation,principal:'999.00'}},
  {simulation:{...simulation,monthly_rate:'Infinity'}},
  {simulation:{...simulation,total_payable:'1309.10'}},
  {simulation:{...simulation,last_payment:'654.545'}},
  {simulation:{...simulation,uniform_payment:null}},
  {simulation:{...simulation,total_interest:'-1.00'}}]){
  assert.throws(()=>parseCreditPricePreview({...preview,...patch},grant,'1000.00',2));
}
assert.match(api,/parseCreditPricePreview\(await call<unknown>/);
console.log('M40953_CREDIT_SIMULATION_RESPONSE_FENCE=PASS');
