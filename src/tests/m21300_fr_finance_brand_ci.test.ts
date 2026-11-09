import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read=(p:string)=>readFileSync(p,'utf8');
const files=[
 'capacitor.config.ts',
 'android/app/src/main/res/values/strings.xml',
 'android/app/src/debug/res/values/strings.xml',
 'android/app/src/main/assets/capacitor.config.json',
 'index.html','public/manifest.webmanifest','public/icon.svg',
 'src/components/Navbar.tsx','src/components/LoginView.tsx',
 'src/App.tsx','src/components/NotificationsView.tsx',
 'docs/FR_CAIXINHA_M21200_MERCADO_PAGO_CONFIGURATION.md',
 'README.md','server.ts','metadata.json'
];
for(const f of files){
 const src=read(f);
 assert.ok(src.includes('FR Finance'),f+' should present FR Finance');
 const screened = f === 'README.md' ? src.replaceAll('FR Caixinha 2.2','HISTORICAL_PROJECT') : src;
 assert.ok(!screened.includes('FR Caixinha'),f+' contains old commercial display name');
}
assert.ok(read('capacitor.config.ts').includes("appId: 'com.frcaixinha.app'"));
assert.ok(read('android/app/build.gradle').includes('applicationId "com.frcaixinha.app"'));
assert.ok(read('android/app/src/main/res/values/strings.xml').includes('<string name="app_name">FR Finance</string>'));
assert.ok(read('android/app/src/debug/res/values/strings.xml').includes('<string name="app_name">FR Finance</string>'));
const manifest=JSON.parse(read('public/manifest.webmanifest'));
assert.equal(manifest.short_name,'FR Finance');
assert.equal(JSON.parse(read('android/app/src/main/assets/capacitor.config.json')).appName,'FR Finance');
assert.match(read('src/components/MobileInstallModal.tsx'),/FR Finance/);
assert.match(read('src/components/GitHubSyncModal.tsx'),/FR Finance/);
assert.match(read('src/services/zipExportService.ts'),/FR Finance/);
assert.ok(read('docs/FR_FINANCE_REBRANDING_M21300.md').includes('com.frcaixinha.app'));
assert.equal(JSON.parse(read('metadata.json')).name,'FR Finance — Gestão Financeira');
assert.equal(JSON.parse(read('package.json')).name,'fr-finance-aistudio');
assert.equal(JSON.parse(read('package-lock.json')).name,'fr-finance-aistudio');
assert.equal(JSON.parse(read('package-lock.json')).packages[''].name,'fr-finance-aistudio');
console.log('M21300_FR_FINANCE_COMMERCIAL_BRAND_AND_ANDROID_ID=PASS');
