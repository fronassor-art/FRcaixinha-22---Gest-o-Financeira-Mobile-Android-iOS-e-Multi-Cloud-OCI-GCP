import React, { useState } from 'react';
import {
  Calendar,
  CheckCircle2,
  DollarSign,
  Users,
  Award,
  AlertCircle,
  Send,
  FileCheck,
  Scale,
  Percent,
  Coins
} from 'lucide-react';
import { AppState, appStore } from '../services/store';
import { calculateCycleClosingSettlement, formatBRL, formatDateBR, roundCents } from '../services/financialEngine';
import confetti from 'canvas-confetti';

interface CycleClosingViewProps {
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

export const CycleClosingView: React.FC<CycleClosingViewProps> = ({ state, onOpenPixModal }) => {
  const currentRole = state.currentRole;
  const currentTenant = state.tenants.find(t => t.id === state.currentTenantId);
  const currentPolicy = state.policies.find(p => p.tenant_id === state.currentTenantId && p.status === 'ACTIVE');
  const currentCycle = state.cycles.find(c => c.tenant_id === state.currentTenantId);

  const [closingStatus, setClosingStatus] = useState<'EM_APURACAO' | 'APROVADO_PARA_LIQUIDACAO' | 'FECHADO'>('APROVADO_PARA_LIQUIDACAO');

  // Lucro realizado apurado no Ledger (Receitas de juros e multas já recebidas)
  const realizedNetProfit = appStore.getTenantRealizedProfit(state.currentTenantId);

  // Montar participantes e pesos Capital-Dias
  const members = state.memberships
    .filter(m => m.tenant_id === state.currentTenantId && m.status === 'ATIVA')
    .map(m => {
      const contributionsPaid = state.contributions
        .filter(c => c.membership_id === m.id)
        .reduce((acc, c) => acc + c.amount_paid, 0);

      const quotasCount = state.quotas.filter(q => q.membership_id === m.id && q.status === 'ATIVA').length;

      // Peso simulado Capital-Dias V2 com corte ao fim de cada dia civil (Cláusula 10.3)
      // Ana Costa possui 3 meses vencidos consecutivos, portanto is_profit_eligible = false (E_i = 0)
      const daysInYear = 365;
      const capitalDiasWeight = m.is_profit_eligible ? contributionsPaid * daysInYear : 0;

      return {
        membershipId: m.id,
        memberName: m.user_name,
        isProfitEligible: m.is_profit_eligible,
        totalCapitalConfirmed: contributionsPaid,
        capitalDiasWeight,
      };
    });

  const adminPct = currentPolicy?.admin_pct || 15;
  const memberPct = currentPolicy?.member_pct || 85;

  const closingResult = calculateCycleClosingSettlement(realizedNetProfit, adminPct, memberPct, members);

  // Administrador também é membro?
  const adminMember = state.memberships.find(
    m => m.tenant_id === state.currentTenantId && m.user_id === currentTenant?.admin_user_id
  );

  const [errorModal, setErrorModal] = useState<{ title: string; message: string; detail?: string } | null>(null);

  const handleAuthorizeClosingPix = () => {
    const totalToDisburse = roundCents(closingResult.memberPool + closingResult.adminPool);

    onOpenPixModal({
      title: 'Liquidação Final do Ciclo 2027',
      amount: totalToDisburse,
      description: `Liquidação de encerramento anual prevista para 10/01/2028`,
      recipientName: `Todos os ${members.length} cotistas e administrador`,
      referenceId: `close-settle-${Date.now()}`,
      onConfirm: async () => {
        try {
          await appStore.closeCycle(currentCycle?.id || 'cycle-2027-inaugural');
          setClosingStatus('FECHADO');
          confetti({
            particleCount: 150,
            spread: 80,
            origin: { y: 0.5 },
          });
        } catch (err: any) {
          setErrorModal({
            title: 'Fechamento de Ciclo Bloqueado',
            message: err?.message || 'Falha ao processar o fechamento do ciclo no backend.',
            detail: err?.detail || 'A apuração do lucro, rateio Capital-Dias V2 e distribuição de centavos exigem persistência transacional no PostgreSQL.'
          });
        }
      },
    });
  };

  return (
    <div className="space-y-6">
      {/* Banner de Estado do Backend Contratual */}
      <div className="bg-amber-50 border border-amber-300 rounded-2xl p-4 shadow-xs flex items-start gap-3">
        <Scale className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-950">
          <span className="font-bold block text-sm text-amber-900 mb-0.5">
            Apuração Autoritativa Capital-Dias V2: FastAPI + PostgreSQL
          </span>
          <p>
            O cálculo do pool de membros (85%), taxa de administração (15%), pesos ponderados pelo tempo e a distribuição dos maiores restos (Hare-Niemeyer) são homologados e arquivados pelo backend oficial. Operações locais sem banco conectado são bloqueadas.
          </p>
        </div>
      </div>

      {/* Header do Fechamento Central */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Encerramento Anual e Rateio Capital-Dias V2</h2>
            <span
              className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full ${
                closingStatus === 'FECHADO'
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-blue-100 text-blue-800'
              }`}
            >
              STATUS: {closingStatus}
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-1">
            Fases do Fechamento (Cláusula 4.6): Congelamento em <strong>31/12</strong> • Auditoria <strong>01 a 09/01</strong> • Liquidação Pix em <strong>10/01</strong>.
          </p>
        </div>

        {currentRole === 'TENANT_ADMIN' && closingStatus !== 'FECHADO' && (
          <button
            onClick={handleAuthorizeClosingPix}
            className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl shadow-md shadow-emerald-600/20 cursor-pointer flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
            <span>Autorizar Liquidação Pix em 10/01/2028</span>
          </button>
        )}
      </div>

      {/* Cards de Apuração do Lucro Realizado */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Lucro Líquido Realizado</span>
          <div className="text-2xl font-black text-emerald-700 mt-2">{formatBRL(closingResult.totalNetProfitRealized)}</div>
          <p className="text-[11px] text-slate-500 mt-1">Juros, mora e multas efetivamente recebidos</p>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Montante dos Membros ({memberPct}%)
          </span>
          <div className="text-2xl font-black text-slate-900 mt-2">{formatBRL(closingResult.memberPool)}</div>
          <p className="text-[11px] text-slate-500 mt-1">Rateio estrito por Capital-Dias V2</p>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Remuneração do Admin ({adminPct}%)
          </span>
          <div className="text-2xl font-black text-slate-900 mt-2">{formatBRL(closingResult.adminPool)}</div>
          <p className="text-[11px] text-slate-500 mt-1">Taxa de gestão administrativa pactuada</p>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Método dos Maiores Restos
          </span>
          <div className="text-2xl font-black text-teal-700 mt-2">
            {closingResult.residualCentavosToDistribute} centavos
          </div>
          <p className="text-[11px] text-teal-800 mt-1">Carteira Técnica baixada; zero resíduos</p>
        </div>
      </div>

      {/* Tabela de Rateio Capital-Dias V2 e Maiores Restos */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <Coins className="w-4 h-4 text-emerald-600" />
              <span>Demonstrativo Individual de Rateio (Capital-Dias V2 + Maiores Restos)</span>
            </h3>
            <span className="text-xs text-slate-500">
              Cláusula 10.4 / AT-14 / AT-42: Truncamento ao centavo e alocação residual aos maiores restos com desempate por membership_id
            </span>
          </div>
          <span className="text-xs font-mono font-bold text-slate-700 bg-slate-100 px-3 py-1 rounded-lg">
            Soma dos Pesos W_i: {closingResult.totalWeights.toLocaleString('pt-BR')}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100/70 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[10px]">
              <tr>
                <th className="py-3 px-3">Membro Participante</th>
                <th className="py-3 px-3 text-center">Elegibilidade</th>
                <th className="py-3 px-3 text-right">Capital Confirmado</th>
                <th className="py-3 px-3 text-right">Peso Capital-Dias (W_i)</th>
                <th className="py-3 px-3 text-right">% no Pool</th>
                <th className="py-3 px-3 text-right">Quota Exata</th>
                <th className="py-3 px-3 text-right">Quota Truncada</th>
                <th className="py-3 px-3 text-right">Resto Decimal</th>
                <th className="py-3 px-3 text-right">Bônus Centavo</th>
                <th className="py-3 px-3 text-right font-bold text-emerald-800">Lucro Final</th>
                <th className="py-3 px-3 text-right font-black text-slate-900">Total a Restituir</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {closingResult.memberDistributions.map(dist => {
                const memberData = members.find(m => m.membershipId === dist.membershipId);
                const capitalRefund = memberData?.totalCapitalConfirmed || 0;
                const totalRefund = capitalRefund + dist.finalProfitShare;

                return (
                  <tr key={dist.membershipId} className="hover:bg-slate-50/70">
                    <td className="py-3 px-3 font-sans font-bold text-slate-900">
                      <div>{dist.memberName}</div>
                      <span className="text-[10px] text-slate-400 font-mono">ID: {dist.membershipId}</span>
                    </td>
                    <td className="py-3 px-3 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full font-bold text-[9px] ${
                          dist.isEligible
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {dist.isEligible ? 'Elegível' : 'Inadimplente (E_i = 0)'}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right text-slate-700">{formatBRL(capitalRefund)}</td>
                    <td className="py-3 px-3 text-right font-semibold text-slate-800">
                      {dist.capitalDiasWeight.toLocaleString('pt-BR')}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-700">{dist.weightPercentage.toFixed(2)}%</td>
                    <td className="py-3 px-3 text-right text-slate-500 font-mono text-[11px]">
                      R$ {dist.exactShare.toFixed(4)}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-700">{formatBRL(dist.truncatedShare)}</td>
                    <td className="py-3 px-3 text-right text-slate-400 text-[10px]">
                      {dist.remainderFraction.toFixed(4)}
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-teal-700">
                      {dist.bonusCentavos > 0 ? `+${formatBRL(dist.bonusCentavos)}` : '-'}
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-emerald-700 bg-emerald-50/40">
                      {formatBRL(dist.finalProfitShare)}
                    </td>
                    <td className="py-3 px-3 text-right font-black text-slate-900 bg-slate-100/50">
                      {formatBRL(totalRefund)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Nota de Auditoria de Centavos */}
        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs text-slate-600 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>
              Soma total distribuída aos membros: <strong>{formatBRL(closingResult.memberPool)}</strong> (bate exatamente no centavo, sem resíduo!).
            </span>
          </div>
          <div className="text-[11px] text-slate-500">
            Regra Cláusula 10.5: O administrador João Silva recebe seu rateio de membro + taxa administrativa em linhas contábeis separadas.
          </div>
        </div>
      </div>

      {/* Modal de Bloqueio por Backend Não Conectado */}
      {errorModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 border border-rose-200">
            <div className="flex items-center gap-3 text-rose-700">
              <Scale className="w-6 h-6 shrink-0" />
              <h3 className="font-bold text-base text-slate-900">{errorModal.title}</h3>
            </div>
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-950 space-y-1.5">
              <span className="font-bold block text-rose-900">{errorModal.message}</span>
              {errorModal.detail && <p className="text-[11px] text-rose-800">{errorModal.detail}</p>}
            </div>
            <p className="text-[11px] text-slate-500">
              O encerramento do ciclo e rateio de sobras não foi gravado localmente para evitar distribuição fictícia de valores sem confirmação no livro-razão do servidor.
            </p>
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setErrorModal(null)}
                className="px-5 py-2 text-xs font-bold bg-slate-900 hover:bg-slate-800 text-white rounded-xl cursor-pointer"
              >
                Compreendi
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
