import React, { useEffect, useState } from 'react';
import { AppState } from '../services/store';
import { financialApi } from '../services/financialApiService';

interface Props { state: AppState }
interface Account {
  id: string;
  tenant_id: string;
  account_code: string;
  account_name: string;
  account_type: string;
  balance_cents: number;
}
interface Transaction {
  id: string;
  tenant_id: string;
  description: string;
  transaction_date: string;
  reference_id: string;
  entries: Array<{ id: string; account_name: string; entry_type: string; amount_cents: number }>;
}
interface Result {
  key: string;
  status: 'loading' | 'ready' | 'error';
  accounts: Account[];
  transactions: Transaction[];
}

export const LedgerView: React.FC<Props> = ({ state }) => {
  const key = [state.currentUserId, state.currentRole, state.currentTenantId].join(':');
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<Result>({ key: '', status: 'loading', accounts: [], transactions: [] });
  useEffect(() => {
    let active = true;
    setResult({ key, status: 'loading', accounts: [], transactions: [] });
    if (state.currentRole !== 'TENANT_ADMIN' || !state.currentTenantId || !state.currentUserId) {
      setResult({ key, status: 'error', accounts: [], transactions: [] });
      return () => { active = false; };
    }
    Promise.all([
      financialApi.fetchLedgerAccounts(state.currentTenantId),
      financialApi.fetchLedgerTransactions(state.currentTenantId),
    ]).then(([accounts, transactions]) => {
      if (!Array.isArray(accounts) || !Array.isArray(transactions) ||
          accounts.some(a => a.tenant_id !== state.currentTenantId) ||
          transactions.some(t => t.tenant_id !== state.currentTenantId)) {
        throw new Error('Isolamento do ledger inválido');
      }
      if (active) setResult({ key, status: 'ready', accounts, transactions });
    }).catch(() => {
      if (active) setResult({ key, status: 'error', accounts: [], transactions: [] });
    });
    return () => { active = false; };
  }, [key, revision]);

  const current = result.key === key ? result : { key, status: 'loading' as const, accounts: [], transactions: [] };
  const fmt = (cents: number) =>
    new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(cents / 100);

  return (
    <section className="space-y-5" aria-labelledby="ledger-title">
      <header className="rounded-xl bg-white p-5">
        <h2 id="ledger-title" className="text-lg font-bold text-slate-900">Livro-Razão da Caixinha</h2>
        <p className="text-sm text-slate-600">Leitura exclusiva do administrador, diretamente do PostgreSQL com RLS.</p>
        <button type="button" onClick={() => setRevision(v => v + 1)}
          className="mt-3 rounded-lg border border-slate-300 px-4 py-2 text-sm">Atualizar</button>
      </header>
      {current.status === 'loading' && <p role="status">Carregando contas e lançamentos...</p>}
      {current.status === 'error' && <p role="alert" className="rounded-lg bg-rose-50 p-4 text-rose-900">
        Livro-Razão indisponível ou acesso não autorizado. Nenhum saldo demonstrativo é apresentado.
      </p>}
      {current.status === 'ready' && <>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {current.accounts.map(a => (
            <article key={a.id} className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">{a.account_code} — {a.account_type}</p>
              <h3 className="font-semibold text-slate-900">{a.account_name}</h3>
              <p className="mt-2 text-lg font-bold">{fmt(a.balance_cents)}</p>
            </article>
          ))}
        </div>
        {current.accounts.length === 0 && <p className="rounded-lg bg-white p-4">
          Nenhuma conta contábil encontrada no servidor para esta caixinha.
        </p>}
        <h3 className="text-base font-semibold text-slate-900">Lançamentos contabilizados</h3>
        {current.transactions.length === 0 && <p className="rounded-lg bg-white p-4">
          Nenhum lançamento confirmado.
        </p>}
        {current.transactions.map(t => (
          <article key={t.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <h4 className="font-semibold text-slate-900">{t.description}</h4>
            <p className="text-xs text-slate-600">{t.transaction_date} • Ref.: {t.reference_id}</p>
            <div className="mt-3 space-y-1">
              {t.entries.map(e => <p key={e.id} className="text-sm text-slate-700">
                {e.account_name} • {e.entry_type} • {fmt(e.amount_cents)}
              </p>)}
            </div>
          </article>
        ))}
      </>}
    </section>
  );
};
