import React, { useEffect, useState } from 'react';
import { financialApi } from '../services/financialApiService';
import { AppState } from '../services/store';

interface DashboardViewProps {
  state: AppState;
  onNavigateTab: (tab: string) => void;
  onOpenPixModal: (params: {
    title: string;
    amount: number;
    description: string;
    recipientName: string;
    referenceId: string;
    onConfirm: () => void;
  }) => void;
}

type MasterData = Awaited<ReturnType<typeof financialApi.fetchMasterOverview>>;
type TenantData = Awaited<ReturnType<typeof financialApi.fetchTenantOverview>>;
type Result = {
  scope: string;
  status: 'loading' | 'ready' | 'error';
  master?: MasterData;
  tenant?: TenantData;
};

/** Painel minimalista: apenas consultas reais autorizadas pelo backend. */
export const DashboardView: React.FC<DashboardViewProps> = ({ state, onNavigateTab }) => {
  const role = state.currentRole;
  const scope = [state.currentUserId, role, state.currentTenantId].join(':');
  const [result, setResult] = useState<Result>({ scope: '', status: 'loading' });
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let alive = true;
    setResult({ scope, status: 'loading' });

    const request = role === 'MASTER'
      ? financialApi.fetchMasterOverview().then(master => {
          if (master.source !== 'POSTGRESQL_RLS') throw Error('Resposta inválida');
          if (alive) setResult({ scope, status: 'ready', master });
        })
      : financialApi.fetchTenantOverview(state.currentTenantId).then(tenant => {
          if (tenant.source !== 'POSTGRESQL_RLS' ||
              tenant.role !== role || tenant.tenant_id !== state.currentTenantId) {
            throw Error('Contexto inválido');
          }
          if (alive) setResult({ scope, status: 'ready', tenant });
        });
    request.catch(() => {
      if (alive) setResult({ scope, status: 'error' });
    });
    return () => { alive = false; };
  }, [scope, revision]);

  const current = result.scope === scope ? result : { scope, status: 'loading' };
  const heading = role === 'MASTER' ? 'Minha plataforma'
    : role === 'TENANT_ADMIN' ? 'Gestão da caixinha' : 'Minha caixinha';

  if (current.status !== 'ready') {
    return (
      <section role="status" className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-bold text-slate-900">{heading}</h2>
        <p className="mt-2 text-sm text-slate-600">
          {current.status === 'error'
            ? 'Não foi possível carregar os dados. Verifique sua conexão.'
            : 'Carregando...'}
        </p>
        {current.status === 'error' && (
          <button type="button" onClick={() => setRevision(x => x + 1)}
            className="mt-3 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold">
            Tentar novamente
          </button>
        )}
      </section>
    );
  }

  if (role === 'MASTER') {
    const data = current.master!;
    return (
      <section className="space-y-4" aria-label="Painel da plataforma">
        <h2 className="text-xl font-bold text-slate-900">Minha plataforma</h2>
        <div className="grid grid-cols-2 gap-3">
          <article className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-xs text-slate-600">Caixinhas</h3>
            <p className="mt-1 text-3xl font-bold text-slate-950">{data.total_tenants}</p>
          </article>
          <article className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-xs text-slate-600">Licenciamento</h3>
            <p className="mt-2 text-sm font-semibold text-amber-800">Em homologação</p>
          </article>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-bold text-slate-900">Caixinhas cadastradas</h3>
            <button type="button" onClick={() => onNavigateTab('LICENCAS')}
              className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white">
              Licenças
            </button>
          </div>
          {data.tenants.length === 0 ? (
            <p className="mt-3 text-sm text-slate-600">Nenhuma caixinha cadastrada.</p>
          ) : (
            <ul className="mt-3 divide-y divide-slate-100">
              {data.tenants.slice(0, 10).map(tenant => (
                <li key={tenant.id} className="py-3">
                  <p className="font-semibold text-slate-900">{tenant.display_name}</p>
                  <p className="text-xs text-slate-600">
                    {tenant.status}{tenant.is_owner_box ? ' · Inaugural' : ''}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    );
  }

  const data = current.tenant!;
  const cards = [
    { name: 'Cotas', value: data.quota_count_visible },
    { name: 'Contribuições', value: data.contribution_count_visible },
    { name: 'Empréstimos', value: data.loan_count_visible },
    ...(role === 'TENANT_ADMIN'
      ? [{ name: 'Membros', value: data.member_count_visible ?? 0 }] : []),
  ];

  return (
    <section className="space-y-4" aria-label={heading}>
      <h2 className="text-xl font-bold text-slate-900">{heading}</h2>
      <div className="grid grid-cols-2 gap-3">
        {cards.map(card => (
          <article key={card.name} className="min-w-0 rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-xs font-medium text-slate-600">{card.name}</h3>
            <p className="mt-1 text-3xl font-bold text-slate-950">{card.value}</p>
          </article>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => onNavigateTab(
          role === 'TENANT_ADMIN' ? 'CONTRIBUICOES' : 'MINHAS_CONTRIBUICOES')}
          className="min-h-11 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white">
          {role === 'TENANT_ADMIN' ? 'Ver contribuições' : 'Minhas contribuições'}
        </button>
        {role === 'TENANT_ADMIN' && (
          <button type="button" onClick={() => onNavigateTab('MEMBROS')}
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800">
            Ver membros
          </button>
        )}
      </div>
      <p className="text-xs text-slate-500">
        {role === 'TENANT_ADMIN'
          ? 'Dados desta caixinha. Operações financeiras reais desativadas.'
          : 'Somente seus dados autorizados. Operações reais desativadas.'}
      </p>
    </section>
  );
};
