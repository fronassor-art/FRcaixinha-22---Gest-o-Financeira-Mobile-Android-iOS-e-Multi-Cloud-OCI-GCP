import assert from 'node:assert/strict';
import { AppStore } from '../services/store';
import { financialApi } from '../services/financialApiService';

async function main() {
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
  console.log('PASS: intenção pendente não altera saldos; conectividade não valida dados locais.');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
