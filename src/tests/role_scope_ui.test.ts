import assert from 'node:assert/strict';
import { tabsAllowedToRole, isRoleTabAllowed, initialRoleTab } from '../services/roleScope';

assert.deepEqual(tabsAllowedToRole('TENANT_MEMBER'),[
  'MEU_PAINEL','MINHAS_CONTRIBUICOES','MEU_EMPRESTIMO','MEU_RESULTADO','NOTIFICACOES',
]);
assert.equal(initialRoleTab('TENANT_MEMBER'),'MEU_PAINEL');
for(const tab of [
  'MEMBROS','LEDGER','FECHAMENTO','CONSENTIMENTO',
  'AUTORIZACAO_ADMIN','LICENCAS','SUPORTE','NUVEM','AUDITORIA',
  'BOLOES','MEUS_BOLOES','RIFAS','MINHAS_RIFAS'
]){
  assert.equal(isRoleTabAllowed('TENANT_MEMBER',tab),false,'membro viu '+tab);
}
for(const tab of ['MEMBROS','FECHAMENTO','MEU_PAINEL','MEU_RESULTADO']){
  assert.equal(isRoleTabAllowed('MASTER',tab),false,'master viu '+tab);
}
assert.equal(isRoleTabAllowed('TENANT_ADMIN','FECHAMENTO'),true);
assert.equal(isRoleTabAllowed('TENANT_MEMBER','MEU_RESULTADO'),true);
console.log('PASS: papel membro nao autoriza telas globais ou administrativas');

for (const role of ['MASTER','TENANT_ADMIN','TENANT_MEMBER'] as const) {
  assert.equal(isRoleTabAllowed(role,'NOTIFICACOES'),true);
}
