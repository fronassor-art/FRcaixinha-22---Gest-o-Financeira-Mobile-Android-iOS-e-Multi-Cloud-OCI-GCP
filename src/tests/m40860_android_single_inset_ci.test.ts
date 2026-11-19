/** M40860 — single Android status inset, keyboard and logout viewport.
 * Static/SSR evidence only; physical Android verification is still pending.
 */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {LoginView} from '../components/LoginView';
import {visibleLoginHeight,resetLoginScroll} from '../services/loginViewport';

const css=readFileSync('src/index.css','utf8');
const code=readFileSync('src/components/LoginView.tsx','utf8');
const root=css.match(/#root\s*\{([^}]*)\}/s)?.[1];
const login=css.match(/main\.fr-page\s*\{([^}]*)\}/s)?.[1];
assert.ok(root && login);
assert.match(root,/padding-top:\s*var\(--fr-safe-top\)/);
assert.match(login,/padding-top:\s*1\.5rem\s*;/);
assert.doesNotMatch(login,/padding-top:[^;]*--fr-safe-top/);
assert.match(login,/box-sizing:\s*border-box/);
assert.match(login,/overflow-y:\s*auto/);
assert.match(login,/max-height:\s*100%/);
assert.match(code,/visibleLoginHeight\(/);
assert.match(code,/resetLoginScroll\(node\)/);
assert.match(code,/visual\?\.addEventListener\('resize'/);
assert.match(code,/visual\?\.addEventListener\('scroll'/);
assert.doesNotMatch(code,/<main[^>]+min-h-dvh/);
const markup=renderToStaticMarkup(React.createElement(LoginView,{onLoginSuccess:()=>undefined}));
assert.match(markup,/data-fr-login-scroll="true"/);
assert.match(markup,/min-h-0 h-full/);
assert.match(markup,/FR Finance/);
for (const [layout,visible,offset,top,result] of [
  [780,780,0,0,780],
  [780,780,0,34,746],
  [780,410,0,34,376],
  [780,380,20,34,366],
  [500,100,0,120,1],
] as const) {
  assert.equal(visibleLoginHeight(layout,visible,offset,top),result);
}
const node={scrollTop:240,scrollLeft:25};
resetLoginScroll(node as HTMLElement);
assert.deepEqual(node,{scrollTop:0,scrollLeft:0});
console.log('M40860_SINGLE_ANDROID_SAFE_TOP=PASS_STATIC');
console.log('M40860_KEYBOARD_LOGOUT=PASS_UNIT');
console.log('M40860_PHYSICAL_ANDROID=RETEST_REQUIRED');
console.log('M40860_PRODUCTION=BLOCKED');
