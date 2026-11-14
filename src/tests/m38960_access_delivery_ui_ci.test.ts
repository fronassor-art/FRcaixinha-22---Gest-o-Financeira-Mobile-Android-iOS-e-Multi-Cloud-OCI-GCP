/* M38960: Android recovery button uses existing API, never claims fake delivery. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const ui = readFileSync('src/components/LoginView.tsx', 'utf8');
const svc = readFileSync('src/services/authService.ts', 'utf8');
const api = readFileSync('backend/app/routers/auth.py', 'utf8');
const invite = readFileSync('backend/app/routers/invitations.py', 'utf8');
const members = readFileSync('src/components/MembersView.tsx', 'utf8');
const finance = readFileSync('src/services/financialApiService.ts', 'utf8');

assert.match(ui, /authService\.requestPasswordReset\(email\.trim\(\)\)/);
assert.match(ui, /Enviar instruções de recuperação/);
assert.match(ui, /setResetBusy\(true\)/);
assert.match(ui, /setResetNotice\(cause instanceof Error/);
assert.match(svc, /api\/v1\/auth\/forgot-password/);
assert.match(svc, /reply\.status !== 'REQUEST_ACCEPTED_IF_ELIGIBLE'/);
assert.match(svc, /reply\.user_exists !== null/);
assert.match(svc, /reply\.email_sent !== false/);
assert.match(svc, /res\.status !== 202/);
assert.match(svc, /Recuperação ainda indisponível\. Nenhuma mensagem foi enviada/);

assert.match(api, /submit_password_recovery_to_existing_outbox/);
assert.match(invite, /submit_invitation_to_existing_outbox/);
assert.match(members, /Solicitar convite/);
assert.match(members, /financialApi\.issueMemberInvitation/);
assert.match(members, /UUID do contrato publicado/);
assert.match(finance, /public async issueMemberInvitation/);
assert.match(finance, /\/api\/v1\/invitations/);
assert.match(finance, /r\.status !== 'QUEUED_FOR_DELIVERY'/);
assert.match(finance, /r\.activation_authorized !== false/);
assert.doesNotMatch(api, /submit_access_message\(/);
assert.doesNotMatch(invite, /submit_access_message\(/);
assert.doesNotMatch(ui, /localStorage\.setItem/);
console.log('M38960: rotas e interface de recuperação vinculadas sem envio fictício PASS');
