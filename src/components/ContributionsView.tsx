import React, { useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { AppState } from '../services/store';
import { financialApi } from '../services/financialApiService';
import { DisplayContribution, normalizeContributions, contributionScopeKey } from '../services/contributionsData';
import { formatBRL } from '../services/financialEngine';

interface ContributionsViewProps {
  state: AppState;
  onOpenPixModal: (params: {
    title: string; amount: number; description: string; recipientName: string;
    referenceId: string; onConfirm: () => void;
  }) => void;
}

type Result = { key: string; status: 'loading' | 'ready' | 'error'; items: DisplayContribution[]; message?: string };

export const ContributionsView: React.FC<ContributionsViewProps> = ({ state }) => {
  // O papel integra a chave: uma resposta do perfil administrador nunca pode ser exibida no perfil membro.
  const key = contributionScopeKey(state.currentUserId, state.currentTenantId, state.currentRole);
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<Result>({ key: '', status: 'loading', items: [] });

  useEffect(() => {
    let active = true;
    const tenant = state.currentTenantId;
    setResult({ key, status: 'loading', items: [] });
    if (!tenant || !state.currentUserId || state.currentRole === 'MASTER') {
      setResult({ key, status: 'error', items: [], message: 'Não há uma caixinha disponível para esta conta.' });
      return () => { active = false; };
    }
    financialApi.fetchContributions(tenant).then(data => {
      const items = normalizeContributions(data, tenant);
      if (active) setResult({ key, status: 'ready', items });
    }).catch(() => {
      if (active) setResult({ key, status: 'error', items: [], message: 'Não foi possível carregar as contribuições. Verifique a conexão e tente novamente.' });
    });
    return () => { active = false; };
  }, [key, revision, state.currentRole]);

  // Nunca mostre a resposta da conta anterior durante uma troca de sessão.
  const current = result.key === key ? result : { key, status: 'loading' as const, items: [] };
  return (
    <section className="space-y-4" aria-labelledby="contributions-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="contributions-title" className="text-lg font-bold text-slate-900">Contribuições</h2>
          <p className="text-sm text-slate-600">Valores consultados no servidor da sua caixinha.</p>
        </div>
        <button type="button" onClick={() => setRevision(n => n + 1)}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-50">
          <RefreshCw className="h-4 w-4" aria-hidden="true" /> Atualizar
        </button>
      </div>
      <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
        Pagamentos por Pix ainda não estão disponíveis. Nenhum valor é marcado como pago sem conciliação.
      </p>
      <div aria-live="polite">
        {current.status === 'loading' && <p className="py-4 text-sm text-slate-600">Carregando contribuições...</p>}
        {current.status === 'error' && <div role="alert" className="flex gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"><AlertTriangle className="h-5 w-5 shrink-0" aria-hidden="true" />{current.message}</div>}
        {current.status === 'ready' && current.items.length === 0 && <p className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Nenhuma contribuição encontrada para esta conta.</p>}
        {current.status === 'ready' && current.items.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {current.items.map(c => (
              <article key={c.id} className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0"><h3 className="break-words font-semibold text-slate-900">{c.member_name || 'Contribuição'}</h3><p className="text-sm text-slate-600">Competência {c.competence}</p></div>
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-800">{c.payment_status}</span>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-x-3 gap-y-3 text-sm">
                  <div><dt className="text-slate-600">Vencimento</dt><dd className="font-medium text-slate-900">{c.due_date.split('-').reverse().join('/')}</dd></div>
                  <div><dt className="text-slate-600">Situação</dt><dd className="break-words font-medium text-slate-900">{c.due_status.replaceAll('_', ' ')}</dd></div>
                  <div><dt className="text-slate-600">Valor devido</dt><dd className="font-semibold text-slate-900">{formatBRL(c.amount_due)}</dd></div>
                  <div><dt className="text-slate-600">Valor pago</dt><dd className="font-semibold text-slate-900">{formatBRL(c.amount_paid)}</dd></div>
                  <div className="col-span-2 border-t border-slate-100 pt-3"><dt className="text-slate-600">Saldo em aberto</dt><dd className="text-base font-bold text-slate-900">{formatBRL(Math.max(0, c.amount_due - c.amount_paid))}</dd></div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};
