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
const app=file('src/App.tsx');
const android=file('android/app/build.gradle');
const workflow=file('.github/workflows/validacao-atualizacao.yml');

assert.match(html,/viewport-fit=cover/);
assert.match(config,/SystemBars:\s*\{/);
assert.match(config,/insetsHandling:\s*'css'/);
assert.match(config,/initialViewportFitValueHint:\s*'cover'/);
assert.match(config,/style:\s*'DARK'/);
assert.match(css,/--fr-safe-top:\s*var\(--safe-area-inset-top,\s*env\(safe-area-inset-top,\s*0px\)\)/);
assert.match(css,/--fr-safe-bottom:\s*var\(--safe-area-inset-bottom,\s*env\(safe-area-inset-bottom,\s*0px\)\)/);
assert.match(css,/html, body\\s*\\{[^}]*overflow:\\s*hidden/s);
assert.match(css,/#root\\s*\\{[^}]*position:\\s*fixed;[^}]*padding-top:\\s*var\\(--fr-safe-top\\)/s);
assert.doesNotMatch(css,/body\\s*\\{[^}]*padding-top:/s);
assert.match(css,/\\.fr-app-profile\\s*\\{[^}]*flex-shrink:\\s*0/s);
assert.match(css,/\.fr-app-shell\s*\{[^}]*height:\s*100%;[^}]*overflow:\s*hidden/s);
assert.match(css,/\.fr-app-main\s*\{[^}]*overflow-y:\s*auto/s);
assert.match(css,/#root\s*\{[^}]*height:\s*100%/s);
assert.match(css,/\.fr-mobile-nav\s*\{[^}]*padding-bottom:\s*max\(\.5rem,\s*var\(--fr-safe-bottom\)\)/s);
assert.match(css,/main\\.fr-page\\s*\\{[^}]*overflow-y:\\s*auto/s);
assert.match(nav,/className="fr-app-header relative/);
assert.doesNotMatch(nav,/fr-app-header sticky/);
assert.match(app,/className="fr-app-shell /);
assert.match(app,/<main className="fr-app-main /);
assert.match(app,/fr-mobile-nav relative/);
assert.match(app,/fr-app-profile shrink-0/);
assert.match(app,/whitespace-normal break-words leading-4/);
assert.doesNotMatch(app,/className="truncate">\\s*\\{state.currentRole === 'MASTER'/);
assert.doesNotMatch(app,/fr-mobile-nav fixed/);
assert.doesNotMatch(app,/min-h-dvh min-w-0/);
assert.match(android,/applicationIdSuffix "\.aistudio"/);
assert.match(workflow,/Validar barras de sistema e safe area Android/);
assert.match(workflow,/SystemBars\?\.insetsHandling/);
const login=renderToStaticMarkup(React.createElement(LoginView,{
 onLoginSuccess:()=>undefined
}));
assert.match(login,/fr-page fr-sheen/);
console.log('PACOTE_16_ANDROID_SAFE_AREA_CI=PASS');
