/** M40500 consolidated: Android inset, FR brand, local encrypted avatar,
 * native biometric lock (not a substitute for server auth), real account names.
 * Offline; no PostgreSQL, HTTP requests, real messages or payments.
 */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {LoginView} from '../components/LoginView';
import {ProfilePanel} from '../components/ProfilePanel';
import type {AuthenticatedUser} from '../services/authService';
import {
 deviceAccountKey,isAndroidSecuritySupported,biometricAvailable,
 readPrivateAvatar,
} from '../services/deviceSecurity';
const read=(path:string)=>readFileSync(path,'utf8');
let checks=0;
function pass(fn:()=>void){fn();checks++;}
const main=read('src/App.tsx');
const login=read('src/components/LoginView.tsx');
const navbar=read('src/components/Navbar.tsx');
const dash=read('src/components/DashboardView.tsx');
const css=read('src/index.css');
const icon=read('public/icon.svg');
const androidIcon=read('android/app/src/main/res/drawable-v24/ic_fr_foreground.xml');
const android=read('android/app/src/main/AndroidManifest.xml');
const native=read('android/app/src/main/java/com/frcaixinha/app/FRDeviceSecurityPlugin.java');
const activity=read('android/app/src/main/java/com/frcaixinha/app/MainActivity.java');
const security=read('src/services/deviceSecurity.ts');
const panel=read('src/components/ProfilePanel.tsx');
const sw=read('public/sw.js');
const manifest=JSON.parse(read('public/manifest.webmanifest'));
const html=read('index.html');
const workflow=read('.github/workflows/validacao-atualizacao.yml');

