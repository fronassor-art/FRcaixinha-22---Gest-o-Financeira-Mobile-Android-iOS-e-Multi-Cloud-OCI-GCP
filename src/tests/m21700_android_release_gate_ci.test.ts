import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const gradle=readFileSync('android/app/build.gradle','utf8');
const cap=readFileSync('capacitor.config.ts','utf8');
const manifest=readFileSync('android/app/src/main/AndroidManifest.xml','utf8');
for (const item of ['releaseRequested','productionRelease',
  'FR_FINANCE_ANDROID_RELEASE_KEYSTORE_FILE',
  'FR_FINANCE_ANDROID_RELEASE_STORE_PASSWORD',
  'FR_FINANCE_ANDROID_RELEASE_KEY_ALIAS',
  'FR_FINANCE_ANDROID_RELEASE_KEY_PASSWORD',
  'signingConfig signingConfigs.productionRelease',
  'parsed.server?.androidScheme != "https"',
  'parsed.server?.cleartext != false',
  'http://127.0.0.1:8000']) {
  assert.ok(gradle.includes(item),'missing Gradle gate '+item);
}
for(const item of ['FR_FINANCE_ANDROID_RELEASE_PROFILE','VITE_API_URL',
 'release exige origem HTTPS pública','release não aceita Termux.']) {
  assert.ok(cap.includes(item),'missing Capacitor gate '+item);
}
assert.ok(gradle.includes('applicationIdSuffix diagnosticParallel ? ".aistudio.diag" : ".aistudio"'));
assert.ok(gradle.includes('FR_FINANCE_ANDROID_PARALLEL_DIAGNOSTIC'));
assert.ok(gradle.includes('if (releaseRequested && diagnosticParallel)'));
assert.ok(gradle.includes('signingConfig signingConfigs.productionRelease'));
assert.ok(!manifest.includes('android:usesCleartextTraffic="true"'));
console.log('PASS M21700 release requires dedicated signing and public HTTPS');
