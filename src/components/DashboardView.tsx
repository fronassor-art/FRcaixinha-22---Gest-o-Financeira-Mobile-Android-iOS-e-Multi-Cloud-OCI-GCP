import React, { useEffect, useState } from 'react';
import { financialApi } from '../services/financialApiService';
import {
  Wallet,
  ArrowUpRight,
  ArrowDownLeft,
  Users,
  ShieldCheck,
  AlertCircle,
  Clock,
  CheckCircle2,
  Percent,
  Calendar,
  Lock,
  Building,
  TrendingUp,
  FileText,
  Ticket,
  Cloud,
  Smartphone
} from 'lucide-react';
import { AppState, appStore } from '../services/store';
import { formatBRL, formatDateBR } from '../services/financialEngine';

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

export const DashboardView: React.FC<DashboardViewProps> = ({ state, onNavigateTab, onOpenPixModal }) => {
  const currentRole = state.currentRole;
  const scope = [state.currentUserId, currentRole, state.currentTenantId].join(':');
  type MasterData = Awaited<ReturnType<typeof financialApi.fetchMasterOverview>>;
  type TenantData = Awaited<ReturnType<typeof financialApi.fetchTenantOverview>>;
  type Result = {
    scope: string;
    status: 'loading' | 'ready' | 'error';
    master?: MasterData;
    tenant?: TenantData;
    error?: string;
  };
  const [serverResult, setServerResult] = useState<Result>({ scope: '', status: 'loading' });
  useEffect(() => {
    let active = true;
    setServerResult({ scope, status: 'loading' });
    const task = currentRole === 'MASTER'
      ? financialApi.fetchMasterOverview().then(master => {
          if (master.source !== 'POSTGRESQL_RLS') throw new Error('Fonte de dados inválida');
          if (active) setServerResult({ scope, status: 'ready', master });
        })
      : financialApi.fetchTenantOverview(state.currentTenantId).then(tenant => {
          if (tenant.source !== 'POSTGRESQL_RLS' || tenant.role !== currentRole ||
              tenant.tenant_id !== state.currentTenantId) throw new Error('Contexto de dados inválido');
          if (active) setServerResult({ scope, status: 'ready', tenant });
        });
    task.catch(() => {
      if (active) setServerResult({ scope, status: 'error',
        error: 'Não foi possível consultar o PostgreSQL. Nenhum dado demonstrativo será apresentado como real.' });
    });
    return () => { active = false; };
  }, [scope]);
  const currentResult: Result = serverResult.scope === scope
    ? serverResult : { scope, status: 'loading' };
  if (currentResult.status !== 'ready') {
    return (
      <section className="rounded-2xl border border-slate-300 bg-white p-6" role="status">
        <h2 className="text-lg font-bold">Painel {currentRole === 'MASTER' ? 'Master SaaS' : 'da Caixinha'}</h2>
        <p className="mt-2 text-sm text-slate-700">
          {currentResult.status === 'error' ? currentResult.error : 'Consultando dados autorizados no PostgreSQL...'}
        </p>
      </section>
    );
  }
  if (currentRole !== 'MASTER') {
    const data = currentResult.tenant!;
    const metrics = [
      { label: 'Cotas visíveis', value: data.quota_count_visible },
      { label: 'Contribuições visíveis', value: data.contribution_count_visible },
      { label: 'Empréstimos visíveis', value: data.loan_count_visible },
      ...(currentRole === 'TENANT_ADMIN' ? [{
        label: 'Membros ativos da caixinha', value: data.member_count_visible ?? 0,
      }] : []),
    ];
    return (
      <section className="space-y-5">
        <div className="rounded-xl border border-slate-300 bg-white p-5">
          <h2 className="text-lg font-bold text-slate-900">
            {currentRole === 'TENANT_ADMIN' ? 'Painel do Administrador' : 'Meu Painel'}
          </h2>
          <p className="mt-1 text-sm text-slate-700">
            Dados reais consultados pelo servidor com isolamento de perfil e caixinha.
            Nenhuma simulação de capital ou de Pix é apresentada como saldo confirmado.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map(metric => (
            <article key={metric.label} className="rounded-xl border border-slate-200 bg-white p-5">
              <h3 className="text-sm text-slate-600">{metric.label}</h3>
              <p className="mt-2 text-3xl font-bold text-slate-900">{metric.value}</p>
            </article>
          ))}
        </div>
        <p className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          Movimentações financeiras reais ainda dependem de autorização, conciliação bancária
          e testes completos. Nenhuma movimentação foi realizada nesta consulta.
        </p>
        <div className="flex flex-wrap gap-3">
          <button type="button" onClick={() => onNavigateTab('CONTRIBUICOES')}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
            Consultar contribuições
          </button>
          {currentRole === 'TENANT_ADMIN' && <button type="button"
            onClick={() => onNavigateTab('MEMBROS')}
            className="rounded-lg bg-indigo-900 px-4 py-2 text-sm font-semibold text-white">
            Consultar membros
          </button>}
        </div>
      </section>
    );
  }

  const currentTenant = state.tenants.find(t => t.id === state.currentTenantId);
  const currentPolicy = state.policies.find(p => p.tenant_id === state.currentTenantId && p.status === 'ACTIVE');
  const currentSub = state.subscriptions.find(s => s.tenant_id === state.currentTenantId);
  const currentPlan = state.plans.find(p => p.tier === currentSub?.plan_tier);

  // Totais do tenant
  const cashAcc = state.ledgerAccounts.find(a => a.tenant_id === state.currentTenantId && a.account_code === '1.1.1');
  const creditAcc = state.ledgerAccounts.find(a => a.tenant_id === state.currentTenantId && a.account_code === '1.2.1');
  const capitalAcc = state.ledgerAccounts.find(a => a.tenant_id === state.currentTenantId && a.account_code === '2.1.1');
  const profitAcc = state.ledgerAccounts.find(a => a.tenant_id === state.currentTenantId && a.account_code === '4.1.1');
  const reserveAcc = state.ledgerAccounts.find(a => a.tenant_id === state.currentTenantId && a.account_code === '2.2.1');

  const cashBalance = cashAcc ? cashAcc.balance_cents / 100 : 0;
  const creditOutstanding = creditAcc ? creditAcc.balance_cents / 100 : 0;
  const capitalConfirmed = capitalAcc ? capitalAcc.balance_cents / 100 : 0;
  const profitRealized = profitAcc ? profitAcc.balance_cents / 100 : 0;
  const reservedAmount = reserveAcc ? reserveAcc.balance_cents / 100 : 0;
  const freeCash = Math.max(0, cashBalance - reservedAmount);

  // Membros e cotas ativas
  const activeMembers = state.memberships.filter(m => m.tenant_id === state.currentTenantId && m.status === 'ATIVA');
  const activeQuotas = state.quotas.filter(q => q.tenant_id === state.currentTenantId && q.status === 'ATIVA');

  // Dados do membro conectado (se for TENANT_MEMBER)
  const currentMember = state.memberships.find(
    m => m.tenant_id === state.currentTenantId && m.user_id === state.currentUserId
  );
  const myQuotas = state.quotas.filter(
    q => q.tenant_id === state.currentTenantId && q.membership_id === currentMember?.id && q.status === 'ATIVA'
  );
  const myContributions = state.contributions.filter(
    c => c.tenant_id === state.currentTenantId && c.membership_id === currentMember?.id
  );
  const nextContribution = myContributions.find(c => c.payment_status !== 'QUITADA');
  const myActiveLoan = state.loans.find(
    l => l.tenant_id === state.currentTenantId && l.borrower_membership_id === currentMember?.id && l.status === 'DESEMBOLSADO'
  );

  // Status de autorização anual para crédito próprio do admin
  const selfConsent = state.adminSelfConsents.find(c => c.tenant_id === state.currentTenantId);

  // O painel Master existente usa apenas inventário cadastral autorizado do servidor.
  if (currentRole === 'MASTER') {
    const masterData = currentResult.master!;
    const totalTenants = masterData.total_tenants;

    return (
      <div className="space-y-6">
        {/* Master Alert Bar */}
        <div className="p-4 rounded-2xl bg-indigo-900/40 border border-indigo-700/50 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-300 flex items-center justify-center">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-bold text-white text-sm">Painel Central do Proprietário (Master)</h3>
              <p className="text-xs text-indigo-200">
                Supervisão de Licenças e Operação Técnica • Sem acesso financeiro ou Pix das caixinhas (Cláusula 2.8)
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onNavigateTab('LICENCAS')}
              className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold cursor-pointer shadow-xs"
            >
              Gerenciar Preços e Licenças
            </button>
            <button
              onClick={() => onNavigateTab('SUPORTE')}
              className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold cursor-pointer border border-slate-700"
            >
              Suporte & Break-Glass
            </button>
          </div>
        </div>

        {/* Master Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xs">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Receita da Plataforma (SaaS)</span>
            <div className="text-2xl font-black text-emerald-400 mt-2">Não integrado</div>
            <p className="text-[11px] text-slate-400 mt-1">Cobranças de licenças ainda sem registro conciliado no servidor</p>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xs">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Caixinhas cadastradas</span>
            <div className="text-2xl font-black text-white mt-2">{totalTenants}</div>
            <p className="text-[11px] text-slate-400 mt-1">Assinaturas SaaS ainda não persistidas</p>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xs">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Preço Essencial Vigente</span>
            <div className="text-2xl font-black text-white mt-2">
              Catálogo demonstrativo
            </div>
            <p className="text-[11px] text-emerald-400 mt-1">Preços não vinculados a cobrança real</p>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xs">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Demonstrador Regulatório</span>
            <div className="text-2xl font-black text-amber-400 mt-2">Bolões CAIXA</div>
            <p className="text-[11px] text-amber-300/80 mt-1">Demonstração sem dinheiro real (Seção 14)</p>
          </div>
        </div>

        {/* Multi-Cloud Soberana OCI + GCP & Mobile Status */}
        <div className="bg-gradient-to-r from-slate-900 via-slate-850 to-indigo-950/80 border border-slate-700/80 rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4 text-white shadow-md">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center font-bold text-xs">
              <Cloud className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="font-bold text-sm text-white">Infraestrutura Multi-Cloud Soberana (GCP + OCI)</h4>
                <span className="text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                  Infraestrutura em demonstração
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                Topologia ilustrativa. Não há medição verificada de disponibilidade, RPO, RTO ou integridade WORM.
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigateTab('NUVEM')}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold cursor-pointer shadow-xs transition-colors flex items-center gap-1.5"
          >
            <Cloud className="w-3.5 h-3.5 text-cyan-300" />
            <span>Ver Topologia Multi-Cloud</span>
          </button>
        </div>

        {/* Lista de Caixinhas Contratadas */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-bold text-white text-sm flex items-center gap-2">
              <Building className="w-4 h-4 text-emerald-400" />
              <span>Caixinhas Clientes e Capacidade Agregada</span>
            </h4>
            <span className="text-xs text-slate-400">Dados cadastrais e técnicos minimizados (LGPD)</span>
          </div>

          <div className="space-y-3">
            {masterData.tenants.length === 0 && (
              <p className="text-sm text-slate-300">Nenhuma caixinha cadastrada no PostgreSQL.</p>
            )}
            {masterData.tenants.map(t => (
              <div key={t.id} className="rounded-xl border border-slate-700 bg-slate-800/60 p-4">
                <strong className="text-sm text-white">{t.display_name}</strong>
                <p className="mt-1 text-xs text-slate-300">
                  Situação: {t.status} {t.is_owner_box ? ' • Caixinha inaugural' : ''}
                </p>
              </div>
            ))}
            {masterData.has_more && (
              <p className="text-xs text-slate-300">Mostrando os primeiros 200 registros. Total: {totalTenants}.</p>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Se o usuário for TENANT_ADMIN
  if (currentRole === 'TENANT_ADMIN') {
    return (
      <div className="space-y-6">
        {/* Banner com Identificação e Políticas Inaugurais */}
        <div className="p-5 rounded-2xl bg-gradient-to-r from-emerald-950/90 via-slate-900 to-teal-950/80 border border-emerald-800/40 shadow-sm flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-lg font-extrabold text-white">{currentTenant?.display_name}</h2>
              {currentTenant?.is_owner_box && (
                <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                  Caixinha Inaugural do Proprietário (Cláusula 4.2)
                </span>
              )}
            </div>
            <p className="text-xs text-emerald-200/80 mt-1">
              Taxa: <strong>{(currentPolicy?.monthly_interest_rate || 0.20) * 100}% a.m.</strong> • Sistema: <strong>Price</strong> • Até <strong>{currentPolicy?.max_installments} parcelas</strong> • Split: <strong>{currentPolicy?.member_pct}% Membros / {currentPolicy?.admin_pct}% Administrador</strong>
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onNavigateTab('EMPRESTIMOS')}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold cursor-pointer shadow-md shadow-emerald-600/20 transition-all flex items-center gap-1.5"
            >
              <ArrowUpRight className="w-4 h-4" />
              <span>Gerenciar Empréstimos</span>
            </button>
            <button
              onClick={() => onNavigateTab('LEDGER')}
              className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold cursor-pointer border border-slate-700 transition-colors"
            >
              Ver Livro-Razão
            </button>
          </div>
        </div>

        {/* 4 Cards Financeiros Centrais */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Caixa Financeiro */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>Caixa Reconciliado</span>
              <Wallet className="w-4 h-4 text-emerald-600" />
            </div>
            <div className="text-2xl font-black text-slate-900 mt-2">{formatBRL(cashBalance)}</div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500 border-t border-slate-100 pt-2">
              <span>Saldo livre para crédito:</span>
              <strong className="text-emerald-700 font-bold">{formatBRL(freeCash)}</strong>
            </div>
          </div>

          {/* Capital Confirmado */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>Capital dos Membros</span>
              <Users className="w-4 h-4 text-blue-600" />
            </div>
            <div className="text-2xl font-black text-slate-900 mt-2">{formatBRL(capitalConfirmed)}</div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500 border-t border-slate-100 pt-2">
              <span>Cotas ativas:</span>
              <strong className="text-slate-800">{activeQuotas.length} cotas (R$ {currentPolicy?.contribution_per_quota.toFixed(2)}/cota)</strong>
            </div>
          </div>

          {/* Saldo Devedor em Aberto */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>Crédito Concedido</span>
              <TrendingUp className="w-4 h-4 text-amber-600" />
            </div>
            <div className="text-2xl font-black text-slate-900 mt-2">{formatBRL(creditOutstanding)}</div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500 border-t border-slate-100 pt-2">
              <span>Principal ativo:</span>
              <strong className="text-slate-800">{state.loans.filter(l => l.status === 'DESEMBOLSADO').length} empréstimo(s)</strong>
            </div>
          </div>

          {/* Lucro Realizado Acumulado */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <span>Lucro Realizado</span>
              <Percent className="w-4 h-4 text-teal-600" />
            </div>
            <div className="text-2xl font-black text-slate-900 mt-2">{formatBRL(profitRealized)}</div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500 border-t border-slate-100 pt-2">
              <span>Provisão rateio ({currentPolicy?.member_pct}%):</span>
              <strong className="text-teal-700 font-bold">{formatBRL(profitRealized * ((currentPolicy?.member_pct || 85) / 100))}</strong>
            </div>
          </div>
        </div>

        {/* Alertas Operacionais e Verificações */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Card 1: Autorização de Autoempréstimo */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>Autoempréstimo do Administrador</span>
              </h4>
              <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                selfConsent?.status === 'ATIVO' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
              }`}>
                {selfConsent?.status}
              </span>
            </div>
            <p className="text-xs text-slate-600">
              Cláusula 2.5: Para o administrador tomar empréstimo próprio, exige-se autorização anual unânime dos demais membros ativos.
            </p>
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-xs text-slate-700 space-y-1">
              <div className="flex justify-between">
                <span>Signatários ativos:</span>
                <strong>{selfConsent?.signatures.filter(s => !s.revoked_at).length} de {activeMembers.length - 1} membros</strong>
              </div>
              <div className="flex justify-between">
                <span>Validade:</span>
                <span>Ciclo 2027 (até 31/12/2027)</span>
              </div>
            </div>
            <button
              onClick={() => onNavigateTab('CONSENTIMENTO')}
              className="w-full py-2 bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs rounded-xl transition-colors cursor-pointer"
            >
              Verificar Assinaturas Coletivas
            </button>
          </div>

          {/* Card 2: Capacidade da Licença */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                <Users className="w-4 h-4 text-blue-600" />
                <span>Capacidade Licenciada</span>
              </h4>
              <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
                {currentPlan?.name}
              </span>
            </div>
            <p className="text-xs text-slate-600">
              Contagem simultânea de membros e cotas em uso ativo (Cláusula 3.4). Convites pendentes não consomem vaga.
            </p>
            <div className="space-y-2">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-600">Membros em uso:</span>
                  <span className="font-bold text-slate-900">{activeMembers.length} / {currentPlan?.member_limit}</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${(activeMembers.length / (currentPlan?.member_limit || 20)) * 100}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-600">Cotas em uso:</span>
                  <span className="font-bold text-slate-900">{activeQuotas.length} / {currentPlan?.quota_limit}</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-emerald-600 h-2 rounded-full"
                    style={{ width: `${(activeQuotas.length / (currentPlan?.quota_limit || 40)) * 100}%` }}
                  />
                </div>
              </div>
            </div>
            <button
              onClick={() => onNavigateTab('MEMBROS')}
              className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 font-medium text-xs rounded-xl transition-colors cursor-pointer"
            >
              Convidar Novo Membro
            </button>
          </div>

          {/* Card 3: Próximos Vencimentos */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-600" />
                <span>Próximo Vencimento Central</span>
              </h4>
              <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
                Dia 10 Mensal
              </span>
            </div>
            <p className="text-xs text-slate-600">
              Vencimento uniforme de contribuições e parcelas de empréstimos em todo dia 10.
            </p>
            <div className="p-3 rounded-xl bg-amber-50/60 border border-amber-200/80 text-xs text-amber-950 space-y-1.5">
              <div className="flex justify-between font-medium">
                <span>Próxima data:</span>
                <strong className="text-amber-900 font-bold">10/03/2027</strong>
              </div>
              <div className="flex justify-between">
                <span>Pendências a receber:</span>
                <span>{state.contributions.filter(c => c.due_status === 'VENCIDA').length} contribuição(ões) em atraso</span>
              </div>
            </div>
            <button
              onClick={() => onNavigateTab('CONTRIBUICOES')}
              className="w-full py-2 bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs rounded-xl transition-colors cursor-pointer"
            >
              Conferir Obrigações do Ciclo
            </button>
          </div>
        </div>

        {/* Banner Especial: Módulo de Rifas (Proposta Consolidada) */}
        <div className="bg-gradient-to-r from-indigo-900/90 via-slate-900 to-indigo-950 border border-indigo-700/60 rounded-2xl p-5 text-white flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-400 flex items-center justify-center font-bold">
              <Ticket className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-amber-300 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                  Módulo de Rifas Homologado
                </span>
                <span className="text-[11px] text-slate-400">3 Campanhas Anuais (Mar/Jun/Set)</span>
              </div>
              <h4 className="text-base font-extrabold text-white mt-1">
                Campanhas Vinculadas às Cotas Ativas • 10 Bilhetes por Cota (R$ 50,00)
              </h4>
              <p className="text-xs text-slate-300 mt-0.5">
                Cartelas digitais geradas, premiação configurável via Pix e simulador de mora de 20%/mês.
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigateTab('RIFAS')}
            className="px-4 py-2.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs rounded-xl shadow-lg shadow-amber-500/20 transition-all cursor-pointer whitespace-nowrap"
          >
            Gerenciar Módulo de Rifas
          </button>
        </div>

        {/* Banner Novo: Módulo de Bolões Oficiais (Versão 1.1 - 30/10/2026) */}
        <div className="bg-gradient-to-r from-emerald-950 via-slate-900 to-indigo-950 border border-emerald-700/60 rounded-2xl p-5 text-white flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center font-bold">
              <Ticket className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-300 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                  Bolões Oficiais CAIXA (Autorizado)
                </span>
                <span className="text-[11px] text-slate-400">Quina • Lotofácil • Mega da Virada</span>
              </div>
              <h4 className="text-base font-extrabold text-white mt-1">
                Criação Integral de Jogos, Impressão do Roteiro e Rateio 96% / 4%
              </h4>
              <p className="text-xs text-slate-300 mt-0.5">
                Seleção de dezenas por jogo, conferência de recibos da lotérica e fórmula de 20% caixinha.
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigateTab('BOLOES')}
            className="px-4 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs rounded-xl shadow-lg shadow-emerald-500/20 transition-all cursor-pointer whitespace-nowrap"
          >
            Gerenciar Bolões Oficiais
          </button>
        </div>

        {/* Multi-Cloud OCI + GCP & Mobile Info Bar para Admin */}
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 text-white flex flex-wrap items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/20 text-cyan-400 flex items-center justify-center">
              <Cloud className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-xs">
              <span className="font-bold text-white">Nuvem Soberana Ativa: Google Cloud (SP) ⇄ Oracle Cloud (Vinhedo)</span>
              <p className="text-[11px] text-slate-400">
                Livro-Razão replicado em tempo real com imutabilidade WORM (Cláusula 14.2) • Suporte a Celular Android e iPhone.
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigateTab('NUVEM')}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-semibold rounded-lg border border-slate-700 cursor-pointer"
          >
            Conferir Nuvem OCI + GCP
          </button>
        </div>
      </div>
    );
  }

  // Se o usuário for TENANT_MEMBER
  return (
    <div className="space-y-6">
      {/* Banner Membro */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-emerald-900 via-slate-900 to-emerald-950 border border-emerald-800/40 text-white shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Painel do Membro Participante</span>
          <h2 className="text-2xl font-black text-white mt-1">Olá, {currentMember?.user_name}</h2>
          <p className="text-xs text-slate-300 mt-1">
            Caixinha: <strong>{currentTenant?.display_name}</strong> • Você possui <strong>{myQuotas.length} cota(s) ativas</strong>
          </p>
        </div>

        {nextContribution && (
          <button
            onClick={() =>
              onOpenPixModal({
                title: `Contribuição Mensal - Comp. ${nextContribution.competence}`,
                amount: nextContribution.amount_due - nextContribution.amount_paid,
                description: `Contribuição dia 10 de ${currentMember?.user_name}`,
                recipientName: currentTenant?.display_name || 'Caixinha',
                referenceId: nextContribution.id,
                onConfirm: () =>
                  appStore.registerContributionPayment(
                    nextContribution.id,
                    nextContribution.amount_due - nextContribution.amount_paid
                  ),
              })
            }
            className="px-5 py-3 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs rounded-xl shadow-lg shadow-emerald-500/20 cursor-pointer flex items-center gap-2"
          >
            <Wallet className="w-4 h-4" />
            <span>Pagar Próxima Contribuição Pix</span>
          </button>
        )}
      </div>

      {/* Cards de Direitos e Posição do Membro */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Meu Capital Confirmado */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Meu Capital Confirmado</span>
          <div className="text-2xl font-black text-slate-900 mt-2">
            {formatBRL(myContributions.reduce((acc, c) => acc + c.amount_paid, 0))}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Capital próprio efetivamente conciliado e preservado</p>
        </div>

        {/* Minha Situação de Elegibilidade */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Elegibilidade para Lucro</span>
          <div className="flex items-center gap-2 mt-2">
            <span
              className={`text-lg font-bold px-3 py-0.5 rounded-full ${
                currentMember?.is_profit_eligible
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-rose-100 text-rose-800'
              }`}
            >
              {currentMember?.is_profit_eligible ? 'Elegível no Ciclo' : 'Bloqueado (Cláusula 6.5)'}
            </span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            {currentMember?.is_profit_eligible
              ? 'Adimplente; participa do rateio anual Capital-Dias V2'
              : 'Três meses em atraso acarretaram perda do lucro deste ciclo'}
          </p>
        </div>

        {/* Empréstimo em Aberto */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Meu Empréstimo Ativo</span>
          {myActiveLoan ? (
            <div>
              <div className="text-2xl font-black text-amber-600 mt-2">
                {formatBRL(
                  myActiveLoan.installments
                    .filter(i => i.status !== 'QUITADA')
                    .reduce((acc, i) => acc + i.principal_due, 0)
                )}
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                {myActiveLoan.installments.filter(i => i.status === 'QUITADA').length} de {myActiveLoan.term_months} parcelas pagas
              </p>
            </div>
          ) : (
            <div>
              <div className="text-lg font-bold text-slate-400 mt-2">Nenhum crédito ativo</div>
              <p className="text-[11px] text-slate-500 mt-1">Você pode simular empréstimos a qualquer momento</p>
            </div>
          )}
        </div>
      </div>

      {/* Ações Rápidas do Membro */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs flex items-center justify-between">
          <div>
            <h4 className="font-bold text-slate-900 text-sm">Precisa de Crédito Interno?</h4>
            <p className="text-xs text-slate-600 mt-0.5">
              Simule sob tabela Price e prazos dentro do ciclo anual de 2027.
            </p>
          </div>
          <button
            onClick={() => onNavigateTab('MEU_EMPRESTIMO')}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs rounded-xl cursor-pointer"
          >
            Simular Empréstimo
          </button>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs flex items-center justify-between">
          <div>
            <h4 className="font-bold text-slate-900 text-sm">Termo de Anuência para o Administrador</h4>
            <p className="text-xs text-slate-600 mt-0.5">
              Consulte e assine ou revogue a autorização anual para crédito do admin (Cláusula 2.5).
            </p>
          </div>
          <button
            onClick={() => onNavigateTab('AUTORIZACAO_ADMIN')}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl cursor-pointer"
          >
            Ver Termo Anual
          </button>
        </div>
      </div>

      {/* Banner de Rifas do Membro */}
      <div className="bg-gradient-to-r from-slate-900 to-indigo-950 border border-indigo-800/60 rounded-2xl p-5 text-white flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold">
            <Ticket className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-bold text-amber-400 uppercase tracking-wider">
              Minhas Cartelas Digitais de Rifa
            </span>
            <h4 className="text-base font-extrabold text-white mt-0.5">
              Suas Cartelas e 10 Bilhetes por Cota (R$ 5,00 cada)
            </h4>
            <p className="text-xs text-slate-300 mt-0.5">
              Consulte os números da sua cota, cadastre compradores ou pague sua cota via Pix para evitar mora.
            </p>
          </div>
        </div>
        <button
          onClick={() => onNavigateTab('MINHAS_RIFAS')}
          className="px-4 py-2.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs rounded-xl shadow-md transition-all cursor-pointer whitespace-nowrap"
        >
          Acessar Minhas Cartelas
        </button>
      </div>

      {/* Banner de Bolões do Membro */}
      <div className="bg-gradient-to-r from-emerald-950 via-slate-900 to-indigo-950 border border-emerald-800/60 rounded-2xl p-5 text-white flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold">
            <Ticket className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
              Meus Bolões Oficiais da CAIXA
            </span>
            <h4 className="text-base font-extrabold text-white mt-0.5">
              Suas Participações em Bolões Oficiais (Quina, Lotofácil e Mega da Virada)
            </h4>
            <p className="text-xs text-slate-300 mt-0.5">
              Consulte seus jogos, dezenas registradas na lotérica, comprovantes e direito a 96% do prêmio apurado.
            </p>
          </div>
        </div>
        <button
          onClick={() => onNavigateTab('MEUS_BOLOES')}
          className="px-4 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs rounded-xl shadow-md transition-all cursor-pointer whitespace-nowrap"
        >
          Acessar Meus Bolões
        </button>
      </div>

      {/* Multi-Cloud & Segurança para o Membro */}
      <div className="p-4 rounded-2xl bg-white border border-slate-200 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center">
            <Cloud className="w-4 h-4 text-emerald-700" />
          </div>
          <div className="text-xs">
            <span className="font-bold text-slate-900">Seus Dados Protegidos por Arquitetura Multi-Cloud Soberana</span>
            <p className="text-[11px] text-slate-500">
              Registros imutáveis com custódia inviolável na Oracle Cloud (Vinhedo) e Google Cloud (São Paulo).
            </p>
          </div>
        </div>
        <button
          onClick={() => onNavigateTab('NUVEM')}
          className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 cursor-pointer"
        >
          Conhecer a Nuvem Soberana
        </button>
      </div>
    </div>
  );
};
