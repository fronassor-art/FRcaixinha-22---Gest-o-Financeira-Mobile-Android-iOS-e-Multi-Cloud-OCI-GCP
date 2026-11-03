/* Pacote 16: regressão visual Android no APK 180, sem banco. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {LoginView} from '../components/LoginView';

const file=(p:string)=>readFileSync(p,'utf8');
const css=file('src/index.css');
const config=file('capacitor.config.ts');
const html=file('index.html');
const nav=file('src/components/Navbar.tsx');
const android=file('android/app/build.gradle');
const workflow=file('.github/workflows/validacao-atualizacao.yml');

assert.match(html,/viewport-fit=cover/);
assert.match(config,/SystemBars:\s*\{/);
assert.match(config,/insetsHandling:\s*'native'/);
assert.match(config,/initialViewportFitValueHint:\s*'cover'/);
assert.match(config,/style:\s*'DARK'/);
assert.match(css,/--fr-safe-top:\s*env\(safe-area-inset-top,\s*0px\)/);
assert.match(css,/--fr-safe-bottom:\s*env\(safe-area-inset-bottom,\s*0px\)/);
assert.match(css,/body\s*\{[^}]*padding-top:\s*var\(--fr-safe-top\)/s);
assert.match(css,/\.fr-app-header\s*\{[^}]*top:\s*var\(--fr-safe-top\)/s);
assert.match(css,/\.fr-mobile-nav\s*\{[^}]*padding-bottom:\s*max\(\.5rem,\s*var\(--fr-safe-bottom\)\)/s);
assert.match(css,/main\.fr-page\s*\{[^}]*min-height:\s*calc\(100dvh - var\(--fr-safe-top\)\)/s);
assert.match(nav,/className="fr-app-header sticky/);
assert.doesNotMatch(nav,/sticky top-0/);
assert.match(android,/applicationIdSuffix "\.aistudio"/);
assert.match(workflow,/Validar barras de sistema e safe area Android/);
assert.match(workflow,/SystemBars\?\.insetsHandling/);
const login=renderToStaticMarkup(React.createElement(LoginView,{
 onLoginSuccess:()=>undefined
}));
assert.match(login,/fr-page fr-sheen/);
console.log('PACOTE_16_ANDROID_SAFE_AREA_CI=PASS');
