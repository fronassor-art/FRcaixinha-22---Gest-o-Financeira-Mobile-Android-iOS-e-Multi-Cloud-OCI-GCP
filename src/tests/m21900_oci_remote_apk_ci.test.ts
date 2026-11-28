import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const wf=readFileSync('.github/workflows/fr-finance-oci-staging-apk.yml','utf8');
const native=readFileSync('capacitor.config.ts','utf8');
for(const item of ['workflow_dispatch:','api_https_url:','FR_FINANCE_ANDROID_RELEASE_PROFILE',
  'VITE_API_URL','npm run cap:build','FRCAIXINHA_ANDROID_REQUIRE_STABLE_SIGNING',
  'FRCAIXINHA_ANDROID_KEYSTORE_BASE64','assembleDebug',
  'com.frcaixinha.app.aistudio','https','FRCAIXINHA_ANDROID_VERSION_CODE',
  'fr-finance-oci-staging-debug','http://127.0.0.1:8000',
  'apksigner','upload-artifact@v4']){
  assert.ok(wf.includes(item),'missing staging security gate: '+item);
}
assert.ok(!wf.includes('assembleRelease'));
assert.ok(!wf.includes('terraform apply'));
assert.ok(!/^  push:/m.test(wf));
assert.ok(!/^  pull_request:/m.test(wf));
assert.ok(native.includes('FR_FINANCE_ANDROID_RELEASE_PROFILE'));
console.log('PASS M21900 manual staging HTTPS APK boundary');
