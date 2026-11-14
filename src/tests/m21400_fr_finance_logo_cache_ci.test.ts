import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read=(f:string)=>readFileSync(f,'utf8');
const token='fr-finance-m21400';
const publicIcon=read('public/icon.svg');
assert.match(publicIcon,/>FR Finance<\/text>/);
assert.doesNotMatch(publicIcon,/>FRcaixinha<\/text>/);
const sw=read('public/sw.js');
assert.ok(sw.includes("const CACHE_NAME = '"+token+"-static'"));
assert.ok(sw.includes("url.pathname === '/icon.svg'"));
assert.ok(sw.indexOf("url.pathname === '/icon.svg'") < sw.indexOf('// Stale-while-revalidate for static assets'));
for(const path of ['src/components/LoginView.tsx','src/components/Navbar.tsx']){
 const s=read(path);
 assert.ok(s.includes('src="/icon.svg?v='+token+'"'),path);
}
assert.ok(read('index.html').includes('/icon.svg?v='+token));
const manifest=JSON.parse(read('public/manifest.webmanifest'));
assert.equal(manifest.icons[0].src,'/icon.svg?v='+token);
assert.equal(manifest.short_name,'FR Finance');
// The older Android app keeps its package ID and all stored accounts/sessions.
assert.ok(read('capacitor.config.ts').includes("appId: 'com.frcaixinha.app'"));
assert.ok(!sw.includes("frcaixinha-v2.2-cache"));
console.log('M21400_FR_FINANCE_LOGO_CACHE_INVALIDATION=PASS');
