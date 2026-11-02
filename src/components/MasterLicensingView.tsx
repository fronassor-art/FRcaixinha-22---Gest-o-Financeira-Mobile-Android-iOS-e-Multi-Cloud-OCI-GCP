import React, { useEffect, useState } from 'react';
import { financialApi } from '../services/financialApiService';
import {
  ShieldCheck,
  CreditCard,
  Edit3,
  CheckCircle2,
  Lock,
  AlertTriangle,
  ArrowRight,
  TrendingUp,
  Percent,
  Calendar,
  Layers
} from 'lucide-react';
import { AppState, appStore } from '../services/store';
import { formatBRL, formatDateBR, calculateLicenseUpgradeProRata, roundCents } from '../services/financialEngine';
import { LicensePlanTier } from '../types';

interface MasterLicensingViewProps {
  state: AppState;
  onOpenPixModal: (params: {
    title: string;
    amount: number;
    description: string;
    recipientName: string;
    referenceId: string;
    onConfirm: () => void;
  }) => void;
}

export const MasterLicensingView: React.FC<MasterLicensingViewProps> = ({ state, onOpenPixModal }) => {
  const currentRole = state.currentRole;
  const isMaster = currentRole === 'MASTER';
  const [catalog, setCatalog] = useState<Awaited<ReturnType<typeof financialApi.fetchMasterLicenses>> | null>(null);
  const [catalogStatus, setCatalogStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    if (!isMaster) return () => { active = false; };
    setCatalog(null);
    setCatalogStatus('loading');
    financialApi.fetchMasterLicenses().then(result => {
      if (result.source !== 'POSTGRESQL_RLS') throw new Error('Fonte inválida');
      if (active) { setCatalog(result); setCatalogStatus('ready'); }
    }).catch(() => {
      if (active) { setCatalog(null); setCatalogStatus('error'); }
    });
    return () => { active = false; };
  }, [isMaster, state.currentUserId, revision]);


  type PrepItem = { id: string; plan_tier: string; billing_period: string;
    status: string; created_at: string; tenant_id?: string };
  type PrepStatus = { key: string; status: 'loading' | 'ready' | 'error';
    preparations: PrepItem[] };
  const prepScope = [state.currentUserId, currentRole, state.currentTenantId].join(':');
  const [subscriptionPreps, setSubscriptionPreps] = useState<PrepStatus>({
    key: '', status: 'loading', preparations: [],
  });
  useEffect(() => {
    let active = true;
    setSubscriptionPreps({ key: prepScope, status: 'loading', preparations: [] });
    const call = currentRole === 'MASTER'
      ? financialApi.fetchMasterSubscriptionPreparations()
      : currentRole === 'TENANT_ADMIN' && state.currentTenantId
        ? financialApi.fetchTenantLicensePreparation(state.currentTenantId)
        : null;
    if (!call) {
      setSubscriptionPreps({ key: prepScope, status: 'ready', preparations: [] });
      return () => { active = false; };
    }
    call.then(response => {
      if (response.source !== 'POSTGRESQL_RLS' ||
          response.billing_status !== 'NO_PROVIDER_NO_FINANCIAL_ACTIVATION' ||
          ('tenant_id' in response && response.tenant_id !== state.currentTenantId)) {
        throw new Error('Fonte ou contexto SaaS inválido');
      }
      if (active) setSubscriptionPreps({ key: prepScope, status: 'ready',
        preparations: response.preparations });
    }).catch(() => {
      if (active) setSubscriptionPreps({ key: prepScope, status: 'error', preparations: [] });
    });
    return () => { active = false; };
  }, [prepScope, revision]);
  const prepCurrent: PrepStatus = subscriptionPreps.key === prepScope
    ? subscriptionPreps
    : { key: prepScope, status: 'loading', preparations: [] };

  type SaasStatus = { key: string; status: 'loading' | 'ready' | 'error';
    payments: Array<{id:string;status:string;expected_amount_cents:number}>;
    licenses: Array<{id:string;plan_tier:string;status:string;effective_status:string;valid_until:string}> };
  const saasScope = [state.currentUserId,currentRole,state.currentTenantId].join(':');
  const [billing, setBilling] = useState<SaasStatus>({
    key:'',status:'loading',payments:[],licenses:[],
  });
  useEffect(() => {
    let active = true;
    setBilling({key:saasScope,status:'loading',payments:[],licenses:[]});
    const request = currentRole==='MASTER'
      ? financialApi.fetchMasterSaasPaymentStatus()
      : currentRole==='TENANT_ADMIN' && state.currentTenantId
        ? financialApi.fetchTenantSaasPaymentStatus(state.currentTenantId)
        : null;
    if (!request) {
      setBilling({key:saasScope,status:'ready',payments:[],licenses:[]});
      return () => {active=false;};
    }
    request.then(result => {
      if (result.source !== 'POSTGRESQL_RLS' ||
          ('tenant_id' in result && result.tenant_id !== state.currentTenantId)) {
        throw new Error('Contexto SaaS inválido');
      }
      if (active) setBilling({key:saasScope,status:'ready',
        payments:result.payments,licenses:result.licenses});
    }).catch(() => {
      if (active) setBilling({key:saasScope,status:'error',payments:[],licenses:[]});
    });
    return () => {active=false;};
  }, [saasScope,revision]);
  const currentBilling: SaasStatus = billing.key===saasScope ? billing :
    {key:saasScope,status:'loading',payments:[],licenses:[]};

  // Edição de Preço pelo Master (Cláusula 3.2-A / AT-24 / AT-25)
  const [editingTier, setEditingTier] = useState<LicensePlanTier | null>(null);
  const [newMonthlyPrice, setNewMonthlyPrice] = useState<number>(89.90);
  const [changeReason, setChangeReason] = useState<string>('Reajuste comercial anual');

  // Simulador de Upgrade Pro-Rata
  const [upgradeTier, setUpgradeTier] = useState<LicensePlanTier>('INTERMEDIARIO');

  const currentSub = state.subscriptions.find(s => s.tenant_id === state.currentTenantId);

  const handleSavePrice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTier || editingTier === 'AMPLIADO' || !isMaster) return;
    try {
      const response = await financialApi.updateMasterLicensePrice(editingTier, newMonthlyPrice, changeReason);
      if (response.status !== 'VERSION_PERSISTED_NO_BILLING') throw new Error('Persistência não confirmada');
      setEditingTier(null);
      setRevision(n => n + 1);
      alert('Nova versão de preço registrada no PostgreSQL. Nenhuma cobrança ou assinatura foi alterada.');
    } catch {
      alert('Não foi possível registrar o preço no servidor. Nenhum sucesso foi declarado.');
    }
  };

  // Preços lidos exclusivamente do backend PostgreSQL; nunca de seeds locais.
  const prices = catalog?.plans.map(p => ({
    ...p,
    plan_tier: p.tier,
    monthly_price: p.monthly_price ? Number(p.monthly_price) : 0,
    annual_price_computed: p.annual_price_computed ? Number(p.annual_price_computed) : 0,
  })) || [];
  const currentEssencialPrice = prices.find(p => p.tier === 'ESSENCIAL');
  const currentInterPrice = prices.find(p => p.tier === 'INTERMEDIARIO');
  const currentAmpPrice = prices.find(p => p.tier === 'AMPLIADO');

  if (!isMaster) {
    return <section role="status" className="rounded-xl border border-amber-300 bg-white p-5">
      <h2 className="text-lg font-bold">Licença SaaS da caixinha</h2>
      {currentRole !== 'TENANT_ADMIN' ? (
        <p className="mt-2 text-sm text-slate-700">
          Informações comerciais são restritas ao administrador contratante.
        </p>
      ) : prepCurrent.status !== 'ready' ? (
        <p className="mt-2 text-sm text-slate-700">
          {prepCurrent.status === 'loading' ? 'Consultando o PostgreSQL...' :
            'Não foi possível consultar a licença. Nenhum status fictício será exibido.'}
        </p>
      ) : (
        <>
          <p className="mt-2 text-sm text-slate-700">
            {prepCurrent.preparations.length} preparação(ões) documentais visíveis.
            Nenhuma representa licença ativa ou pagamento conciliado.
          </p>
          {prepCurrent.preparations.map(p => (
            <p key={p.id} className="mt-2 text-sm text-slate-700">
              {p.plan_tier} • {p.billing_period} • {p.status}
            </p>
          ))}
        </>
      )}
      <div className="mt-4 rounded-xl border border-slate-200 p-3 text-sm text-slate-800">
        <strong>Status SaaS validado pelo servidor</strong>
        {currentBilling.status==='ready' ? (
          <p className="mt-1">
            {currentBilling.payments.length} cobrança(s) registrada(s),
            {' '}{currentBilling.licenses.filter(l => l.effective_status==='ACTIVE').length} licença(s) ativa(s).
            {currentBilling.licenses.map(l => (
              <span key={l.id} className="block">
                {l.plan_tier} • {l.effective_status} • validade {l.valid_until}
              </span>
            ))}
          </p>
        ) : <p className="mt-1 text-amber-950">
          {currentBilling.status==='loading' ? 'Consultando registros...' :
          'Consulta indisponível. Nenhuma licença será presumida ativa.'}
        </p>}
      </div>
      <p className="mt-3 text-xs text-amber-950">
        Novas contratações, pagamentos e ativações continuam desabilitados
        até autorização e integração real dos provedores.
      </p>
    </section>;
  }

  if (catalogStatus !== 'ready') {
    return <section role="status" className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-lg font-bold">Licenças e Preços — Master</h2>
      <p className="mt-2 text-sm">
        {catalogStatus === 'error'
          ? 'Catálogo do PostgreSQL indisponível. Não é permitido editar preços simulados.'
          : 'Carregando preços registrados no servidor...'}
      </p>
      <button type="button" onClick={() => setRevision(n => n + 1)}
        className="mt-3 rounded-lg border px-4 py-2">Tentar novamente</button>
    </section>;
  }

  // Cálculo pro-rata se for admin simulando upgrade
  const upgradeProRata = calculateLicenseUpgradeProRata(
    89.90, // De Essencial
    109.90, // Para Intermediário
    new Date('2026-10-16'),
    new Date('2027-10-16'),
    new Date()
  );

  return (
    <div className="space-y-6">
      {/* Header com Regras Comerciais */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Planos e Licenciamento SaaS da Plataforma</h2>
            <span className="text-[11px] font-semibold bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full">
              Tolerância ZERO DIAS • Cláusula 3.8
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-1">
            Receitas de licença são exclusivas da plataforma e segregadas do dinheiro dos membros (Cláusula 1.7 e 3.11). O valor anual é rigorosamente <strong>10 × valor mensal</strong> (2 meses de desconto).
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs bg-slate-100 px-3 py-1.5 rounded-xl text-slate-700">
          <Calendar className="w-4 h-4 text-emerald-600" />
          <span>Fuso Oficial: <strong>America/Belem</strong> (Dia Âncora Preservado)</span>
        </div>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 text-sm">
        <h3 className="font-bold text-slate-900">Preparações de licenças — dados PostgreSQL</h3>
        {prepCurrent.status === 'ready' ? (
          <p className="mt-1 text-slate-700">
            {prepCurrent.preparations.length} preparação(ões) no inventário consultado.
            Nenhuma é pagamento, renovação conciliada ou licença ativada.
          </p>
        ) : (
          <p className="mt-1 text-amber-950">
            {prepCurrent.status === 'loading' ? 'Consultando o servidor...' :
              'Consulta SaaS indisponível; não mostrar assinaturas demonstrativas.'}
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 text-sm">
        <h3 className="font-bold text-slate-900">Cobranças e licenças — PostgreSQL</h3>
        {currentBilling.status==='ready' ? (
          <p className="mt-1 text-slate-700">
            {currentBilling.payments.length} cobrança(s) persistida(s) e
            {' '}{currentBilling.licenses.filter(l => l.effective_status==='ACTIVE').length} licença(s) ativa(s).
            Nenhum registro financeiro é inferido a partir de dados locais de demonstração.
          </p>
        ) : <p className="mt-1 text-amber-950">
          {currentBilling.status==='loading' ? 'Consultando o servidor...' :
            'Status não confirmado pelo servidor.'}
        </p>}
      </section>

      {/* Grid dos 3 Planos Oficiais */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* 1. Plano Essencial */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-col justify-between space-y-4 relative">
          <div>
            <div className="flex justify-between items-start">
              <div>
                <span className="text-[10px] font-bold text-emerald-700 uppercase tracking-wider bg-emerald-50 px-2 py-0.5 rounded-md">
                  Pequenos Grupos
                </span>
                <h3 className="text-lg font-extrabold text-slate-900 mt-1.5">Plano Essencial</h3>
              </div>
              <span className="text-xs font-bold bg-slate-100 text-slate-800 px-2 py-0.5 rounded-full">
                20 / 40
              </span>
            </div>

            <div className="mt-4">
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-black text-slate-900">
                  {formatBRL(currentEssencialPrice?.monthly_price || 0)}
                </span>
                <span className="text-xs text-slate-500">/mês</span>
              </div>
              <div className="text-xs text-emerald-700 font-semibold mt-1">
                Anual: {formatBRL(currentEssencialPrice?.annual_price_computed || 0)} / ano (10x mensal)
              </div>
            </div>

            <div className="mt-5 space-y-2 text-xs text-slate-600">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>Até <strong>20 membros</strong> ativos</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>Até <strong>40 cotas</strong> simultâneas</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>Motor Price & Capital-Dias V2</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>Conciliação Pix Mercado Pago</span>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100">
            {isMaster ? (
              <button
                onClick={() => {
                  setEditingTier('ESSENCIAL');
                  setNewMonthlyPrice(currentEssencialPrice?.monthly_price || 0);
                }}
                className="w-full py-2 bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs rounded-xl cursor-pointer flex items-center justify-center gap-1.5"
              >
                <Edit3 className="w-3.5 h-3.5" />
                <span>Editar Preço Mensal (Master)</span>
              </button>
            ) : (
              <div className="text-center text-xs text-slate-500 py-2">Plano Básico Homologado</div>
            )}
          </div>
        </div>

        {/* 2. Plano Intermediário */}
        <div className="bg-white border-2 border-emerald-600 rounded-2xl p-6 shadow-md flex flex-col justify-between space-y-4 relative">
          <div className="absolute -top-3 right-5 bg-emerald-600 text-white text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
            Mais Escolhido
          </div>
          <div>
            <div className="flex justify-between items-start">
              <div>
                <span className="text-[10px] font-bold text-emerald-700 uppercase tracking-wider bg-emerald-50 px-2 py-0.5 rounded-md">
                  Médio Porte
                </span>
                <h3 className="text-lg font-extrabold text-slate-900 mt-1.5">Plano Intermediário</h3>
              </div>
              <span className="text-xs font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                50 / 50
              </span>
            </div>

            <div className="mt-4">
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-black text-slate-900">
                  {formatBRL(currentInterPrice?.monthly_price || 0)}
                </span>
                <span className="text-xs text-slate-500">/mês</span>
              </div>
              <div className="text-xs text-emerald-700 font-semibold mt-1">
                Anual: {formatBRL(currentInterPrice?.annual_price_computed || 0)} / ano (10x mensal)
              </div>
            </div>

            <div className="mt-5 space-y-2 text-xs text-slate-600">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>Até <strong>50 membros</strong> ativos</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>Até <strong>50 cotas</strong> simultâneas</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>Todas as funcionalidades habilitadas</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>Suporte técnico prioritário</span>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100">
            {isMaster ? (
              <button
                onClick={() => {
                  setEditingTier('INTERMEDIARIO');
                  setNewMonthlyPrice(currentInterPrice?.monthly_price || 0);
                }}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl cursor-pointer flex items-center justify-center gap-1.5 shadow-xs"
              >
                <Edit3 className="w-3.5 h-3.5" />
                <span>Editar Preço Mensal (Master)</span>
              </button>
            ) : (
              <div className="text-center text-xs font-bold text-emerald-700 py-2">Plano Contratado Atualmente</div>
            )}
          </div>
        </div>

        {/* 3. Plano Ampliado (Teto Pendente / Bloqueado) */}
        <div className="bg-slate-50/80 border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-col justify-between space-y-4 opacity-80">
          <div>
            <div className="flex justify-between items-start">
              <div>
                <span className="text-[10px] font-bold text-amber-800 uppercase tracking-wider bg-amber-100 px-2 py-0.5 rounded-md">
                  Teto Pendente
                </span>
                <h3 className="text-lg font-extrabold text-slate-700 mt-1.5">Plano Ampliado</h3>
              </div>
              <span className="text-xs font-bold bg-slate-200 text-slate-600 px-2 py-0.5 rounded-full flex items-center gap-1">
                <Lock className="w-3 h-3" />
                Bloqueado
              </span>
            </div>

            <div className="mt-4">
              <div className="flex items-baseline gap-1 text-slate-500">
                <span className="text-2xl font-bold">R$ 129,90</span>
                <span className="text-xs">/mês (indicativo)</span>
              </div>
              <div className="text-xs text-slate-500 mt-1">Anual: R$ 1.299,00 / ano</div>
            </div>

            <div className="mt-5 space-y-2 text-xs text-slate-500">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                <span>Acima de 50 membros (teto indefinido)</span>
              </div>
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                <span>Checkout desativado contratualmente</span>
              </div>
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                <span>Não promete capacidade ilimitada (Cláusula 3.3)</span>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-200/80">
            <button
              disabled
              className="w-full py-2 bg-slate-200 text-slate-500 font-bold text-xs rounded-xl cursor-not-allowed flex items-center justify-center gap-1.5"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Checkout Bloqueado</span>
            </button>
          </div>
        </div>
      </div>

      {/* Seção de Demonstração do Cálculo de Upgrade Pro-Rata (Cláusula 3.10) */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
        <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
          <Layers className="w-4 h-4 text-emerald-600" />
          <span>Simulador de Upgrade Pro-Rata Transparente (Cláusula 3.10 / AT-20)</span>
        </h3>
        <p className="text-xs text-slate-600">
          O cálculo do upgrade considera cada segmento de vigência já adquirido e não transcorrido pela fórmula:
          <code className="mx-1 px-1.5 py-0.5 bg-slate-100 rounded text-slate-800 font-mono text-[11px]">
            max(0, novo_preco - antigo_preco) × segundos_restantes / segundos_totais
          </code>.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs">
          <div>
            <span className="text-slate-500 block">Diferença de Valor:</span>
            <strong className="text-slate-900 font-mono text-sm">{formatBRL(upgradeProRata.priceDifference)}</strong>
          </div>
          <div>
            <span className="text-slate-500 block">Dias Restantes no Segmento:</span>
            <strong className="text-slate-900 font-mono text-sm">{upgradeProRata.daysRemaining} de {upgradeProRata.totalDays} dias</strong>
          </div>
          <div>
            <span className="text-slate-500 block">Valor Pro-Rata Devido:</span>
            <strong className="text-emerald-700 font-mono text-base font-extrabold">{formatBRL(upgradeProRata.proRataAmount)}</strong>
          </div>
          <div className="flex items-center">
            <span className="text-[11px] text-slate-500">
              Mantém <code>active_until</code> e o dia âncora original sem deriva temporal.
            </span>
          </div>
        </div>
      </div>

      {/* Modal de Edição de Preço pelo Master (Cláusula 3.2-A / AT-24 / AT-25) */}
      {editingTier && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-sm">Editar Preço Comercial - Plano {editingTier}</h3>
              <span className="text-[10px] font-mono text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded">
                Cláusula 3.2-A
              </span>
            </div>

            <form onSubmit={handleSavePrice} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Novo Valor Mensal (R$) <span className="text-emerald-600 font-normal">(Único campo editável)</span>
                </label>
                <input
                  type="number"
                  step="0.10"
                  min="1"
                  value={newMonthlyPrice}
                  onChange={e => setNewMonthlyPrice(Number(e.target.value))}
                  className="w-full text-lg font-bold px-3 py-2 border border-slate-300 rounded-lg text-slate-900"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-500 mb-1">
                  Valor Anual Calculado Automaticamente (R$) <span className="text-slate-400 font-normal">(Leitura obrigatória)</span>
                </label>
                <input
                  type="text"
                  readOnly
                  disabled
                  value={formatBRL(roundCents(newMonthlyPrice * 10))}
                  className="w-full text-base font-mono font-bold px-3 py-2 bg-slate-100 border border-slate-200 rounded-lg text-slate-600 cursor-not-allowed"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">
                  Regra AT-25: Proibido editar a anuidade diretamente; sempre 10 × mensalidade.
                </span>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Motivo do Reajuste Comercial</label>
                <input
                  type="text"
                  value={changeReason}
                  onChange={e => setChangeReason(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-800"
                />
              </div>

              <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-amber-900 text-[11px] leading-relaxed">
                Cada alteração cria uma <code>LicensePriceVersion</code> imutável. Assinaturas já pagas e ofertas em andamento não sofrem reajuste retroativo.
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingTier(null)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl cursor-pointer shadow-xs"
                >
                  Gravar Nova Versão de Preço
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
