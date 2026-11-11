/* FR Finance M38993: one-time links on existing Android login and API. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const auth = readFileSync('src/services/authService.ts', 'utf8');
const login = readFileSync('src/components/LoginView.tsx', 'utf8');
const link = readFileSync('src/components/AccessLinkView.tsx', 'utf8');
const api = readFileSync('backend/app/routers/auth.py', 'utf8');
const invite = readFileSync('backend/app/routers/invitations.py', 'utf8');

assert.match(link, /parseAccessLink\(hash: string\)/);
assert.match(link, /#recuperacao\?/);
assert.match(link, /#convite\?/);
assert.match(login, /window\.history\.replaceState/);
assert.match(login, /<AccessLinkView link=\{accessLink\}/);
assert.match(link, /authService\.completePasswordReset\(token, newPassword\)/);
assert.match(link, /authService\.verifyInvitationEmail\(token\)/);
assert.match(link, /setToken\(''\)/);
assert.match(link, /setNewPassword\(''\)/);
assert.match(link, /Não foi possível validar o link/);
assert.match(auth, /\/api\/v1\/auth\/reset-password/);
assert.match(auth, /\/api\/v1\/invitations\/verify-email/);
assert.match(auth, /data\.sessions_revoked !== true/);
assert.match(auth, /data\.account_activated !== false/);
assert.match(api, /complete_original_pg18_password_reset/);
assert.match(invite, /verify_original_pg18_invitation_email/);
assert.doesNotMatch(link, /localStorage\.setItem|sessionStorage\.setItem/);
console.log('M38993 original Android deep-link consumption: PASS');
