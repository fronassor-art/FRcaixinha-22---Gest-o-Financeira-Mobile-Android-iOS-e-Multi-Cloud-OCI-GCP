import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { isRoleTabAllowed } from '../services/roleScope';

const app=readFileSync('src/App.tsx','utf8');
const view=readFileSync('src/components/NotificationsView.tsx','utf8');
for(const role of ['MASTER','TENANT_ADMIN','TENANT_MEMBER'] as const){
  assert.equal(isRoleTabAllowed(role,'NOTIFICACOES'),true);
}
assert.ok(app.includes("{visibleTab === 'NOTIFICACOES'"));
assert.equal((app.match(/id: 'NOTIFICACOES'/g)||[]).length,3);
assert.ok(view.includes('Notificações'));
assert.ok(view.includes('Não ativado'));
assert.ok(view.includes('role: UserRole'));
assert.ok(!view.includes('requestPermission('));
assert.ok(!view.includes('localStorage.setItem'));
assert.ok(!view.includes('mockUnread'));
console.log('PASS M15000 notificações UI: três perfis, sem contagem ou entrega fictícia');
