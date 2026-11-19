/** M40510: physical failure follow-up — login clipped on Android/status bar,
 * on keyboard resize, and after logout. Pure deterministic viewport math tests,
 * DOM structure checks + SSR. Never connects to database/phones/payment APIs.
 */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {LoginView} from '../components/LoginView';
import {visibleLoginHeight,resetLoginScroll} from '../services/loginViewport';
let checks=0;
const check=(f:()=>void)=>{f();checks++;};
const css=readFileSync('src/index.css','utf8');
const login=readFileSync('src/components/LoginView.tsx','utf8');
const android=readFileSync('capacitor.config.ts','utf8');
const html=readFileSync('index.html','utf8');
const sizes:Array<[number,number,number,number,number]>= [
 [800,800,0,0,800],
 [800,800,0,28,772],
 [800,800,0,52,748],
 [800,480,0,28,452], // keyboard open reduces visual viewport
 [800,320,0,28,292], // landscape with keyboard
 [800,300,20,52,268], // visual viewport offset
 [600,800,0,28,600], // no growth beyond root
 [1000,900,0,100,800],
 [500,100,0,120,1], // fully obscured: fail closed, still scrollable
 [400,400,0,0,400],
];
for(const [layout,vh,vo,top,expected] of sizes)
 check(()=>assert.equal(visibleLoginHeight(layout,vh,vo,top),expected));
for(const [layout,visual,offset,top,expected] of [
 [500,NaN,0,0,500],[500,0,0,0,500],
 [500,Infinity,0,0,500],[500,500,NaN,0,500],
 [500,500,0,Infinity,500],[0,300,0,0,1],
] as Array<[number,number,number,number,number]>)
 check(()=>assert.equal(visibleLoginHeight(layout,visual,offset,top),expected));
check(()=>{const fake={scrollTop:350,scrollLeft:42};
 resetLoginScroll(fake as HTMLElement);
 assert.deepEqual(fake,{scrollTop:0,scrollLeft:0});
});
check(()=>assert.match(login,/useLayoutEffect\(/));
check(()=>assert.match(login,/ref=\{loginScrollRef\}/));
check(()=>assert.match(login,/resetLoginScroll\(node\)/));
check(()=>assert.match(login,/window\.requestAnimationFrame\(/));
check(()=>assert.match(login,/visual\?\.addEventListener\('resize'/));
check(()=>assert.match(login,/visual\?\.addEventListener\('scroll'/));
check(()=>assert.match(login,/window\.addEventListener\('pageshow'/));
check(()=>assert.match(login,/selectedRole===null\)resetLoginScroll/));
check(()=>assert.match(login,/node\.style\.maxHeight=visibleHeight\+'px'/));
check(()=>assert.match(css,/main\.fr-page\s*\{[^}]*overflow-y:\s*auto/s));
check(()=>assert.match(css,/main\.fr-page\s*\{[^}]*overflow-anchor:\s*none/s));
check(()=>assert.match(css,/main\.fr-page\s*\{[^}]*padding-top:\s*1\.5rem/s));
check(()=>assert.match(css,/#root\s*\{[^}]*padding-top:\s*var\(--fr-safe-top\)/s));
check(()=>assert.match(android,/insetsHandling:\s*'css'/));
check(()=>assert.match(html,/viewport-fit=cover/));
const markup=renderToStaticMarkup(React.createElement(LoginView,{onLoginSuccess:()=>undefined}));
check(()=>assert.match(markup,/data-fr-login-scroll="true"/));
check(()=>assert.match(markup,/FR Finance/));
check(()=>assert.match(markup,/Entrar na sua conta/));
check(()=>assert.match(markup,/fr-finance-m40500/));
assert.equal(checks,36,'M40510 case count changed: '+checks);
console.log('M40510_ANDROID_LOGIN_VISUAL_VIEWPORT=PASS_36_OF_36');
console.log('M40510_AFTER_LOGOUT_SCROLL_RESET=PASS_STATIC_AND_UNIT');
console.log('M40510_KEYBOARD_AND_SAFE_INSETS=PASS_STATIC_AND_UNIT');
console.log('M40510_ORIGINAL_POSTGRES=NOT_CONNECTED');
console.log('M40510_SERVICE_RESTARTS=NONE');
console.log('M40510_PRODUCTION=BLOCKED');
