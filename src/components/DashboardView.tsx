import React, { useEffect, useState } from 'react';
import { BriefcaseBusiness, ChevronRight, Coins, Layers3, ShieldCheck, TrendingUp, Users, Wallet } from 'lucide-react';
import { financialApi } from '../services/financialApiService';
import { AppState } from '../services/store';

interface DashboardViewProps {
  state: AppState;
  onNavigateTab: (tab: string) => void;
  onOpenPixModal: (params: {
    title: string; amount: number; description: string;
    recipientName: string; referenceId: string; onConfirm: () => void;
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

/** Somente indicadores do backend, sem saldos, progresso ou pagamentos seed. */
export const DashboardView: React.FC<DashboardViewProps> = ({ state, onNavigateTab }) => {
  const role = state.currentRole;
  const scope = [state.currentUserId, role, state.currentTenantId].join(':');
  const [result, setResult] = useState<Result>({ scope: '', status: 'loading' });
  const [revision, setRevision] = useState(0);
  const currentUser = state.users.find(user => user.id === state.currentUserId);
  const firstName = currentUser?.name?.trim().split(/\s+/)[0] || 'você';

  useEffect(() => {
    let alive = true;
    setResult({ scope, status: 'loading' });
    const request = role === 'MASTER'
      ? financialApi.fetchMasterOverview().then(master => {
          if (master.source !== 'POSTGRESQL_RLS') throw Error('Origem de dados inválida');
          if (alive) setResult({ scope, status: 'ready', master });
        })
      : financialApi.fetchTenantOverview(state.currentTenantId).then(tenant => {
          if (tenant.source !== 'POSTGRESQL_RLS' ||
              tenant.role !== role || tenant.tenant_id !== state.currentTenantId) {
            throw Error('Contexto de acesso inválido');
          }
          if (alive) setResult({ scope, status: 'ready', tenant });
        });
    request.catch(() => { if (alive) setResult({ scope, status: 'error' }); });
    return () => { alive = false; };
  }, [scope, revision]);

  const current: Result = result.scope === scope ? result : { scope, status: 'loading' };
  const heading = role === 'MASTER' ? 'Minha plataforma'
    : role === 'TENANT_ADMIN' ? 'Gestão da caixinha' : 'Meu painel';

  if (current.status !== 'ready') {
    return (
      <section role="status" className="fr-green-card rounded-2xl p-6 text-white">
        <h2 className="text-lg font-bold text-[#f6dc98]">{heading}</h2>
        <p className="mt-2 text-sm text-emerald-50/85">
          {current.status === 'error'
            ? 'Não foi possível carregar seus dados. Verifique a conexão.'
            : 'Carregando seus dados...'}
        </p>
        {current.status === 'error' && (
          <button type="button" onClick={() => setRevision(value => value + 1)}
            className="fr-outline mt-4 rounded-lg px-4 py-2 text-sm font-semibold">
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
        <div className="fr-green-card fr-sheen rounded-[24px] p-5 text-white">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm text-emerald-100">Olá, {firstName}</p>
              <h2 className="mt-1 text-2xl font-bold text-[#f7d988]">Minha plataforma</h2>
            </div>
            <ShieldCheck className="h-7 w-7 text-[#f1d485]" aria-hidden="true"/>
          </div>
          <p className="mt-5 text-xs font-medium text-emerald-100/85">Caixinhas cadastradas</p>
          <p className="mt-1 text-4xl font-extrabold">{data.total_tenants}</p>
          <button type="button" onClick={() => onNavigateTab('CAIXINHAS')}
            className="mt-4 flex min-h-11 w-full items-center justify-between rounded-xl border border-[#c7aa68]/35 bg-black/15 px-3 py-3 text-left"
          >
            <span className="text-sm text-emerald-50">Gestão cadastral de caixinhas</span>
            <ChevronRight className="h-5 w-5 text-[#f1d485]" aria-hidden="true"/>
          </button>
          <div className="mt-3 flex items-center justify-between rounded-xl border border-[#c7aa68]/35 bg-black/15 px-3 py-3">
            <span className="text-sm text-emerald-50">Licenciamento em homologação</span>
            <button type="button" onClick={() => onNavigateTab('LICENCAS')}
              aria-label="Ver licenças" className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#efd17a] text-[#12452e]">
              <ChevronRight className="h-5 w-5"/>
            </button>
          </div>
        </div>
        <div className="fr-light-card rounded-2xl p-4">
          <div className="mb-2 flex items-center gap-2">
            <BriefcaseBusiness className="h-5 w-5 text-[#075337]"/>
            <h3 className="font-bold text-[#153e2a]">Minhas caixinhas</h3>
          </div>
          {data.tenants.length === 0 ? (
            <p className="text-sm text-slate-600">Nenhuma caixinha cadastrada.</p>
          ) : (
            <ul className="divide-y divide-[#e4ede3]">
              {data.tenants.slice(0, 10).map(tenant => (
                <li key={tenant.id} className="flex min-w-0 items-center justify-between gap-2 py-3">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-[#163c2a]">{tenant.display_name}</p>
                    <p className="text-xs text-[#687c6f]">{tenant.status}{tenant.is_owner_box ? ' · Inaugural' : ''}</p>
                  </div>
                  <Coins className="h-5 w-5 shrink-0 text-[#b28b39]" aria-hidden="true"/>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    );
  }

  const data = current.tenant!;
  const member = role === 'TENANT_MEMBER';
  const cards = [
    { name: 'Cotas', value: data.quota_count_visible, icon: Layers3 },
    { name: 'Contribuições', value: data.contribution_count_visible, icon: Wallet },
    { name: 'Empréstimos', value: data.loan_count_visible, icon: TrendingUp },
    ...(!member ? [{ name: 'Membros', value: data.member_count_visible ?? 0, icon: Users }] : []),
  ];
  return (
    <section className="space-y-4" aria-label={heading}>
      <div className="fr-green-card fr-sheen rounded-[24px] p-5 text-white">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-sm text-emerald-100">Olá, {firstName}</p>
            <h2 className="mt-1 text-2xl font-bold text-[#f7d988]">{heading}</h2>
          </div>
          <ShieldCheck className="h-7 w-7 text-[#f1d485]" aria-hidden="true"/>
        </div>
        <p className="mt-4 text-sm text-emerald-100/80">
          {member ? 'Seu resumo individual' : 'Resumo desta caixinha'}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button"
            onClick={() => onNavigateTab(member ? 'MINHAS_CONTRIBUICOES' : 'CONTRIBUICOES')}
            className="fr-gold-button flex min-h-11 items-center gap-2 rounded-xl px-4 text-sm">
            <Wallet className="h-4 w-4"/>
            {member ? 'Minhas contribuições' : 'Contribuições'}
          </button>
          {!member && (
            <button type="button" onClick={() => onNavigateTab('MEMBROS')}
              className="fr-outline flex min-h-11 items-center gap-2 rounded-xl px-4 text-sm">
              <Users className="h-4 w-4"/>Membros
            </button>
          )}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {cards.map(({name,value,icon:Icon}) => (
          <article key={name} className="fr-light-card min-w-0 rounded-2xl p-4">
            <Icon className="h-5 w-5 text-[#b58c35]" aria-hidden="true"/>
            <h3 className="mt-2 text-xs font-semibold text-[#536c5b]">{name}</h3>
            <p className="mt-1 text-3xl font-extrabold text-[#0a4831]">{value}</p>
          </article>
        ))}
      </div>
      <p className="px-1 text-xs text-[#6a806f]">
        {member ? 'Exibimos apenas seus dados autorizados.' : 'Exibimos apenas dados desta caixinha.'}
      </p>
    </section>
  );
};
