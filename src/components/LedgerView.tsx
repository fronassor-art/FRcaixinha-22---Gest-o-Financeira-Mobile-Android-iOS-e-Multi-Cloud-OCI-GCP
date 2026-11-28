import React, { useEffect, useState } from 'react';
import {LedgerAccountEntries} from './LedgerAccountEntries';
import { AppState } from '../services/store';
import { financialApi } from '../services/financialApiService';
import { authService } from '../services/authService';
import type { LedgerIntegrityPreview } from '../services/ledgerIntegrityPreview';
import type {LedgerAccountDirectory} from '../services/ledgerAccountDirectoryBoundary';
import {ledgerReadMode} from '../services/ledgerVisibilityPolicy';
import {validateLedgerAccountLinks} from '../services/ledgerDetailBoundary';
import type {DisplayLedgerAccount,DisplayLedgerTransaction} from '../services/ledgerDetailBoundary';

interface Props { state: AppState }
interface Result {
  key: string;
  status: 'loading' | 'ready' | 'error';
  accounts: DisplayLedgerAccount[];
  transactions: DisplayLedgerTransaction[];
  integrity?: LedgerIntegrityPreview;
  directory?: LedgerAccountDirectory;
}

export const LedgerView: React.FC<Props> = ({ state }) => {
  const [revision, setRevision] = useState(0);
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const key = [state.currentUserId, state.currentRole, state.currentTenantId, revision].join(':');
  const [result, setResult] = useState<Result>({ key: '', status: 'loading', accounts: [], transactions: [] });
  useEffect(() => {
    let active = true;
    const snapshot=authService.captureSession();
    setSelectedAccountId(null);
    setResult({ key, status: 'loading', accounts: [], transactions: [] });
    if (state.currentRole !== 'TENANT_ADMIN' || !state.currentTenantId || !state.currentUserId) {
      setResult({ key, status: 'error', accounts: [], transactions: [] });
      return () => { active = false; };
    }
    financialApi.fetchLedgerIntegrityPreview(state.currentTenantId).then(async integrity=>{
      if(integrity.status!=='BALANCED') {
        // Somente em NO_TRANSACTIONS: solicitar nomes/códigos de contas,
        // nunca saldos ou lançamentos simulados. Em REVIEW_REQUIRED não detalhar.
        const directory=ledgerReadMode(integrity)==='DIRECTORY_WITHOUT_BALANCES'
          ?await financialApi.fetchLedgerAccountDirectory(state.currentTenantId!)
          :undefined;
        return {integrity,directory,
          accounts:[] as DisplayLedgerAccount[],
          transactions:[] as DisplayLedgerTransaction[]};
      }
      const [accounts,transactions]:[DisplayLedgerAccount[],DisplayLedgerTransaction[]]=await Promise.all([
        financialApi.fetchLedgerAccounts(state.currentTenantId),
        financialApi.fetchLedgerTransactions(state.currentTenantId),
      ]);
      if(!Array.isArray(accounts)||!Array.isArray(transactions)||
         accounts.some(a=>a.tenant_id!==state.currentTenantId)||
         transactions.some(t=>t.tenant_id!==state.currentTenantId)||
         transactions.length!==integrity.checked_transactions){
        throw Error('Detalhamento contábil incompatível.');
      }
      validateLedgerAccountLinks(accounts,transactions);
      return {integrity,accounts,transactions,directory:undefined};
    }).then(({integrity,accounts,transactions,directory})=>{
      if(active&&authService.isSessionSnapshotCurrent(snapshot))
        setResult({key,status:'ready',integrity,accounts,transactions,directory});
    }).catch(()=>{
      if(active&&authService.isSessionSnapshotCurrent(snapshot))
        setResult({key,status:'error',accounts:[],transactions:[]});
    });
    return () => { active = false; };
  }, [key, revision]);

  const current: Result = result.key === key ? result :
    { key, status: 'loading', accounts: [], transactions: [] };
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
      {current.status === 'ready' && current.integrity && <div
        className="rounded-xl border border-slate-200 bg-white p-4 space-y-2"
        aria-label="Prévia de integridade contábil">
        <h3 className="font-semibold text-slate-900">Prévia de integridade do Livro-Razão</h3>
        <p className="text-sm text-slate-700">
          Lançamentos examinados: {current.integrity.checked_transactions} ·
          Equilibrados: {current.integrity.balanced_transactions} ·
          Para revisão: {current.integrity.review_required_transactions}.
        </p>
        <p className="text-sm font-semibold text-slate-800" role="status">
          {current.integrity.status==='BALANCED'
            ?'Partidas dobradas consistentes na prévia.'
            :current.integrity.status==='REVIEW_REQUIRED'
              ?'Divergência contábil: detalhamento bloqueado para revisão.'
              :'Nenhuma transação contábil registrada; saldos e lançamentos consolidados não exibidos.'}
        </p>
        <p className="text-xs text-amber-900">
          Integridade matemática não é conciliação bancária, liberação de
          pagamentos, distribuição de lucros ou autorização de fechamento.
        </p>
      </div>}
      {current.status === 'ready' && current.integrity?.status==='NO_TRANSACTIONS'
        && current.directory && <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
          <h3 className="font-semibold text-slate-900">Plano de contas — sem saldos</h3>
          <p className="text-xs text-amber-900">
            Nenhuma transação registrada na prévia. Contas listadas apenas por
            nome e código; valores, conciliação e fechamento não estão confirmados.
          </p>
          {current.directory.accounts.length===0&&<p className="text-sm text-slate-700">
            Nenhuma conta contábil cadastrada para esta caixinha. Não há extrato a abrir.
          </p>}
          {current.directory.accounts.map(account=><article key={account.id}
            className="rounded-lg border border-slate-200 p-3">
            <p className="text-sm text-slate-600">{account.account_code} — {account.account_type}</p>
            <h4 className="font-medium text-slate-900">{account.account_name}</h4>
            <button type="button" onClick={()=>setSelectedAccountId(account.id)}
              className="mt-2 rounded-lg border px-3 py-2 text-sm">Ver extrato da conta</button>
          </article>)}
          {current.directory.accounts.filter(a=>a.id===selectedAccountId).map(a=>
            <LedgerAccountEntries key={key+':'+a.id}
              tenantId={state.currentTenantId!} account={a}
              onClose={()=>setSelectedAccountId(null)}/>)}
        </div>}
      {current.status === 'ready' && current.integrity?.status==='BALANCED' && <>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {current.accounts.map(a => (
            <article key={a.id} className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">{a.account_code} — {a.account_type}</p>
              <h3 className="font-semibold text-slate-900">{a.account_name}</h3>
              <p className="mt-2 text-lg font-bold">{fmt(a.balance_cents)}</p>
              <button type="button" onClick={()=>setSelectedAccountId(a.id)}
                className="mt-3 rounded-lg border border-slate-300 px-3 py-2 text-sm">
                Ver extrato da conta
              </button>
            </article>
          ))}
        </div>
        {current.accounts.length === 0 && <p className="rounded-lg bg-white p-4">
          Nenhuma conta contábil encontrada no servidor para esta caixinha.
        </p>}
        {current.accounts.filter(a=>a.id===selectedAccountId).map(a=>
          <LedgerAccountEntries key={key+':'+a.id}
            tenantId={state.currentTenantId!} account={a}
            onClose={()=>setSelectedAccountId(null)}/>)}
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
