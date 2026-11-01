import assert from 'node:assert/strict';
import { AppStore } from '../services/store';
import { financialApi } from '../services/financialApiService';
import { normalizeContributions } from '../services/contributionsData';

async function main() {
  const apiRow = { id: 'c1', tenant_id: 't1', cycle_id: '2027', membership_id: 'm1',
    competence: '2027-01', due_date: '2027-01-10', amount_due: '100.00', amount_paid: '0.00',
    payment_status: 'PENDENTE', due_status: 'NO_PRAZO', member_name: 'Pessoa teste' };
  const parsed = normalizeContributions([apiRow], 't1');
  assert.equal(parsed[0].amount_due, 100);
  assert.equal(parsed[0].due_status, 'A_VENCER');
  assert.throws(() => normalizeContributions([apiRow], 'outra-caixinha'));
  assert.throws(() => normalizeContributions([{ ...apiRow, amount_paid: null }], 't1'));
  const store = new AppStore();
  const contribution = store.getState().contributions[0];
  assert.ok(contribution, 'O cenário deve conter contribuição para o teste');
  const beforeContribution = structuredClone(contribution);
  const beforeAccounts = structuredClone(store.getState().ledgerAccounts);
  const beforeTransactions = structuredClone(store.getState().ledgerTransactions);

  financialApi.payContribution = async () => ({ status: 'AGUARDANDO_CONCILIACAO', is_reconciled: false });
  await store.registerContributionPayment(contribution.id, 10);
  assert.deepEqual(contribution, beforeContribution, 'Intenção pendente não deve alterar contribuição');
  assert.deepEqual(store.getState().ledgerAccounts, beforeAccounts, 'Intenção pendente não deve alterar saldos');
  assert.deepEqual(store.getState().ledgerTransactions, beforeTransactions, 'Intenção pendente não deve criar lançamentos');

  financialApi.fetchQuotas = async () => [];
  financialApi.fetchContributions = async () => [];
  financialApi.fetchLoans = async () => [];
  financialApi.fetchLedgerAccounts = async () => [];
  assert.equal(await store.refreshFinancialDataFromServer('tenant-de-teste'), true);
  assert.equal(store.getState().isDataLoadedFromServer, false, 'Resposta da API sem integração não torna os dados locais autoritativos');
  const isolated = new AppStore();
  isolated.setAuthenticatedContext({ id: 'user-a', role: 'TENANT_MEMBER', tenantId: 'tenant-inaugural' });
  const originalTitle = isolated.getState().raffleCampaigns[0].title;
  isolated.getState().raffleCampaigns[0].title = 'Edição fictícia da sessão anterior';
  isolated.setAuthenticatedContext({ id: 'user-b', role: 'TENANT_MEMBER', tenantId: 'tenant-tech' });
  assert.equal(isolated.getState().raffleCampaigns[0].title, originalTitle,
    'Troca de usuário deve descartar mutações locais anteriores');
  isolated.getState().raffleCampaigns[0].title = 'Outra edição fictícia';
  isolated.clearAuthenticatedContext();
  assert.equal(isolated.getState().raffleCampaigns[0].title, originalTitle,
    'Logout deve descartar mutações locais anteriores');
  assert.equal(new AppStore().getState().raffleCampaigns[0].title, originalTitle,
    'Seed global não deve ser alterado por uma sessão');
  console.log('PASS: intenção pendente não altera saldos; conectividade não valida dados locais.');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
