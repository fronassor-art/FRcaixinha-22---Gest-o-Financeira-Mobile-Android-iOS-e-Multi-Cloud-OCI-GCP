import React, { useState } from 'react';
import {
  Calendar,
  Wallet,
  CheckCircle2,
  Clock,
  AlertTriangle,
  QrCode,
  Filter,
  ArrowRight,
  ShieldAlert,
  Info
} from 'lucide-react';
import { AppState, appStore } from '../services/store';
import { Contribution } from '../types';
import { formatBRL, formatDateBR } from '../services/financialEngine';

interface ContributionsViewProps {
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

export const ContributionsView: React.FC<ContributionsViewProps> = ({ state, onOpenPixModal }) => {
  const currentRole = state.currentRole;
  const currentTenant = state.tenants.find(t => t.id === state.currentTenantId);
  const currentMember = state.memberships.find(
    m => m.tenant_id === state.currentTenantId && m.user_id === state.currentUserId
  );

  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [filterCompetence, setFilterCompetence] = useState<string>('ALL');
  const [partialAmountModal, setPartialAmountModal] = useState<{ contrib: Contribution; customAmount: number } | null>(null);

  // Filtrar contribuições conforme papel
  let baseContributions = state.contributions.filter(c => c.tenant_id === state.currentTenantId);
  if (currentRole === 'TENANT_MEMBER') {
    baseContributions = baseContributions.filter(c => c.membership_id === currentMember?.id);
  }

  const filtered = baseContributions.filter(c => {
    if (filterStatus === 'QUITADA' && c.payment_status !== 'QUITADA') return false;
    if (filterStatus === 'PENDENTE' && c.payment_status === 'QUITADA') return false;
    if (filterStatus === 'VENCIDA' && c.due_status !== 'VENCIDA') return false;
    if (filterCompetence !== 'ALL' && c.competence !== filterCompetence) return false;
    return true;
  });

  const [errorModal, setErrorModal] = useState<{ title: string; message: string; detail?: string } | null>(null);

  const handlePayFull = (c: Contribution) => {
    const member = state.memberships.find(m => m.id === c.membership_id);
    const balanceDue = c.amount_due - c.amount_paid;

    onOpenPixModal({
      title: `Contribuição Mensal - Comp. ${c.competence}`,
      amount: balanceDue,
      description: `Contribuição vencimento ${formatDateBR(c.due_date)} de ${member?.user_name}`,
      recipientName: currentTenant?.display_name || 'Caixinha',
      referenceId: c.id,
      onConfirm: async () => {
        try {
          await appStore.registerContributionPayment(c.id, balanceDue);
        } catch (err: any) {
          setErrorModal({
            title: 'Pagamento de Contribuição Bloqueado',
            message: err?.message || 'Falha ao registrar contribuição no backend.',
            detail: err?.detail || 'O Contrato Técnico Mestre veda persistência silenciosa em localStorage. A operação requer conexão ativa com o servidor FastAPI/PostgreSQL.'
          });
        }
      },
    });
  };

  const handlePayPartial = (c: Contribution, customAmount: number) => {
    const member = state.memberships.find(m => m.id === c.membership_id);

    onOpenPixModal({
      title: `Pagamento Parcial - Comp. ${c.competence}`,
      amount: customAmount,
      description: `Pagamento parcial contribuição de ${member?.user_name}`,
      recipientName: currentTenant?.display_name || 'Caixinha',
      referenceId: c.id,
      onConfirm: async () => {
        try {
          await appStore.registerContributionPayment(c.id, customAmount);
          setPartialAmountModal(null);
        } catch (err: any) {
          setErrorModal({
            title: 'Pagamento Parcial Bloqueado',
            message: err?.message || 'Falha ao registrar pagamento no backend.',
            detail: err?.detail || 'O Contrato Técnico Mestre veda persistência silenciosa em localStorage.'
          });
        }
      },
    });
  };

  return (
    <div className="space-y-6">
      {/* Banner de Estado do Backend Contratual */}
      <div className="bg-amber-50 border border-amber-300 rounded-2xl p-4 shadow-xs flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-950">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="font-bold text-sm text-amber-900">
              {state.isDataLoadedFromServer
                ? 'Persistência Autoritativa de Contribuições: FastAPI + PostgreSQL'
                : 'Ambiente Desconectado do Servidor — Exibição em Modo Demonstração'}
            </span>
            {!state.isDataLoadedFromServer && (
              <span className="text-[10px] font-bold bg-amber-200 text-amber-900 px-2 py-0.5 rounded-full">
                Dados Didáticos / Sem Efeito Contábil
              </span>
            )}
          </div>
          <p>
            {state.isDataLoadedFromServer
              ? 'O recebimento de contribuições, baixa de cotas e lançamentos em partidas dobradas no Caixa e Capital dos Membros são efetuados exclusivamente pelo backend.'
              : 'O backend contratual (FastAPI/PostgreSQL) não está conectado. As contribuições exibidas são dados semente didáticos. Operações de baixa financeira, pagamento real e alteração de saldo estão bloqueadas para proteção contábil.'}
          </p>
        </div>
      </div>

      {/* Header com Informação Contratual */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Contribuições Mensais do Ciclo 2027</h2>
            <span className="text-[11px] font-semibold bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full">
              Vencimento Central Dia 10 (Cláusula 4.5 e 6.3)
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-1">
            Status financeiro e status temporal são independentes (Cláusula 6.4 / AT-12). Suporte a pagamentos parciais e conciliação por Pix.
          </p>
        </div>

        {/* Informação de Inadimplência na Caixinha Inaugural */}
        {currentTenant?.is_owner_box && (
          <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-xl px-3.5 py-2 text-xs text-amber-900">
            <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              <strong>Regra Cláusula 6.5:</strong> 3 contribuições consecutivas vencidas ocasionam perda do lucro do ciclo. Principal continua devolvível.
            </span>
          </div>
        )}
      </div>

      {/* Filtros */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="font-semibold text-slate-700">Filtrar Status:</span>
          {['ALL', 'QUITADA', 'PENDENTE', 'VENCIDA'].map(st => (
            <button
              key={st}
              onClick={() => setFilterStatus(st)}
              className={`px-3 py-1 rounded-lg font-medium transition-colors cursor-pointer ${
                filterStatus === st ? 'bg-slate-900 text-white shadow-xs' : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
              }`}
            >
              {st === 'ALL' ? 'Todas' : st}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-700">Competência:</span>
          <select
            value={filterCompetence}
            onChange={e => setFilterCompetence(e.target.value)}
            className="bg-white border border-slate-300 rounded-lg px-2.5 py-1 text-xs text-slate-800"
          >
            <option value="ALL">Todas as Competências</option>
            <option value="2027-01">Janeiro/2027</option>
            <option value="2027-02">Fevereiro/2027</option>
            <option value="2027-03">Março/2027</option>
          </select>
        </div>
      </div>

      {/* Tabela de Contribuições */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100/80 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[10px]">
              <tr>
                <th className="py-3 px-4">Membro / Cotas</th>
                <th className="py-3 px-4">Competência</th>
                <th className="py-3 px-4">Vencimento</th>
                <th className="py-3 px-4 text-right">Valor Devido</th>
                <th className="py-3 px-4 text-right">Valor Pago</th>
                <th className="py-3 px-4 text-right">Saldo Aberto</th>
                <th className="py-3 px-4 text-center">Status Financeiro</th>
                <th className="py-3 px-4 text-center">Status Temporal</th>
                <th className="py-3 px-4 text-right">Ação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map(c => {
                const member = state.memberships.find(m => m.id === c.membership_id);
                const quotasCount = state.quotas.filter(q => q.membership_id === c.membership_id && q.status === 'ATIVA').length;
                const balanceDue = c.amount_due - c.amount_paid;

                return (
                  <tr key={c.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-slate-900">{member?.user_name}</div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        CPF: {member?.user_cpf} • {quotasCount} cota(s)
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono font-medium text-slate-800">
                      {c.competence}
                    </td>
                    <td className="py-3.5 px-4 text-slate-700">
                      {formatDateBR(c.due_date)}
                    </td>
                    <td className="py-3.5 px-4 text-right font-semibold text-slate-900">
                      {formatBRL(c.amount_due)}
                    </td>
                    <td className="py-3.5 px-4 text-right font-semibold text-emerald-700">
                      {formatBRL(c.amount_paid)}
                    </td>
                    <td className="py-3.5 px-4 text-right font-bold text-slate-900">
                      {formatBRL(balanceDue)}
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-full font-bold text-[10px] ${
                          c.payment_status === 'QUITADA'
                            ? 'bg-emerald-100 text-emerald-800'
                            : c.payment_status === 'PARCIAL'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {c.payment_status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-full font-bold text-[10px] ${
                          c.due_status === 'REGULARIZADA'
                            ? 'bg-emerald-100 text-emerald-800'
                            : c.due_status === 'VENCIDA'
                            ? 'bg-rose-100 text-rose-800 font-extrabold'
                            : 'bg-blue-100 text-blue-800'
                        }`}
                      >
                        {c.due_status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right space-x-1.5 whitespace-nowrap">
                      {balanceDue > 0 ? (
                        <>
                          <button
                            onClick={() => handlePayFull(c)}
                            className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-medium rounded-lg text-xs cursor-pointer shadow-2xs"
                          >
                            Pagar Pix ({formatBRL(balanceDue)})
                          </button>
                          <button
                            onClick={() => setPartialAmountModal({ contrib: c, customAmount: Math.round(balanceDue / 2) })}
                            className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium rounded-lg text-xs cursor-pointer border border-slate-200"
                            title="Simular pagamento parcial"
                          >
                            Parcial
                          </button>
                        </>
                      ) : (
                        <span className="text-emerald-700 font-medium text-xs flex items-center justify-end gap-1">
                          <CheckCircle2 className="w-4 h-4" />
                          <span>Conciliado</span>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal de Pagamento Parcial */}
      {partialAmountModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-5 shadow-2xl space-y-4 border border-slate-200">
            <h3 className="font-bold text-slate-900 text-sm">Informar Valor do Pagamento Parcial</h3>
            <p className="text-xs text-slate-600">
              Cláusula 6.3: O sistema aceita pagamentos parciais vinculados à obrigação com emissão de extrato e saldo em aberto.
            </p>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Valor Parcial (R$)</label>
              <input
                type="number"
                step="1"
                min="1"
                max={partialAmountModal.contrib.amount_due - partialAmountModal.contrib.amount_paid}
                value={partialAmountModal.customAmount}
                onChange={e =>
                  setPartialAmountModal({
                    ...partialAmountModal,
                    customAmount: Number(e.target.value),
                  })
                }
                className="w-full text-base font-bold px-3 py-2 border border-slate-300 rounded-lg text-slate-900"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">
                Saldo total aberto: {formatBRL(partialAmountModal.contrib.amount_due - partialAmountModal.contrib.amount_paid)}
              </span>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setPartialAmountModal(null)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
              >
                Cancelar
              </button>
              <button
                onClick={() => handlePayPartial(partialAmountModal.contrib, partialAmountModal.customAmount)}
                className="px-4 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg cursor-pointer shadow-xs"
              >
                Gerar Pix Parcial
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Bloqueio por Backend Não Conectado */}
      {errorModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 border border-rose-200">
            <div className="flex items-center gap-3 text-rose-700">
              <ShieldAlert className="w-6 h-6 shrink-0" />
              <h3 className="font-bold text-base text-slate-900">{errorModal.title}</h3>
            </div>
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-950 space-y-1.5">
              <span className="font-bold block text-rose-900">{errorModal.message}</span>
              {errorModal.detail && <p className="text-[11px] text-rose-800">{errorModal.detail}</p>}
            </div>
            <p className="text-[11px] text-slate-500">
              Para proteger o patrimônio coletivo da caixinha, nenhuma baixa de cota foi salva em contingência local sem confirmação transacional do servidor.
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