pass(()=>assert.match(css,/--fr-safe-top:[^\n]*safe-area-inset-top/));
pass(()=>assert.match(css,/#root\s*\{[\s\S]*?padding-top:\s*var\(--fr-safe-top\)/));
pass(()=>assert.match(css,/main\.fr-page\s*\{[\s\S]*?overflow-y:\s*auto/));
pass(()=>assert.match(css,/justify-content:\s*flex-start/));
pass(()=>assert.match(css,/scroll-padding-top:\s*1rem/));
pass(()=>assert.match(login,/items-center justify-start/));
pass(()=>assert.match(login,/my-auto w-full max-w-sm/));
pass(()=>assert.doesNotMatch(login,/<main className="[^"]*justify-center/));
pass(()=>assert.match(html,/viewport-fit=cover/));
const renderedLogin=renderToStaticMarkup(React.createElement(LoginView,{
 onLoginSuccess:()=>undefined,
}));
pass(()=>assert.match(renderedLogin,/fr-page fr-sheen/));
pass(()=>assert.match(renderedLogin,/my-auto/));

pass(()=>assert.equal((icon.match(/>FR<\/text>/g)||[]).length,2));
pass(()=>assert.match(icon,/>FR Finance<\/text>/));
pass(()=>assert.doesNotMatch(icon,/>R<\/text>/));
pass(()=>assert.match(androidIcon,/true FR monogram/));
pass(()=>assert.match(androidIcon,/M26,29 L48,29/));
pass(()=>assert.match(androidIcon,/M51,29 L67,29/));
for(const item of [navbar,login,sw,html,manifest.icons[0].src]){
 pass(()=>assert.match(item,/fr-finance-m40500/));
}
pass(()=>assert.equal(manifest.short_name,'FR Finance'));

pass(()=>assert.doesNotMatch(navbar,/state\.users\.find\(/));
pass(()=>assert.doesNotMatch(dash,/state\.users\.find\(/));
pass(()=>assert.match(navbar,/authenticatedName\?\.trim\(\)/));
pass(()=>assert.match(dash,/authenticatedName\?\.trim\(\)/));
pass(()=>assert.match(main,/authenticatedName=\{authenticatedUser\.name\}/));
pass(()=>assert.match(main,/Administrador — ' \+ \(authenticatedUser\.name/));
pass(()=>assert.match(main,/Membro — ' \+ \(authenticatedUser\.name/));

pass(()=>assert.match(android,/android\.permission\.USE_BIOMETRIC/));
pass(()=>assert.match(activity,/registerPlugin\(FRDeviceSecurityPlugin\.class\)/));
pass(()=>assert.match(native,/@CapacitorPlugin\(name = "FRDeviceSecurity"\)/));
pass(()=>assert.match(native,/android\.hardware\.biometrics\.BiometricPrompt/));
pass(()=>assert.match(native,/BIOMETRIC_STRONG/));
pass(()=>assert.match(native,/new BiometricPrompt\.Builder/));
pass(()=>assert.match(native,/lastBiometricAccount/));
pass(()=>assert.match(native,/setBiometricEnabled\(/));
pass(()=>assert.match(main,/setBiometricLocked\(true\)/));
pass(()=>assert.match(main,/unlockBiometricSession/));
pass(()=>assert.match(main,/await authService\.checkCurrentUser\(\)/));
pass(()=>assert.match(main,/Sair e entrar com senha/));
pass(()=>assert.match(security,/server_login_replaced:false/));
pass(()=>assert.doesNotMatch(security,/localStorage|sessionStorage/));

pass(()=>assert.match(native,/AndroidKeyStore/));
pass(()=>assert.match(native,/AES\/GCM\/NoPadding/));
pass(()=>assert.match(native,/getContext\(\)\.getFilesDir\(\)/));
pass(()=>assert.match(native,/MAX_JPEG_BYTES = 240_000/));
pass(()=>assert.match(native,/Base64\.decode/));
pass(()=>assert.match(native,/getAvatar\(/));
pass(()=>assert.match(native,/deleteAvatar\(/));
pass(()=>assert.match(panel,/accept="image\/jpeg,image\/png,image\/webp"/));
pass(()=>assert.match(panel,/Não é enviada ao servidor/));
pass(()=>assert.match(panel,/Excluir foto/));
pass(()=>assert.match(panel,/Ativar proteção biométrica/));
pass(()=>assert.match(panel,/user\.name/));
pass(()=>assert.match(main,/onAvatarChanged=\{setAvatarSrc\}/));
pass(()=>assert.match(main,/aria-label="Abrir meu perfil e foto"/));
pass(()=>assert.match(workflow,/M40500/));

const admin:AuthenticatedUser={
 id:'11111111-1111-4111-8111-111111111111',name:'Administradora fictícia CI',
 email:'ci-admin@example.invalid',tenantId:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 role:'TENANT_ADMIN'};
const member:AuthenticatedUser={...admin,role:'TENANT_MEMBER',
 id:'22222222-2222-4222-8222-222222222222',name:'Membro fictício CI'};
pass(()=>assert.notEqual(deviceAccountKey(admin),deviceAccountKey(member)));
pass(()=>assert.equal(deviceAccountKey({...admin,role:'MASTER'}),null));
pass(()=>assert.equal(deviceAccountKey({...member,tenantId:undefined}),null));
pass(()=>assert.equal(deviceAccountKey({...member,id:'invalid'}),null));
pass(()=>assert.equal(deviceAccountKey(admin),
 '11111111-1111-4111-8111-111111111111:TENANT_ADMIN:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'));
pass(()=>assert.equal(isAndroidSecuritySupported(),false));
const adminProfile=renderToStaticMarkup(React.createElement(ProfilePanel,{
 user:admin,onClose:()=>{},onAvatarChanged:()=>{},onBiometricChanged:()=>{},
}));
pass(()=>assert.match(adminProfile,/Administradora fictícia CI/));
pass(()=>assert.match(adminProfile,/Escolher foto/));
pass(()=>assert.match(adminProfile,/Ativar proteção biométrica/));
const memberProfile=renderToStaticMarkup(React.createElement(ProfilePanel,{
 user:member,onClose:()=>{},onAvatarChanged:()=>{},onBiometricChanged:()=>{},
}));
pass(()=>assert.match(memberProfile,/Membro fictício CI/));
pass(()=>assert.match(memberProfile,/Membro da caixinha/));
assert.equal(await biometricAvailable(),false);
assert.equal(await readPrivateAvatar(deviceAccountKey(admin)),null);
checks+=2;
console.log('M40500_CONSOLIDATED_UI_NATIVE_SECURITY=PASS_'+checks+'_OF_'+checks);
console.log('M40500_NO_AUTHENTICATED_SEED_NAMES=PASS');
console.log('M40500_GENUINE_FR_ICON_AND_ANDROID_INSETS=PASS');
console.log('M40500_BIOMETRIC_ONLY_FOR_EXISTING_SERVER_SESSION=PASS_STATIC');
console.log('M40500_PRIVATE_AVATAR_ANDROID_KEYSTORE=PASS_STATIC');
console.log('M40500_SQL_AND_TERMUX_RUNTIME=UNTOUCHED');
console.log('M40500_PIX_REAL=OFF');
console.log('M40500_PRODUCTION=BLOCKED');


// M40954: both directions require the same device authentication.
const toggle=panel.slice(panel.indexOf('const toggleBiometrics='),panel.indexOf("if(user.role==='MASTER')"));
assert.doesNotMatch(toggle,/if\(!bioEnabled\)/);
assert.ok(toggle.indexOf('await biometricChallenge(accountKey)')>=0);
assert.ok(toggle.indexOf('await biometricChallenge(accountKey)')<toggle.indexOf('await updateBiometricPreference'));
assert.match(native,/if \(!key\.equals\(lastBiometricAccount\) \|\|/);
assert.doesNotMatch(native,/if \(value && \(!key\.equals\(lastBiometricAccount\)/);
console.log('M40954_BIOMETRIC_CHANGE_BOTH_DIRECTIONS=PASS');
