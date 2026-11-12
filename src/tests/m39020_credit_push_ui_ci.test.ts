/** M39020 — client & Android push static contract; no device registration. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

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
