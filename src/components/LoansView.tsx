import React, { useState } from 'react';
import {
  Calculator,
  ArrowUpRight,
  CheckCircle2,
  AlertCircle,
  Clock,
  ShieldCheck,
  FileText,
  DollarSign,
  Send,
  HelpCircle,
  Percent,
  Calendar,
  Sparkles,
  Info,
  ShieldAlert
} from 'lucide-react';
import { AppState, appStore } from '../services/store';
import { calculatePriceSimulation, formatBRL, formatDateBR, roundCents } from '../services/financialEngine';
import { Loan } from '../types';

interface LoansViewProps {
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

export const LoansView: React.FC<LoansViewProps> = ({ state, onOpenPixModal }) => {
  const currentRole = state.currentRole;
  const currentTenant = state.tenants.find(t => t.id === state.currentTenantId);
  const currentPolicy = state.policies.find(p => p.tenant_id === state.currentTenantId && p.status === 'ACTIVE');
  const currentMember = state.memberships.find(
    m => m.tenant_id === state.currentTenantId && m.user_id === state.currentUserId
  );

  // Estados da simulação Price (Padrão: R$ 500, 5 parcelas, 20% a.m., sem taxas adicionais)
  const [simPrincipal, setSimPrincipal] = useState<number>(500);
  const [simTerm, setSimTerm] = useState<number>(5);
  const [useIrregularFirstPeriod, setUseIrregularFirstPeriod] = useState<boolean>(false);
  const [simDisbDate, setSimDisbDate] = useState<string>('2027-01-10');
  const [selectedBorrowerId, setSelectedBorrowerId] = useState<string>(
    currentRole === 'TENANT_MEMBER' ? currentMember?.id || '' : 'mem-maria'
  );

  // Modal de pagamento de parcela
  const [repayInstallmentModal, setRepayInstallmentModal] = useState<{
    loan: Loan;
    seq: number;
    amountDue: number;
    customAmount: number;
  } | null>(null);

  // Executar simulação em tempo real
  const monthlyRate = currentPolicy?.monthly_interest_rate || 0.20;
  const simResult = calculatePriceSimulation({
    principal: simPrincipal,
    monthlyRate,
    termMonths: simTerm,
    disbursementDate: new Date(simDisbDate),
    cycleYear: 2027,
    useIrregularFirstPeriod,
  });

  const freeCash = appStore.getTenantFreeCash(state.currentTenantId);

  // Filtrar empréstimos por tenant e papel
  let tenantLoans = state.loans.filter(l => l.tenant_id === state.currentTenantId);
  if (currentRole === 'TENANT_MEMBER') {
    tenantLoans = tenantLoans.filter(l => l.borrower_membership_id === currentMember?.id);
  }

  const [errorModal, setErrorModal] = useState<{ title: string; message: string; detail?: string } | null>(null);

  const handleRequestLoan = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const borrower = state.memberships.find(m => m.id === selectedBorrowerId);
      if (!borrower) throw new Error('Selecione um mutuário membro da caixinha');

      await appStore.requestLoan({
        membershipId: borrower.id,
        principal: simPrincipal,
        termMonths: simTerm,
      });

      alert('Solicitação de empréstimo registrada com sucesso! Aguardando aprovação e reserva.');
    } catch (err: any) {
      setErrorModal({
        title: 'Operação de Crédito Bloqueada',
        message: err?.message || 'Falha ao solicitar empréstimo no backend.',
        detail: err?.detail || 'O Contrato Técnico Mestre exige persistência transacional com RLS. Gravações locais foram bloqueadas com segurança.'
      });
    }
  };

  const handleApprove = async (loanId: string) => {
    try {
      await appStore.approveLoan(loanId);
    } catch (err: any) {
      setErrorModal({
        title: 'Aprovação de Empréstimo Bloqueada',
        message: err?.message || 'Falha ao aprovar empréstimo no backend.',
        detail: err?.detail || 'Apenas o backend oficial com banco de dados conectado pode efetivar a aprovação.'
      });
    }
  };

  const handleDisbursePix = (loan: Loan) => {
    onOpenPixModal({
      title: `Desembolso Pix de Empréstimo`,
      amount: loan.principal,
      description: `Liberação de crédito aprovado para ${loan.borrower_name}`,
      recipientName: loan.borrower_name,
      referenceId: loan.id,
      onConfirm: async () => {
        try {
          await appStore.disburseLoanPix(loan.id);
        } catch (err: any) {
          setErrorModal({
            title: 'Desembolso Financeiro Bloqueado',
            message: err?.message || 'Falha no desembolso.',
            detail: err?.detail || 'Desembolsos exigem validação transacional e lançamento contábil no PostgreSQL.'
          });
        }
      },
    });
  };

  const handleExecuteRepayment = () => {
    if (!repayInstallmentModal) return;
    const { loan, seq, customAmount } = repayInstallmentModal;

    onOpenPixModal({
      title: `Pagamento Parcela ${seq} - Empréstimo`,
      amount: customAmount,
      description: `Amortização parcela ${seq} de ${loan.borrower_name}`,
      recipientName: currentTenant?.display_name || 'Caixinha',
      referenceId: `${loan.id}-seq-${seq}`,
      onConfirm: async () => {
        try {
          await appStore.payLoanInstallment(loan.id, seq, customAmount);
          setRepayInstallmentModal(null);
        } catch (err: any) {
          setErrorModal({
            title: 'Amortização de Parcela Bloqueada',
            message: err?.message || 'Falha ao amortizar parcela.',
            detail: err?.detail || 'A imputação em 4 etapas requer persistência no PostgreSQL.'
          });
        }
      },
    });
  };

  const handleEarlySettlement = (loan: Loan) => {
    let remainingPrincipal = 0;
    let overdueInterest = 0;
    let overdueMora = 0;
    let overdueFine = 0;
    let futureUnaccruedInterest = 0;
    const now = new Date();

    loan.installments.forEach(inst => {
      if (inst.status !== 'QUITADA') {
        const unpaidPrincipal = roundCents(inst.principal_due - inst.paid_principal);
        remainingPrincipal = roundCents(remainingPrincipal + unpaidPrincipal);
        const dueDate = new Date(inst.due_date);
        if (dueDate < now) {
          overdueInterest = roundCents(overdueInterest + (inst.interest_due - inst.paid_interest));
          overdueMora = roundCents(overdueMora + (inst.mora_amount - inst.paid_mora));
          overdueFine = roundCents(overdueFine + (inst.fine_amount - inst.paid_fine));
        } else {
          futureUnaccruedInterest = roundCents(futureUnaccruedInterest + (inst.interest_due - inst.paid_interest));
        }
      }
    });

    const totalToSettle = roundCents(remainingPrincipal + overdueInterest + overdueMora + overdueFine);

    onOpenPixModal({
      title: 'Quitação Antecipada de Empréstimo (Cláusula 8.6)',
      amount: totalToSettle,
      description: `Quitação integral sem juros futuros (desconto de R$ ${futureUnaccruedInterest.toFixed(2)} em juros vincendos não incorridos)`,
      recipientName: currentTenant?.display_name || 'Caixinha',
      referenceId: `early-settle-${loan.id}`,
      onConfirm: async () => {
        try {
          await appStore.settleLoanEarly(loan.id);
        } catch (err: any) {
          setErrorModal({
            title: 'Quitação Antecipada Bloqueada',
            message: err?.message || 'Falha ao liquidar empréstimo.',
            detail: err?.detail || 'Liquidação contábil e abatimento de juros vincendos requerem persistência no backend oficial.'
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
                ? 'Fronteira Transacional Oficial: FastAPI (Python) + PostgreSQL RLS'
                : 'Ambiente Desconectado do Servidor — Simulador Matemático Didático'}
            </span>
            {!state.isDataLoadedFromServer && (
              <span className="text-[10px] font-bold bg-amber-200 text-amber-900 px-2 py-0.5 rounded-full">
                Sem Persistência Contábil
              </span>
            )}
          </div>
          <p>
            {state.isDataLoadedFromServer
              ? 'Todas as operações financeiras reais (solicitação, aprovação, desembolso, amortização com imputação e quitação antecipada) são processadas exclusivamente pelo servidor backend com isolamento RLS.'
              : 'O backend oficial FastAPI / PostgreSQL não está conectado neste ambiente. Os cálculos abaixo operam como simulador matemático estritamente didático. Em estrita conformidade com o Contrato Técnico Mestre, transações financeiras reais (solicitação, aprovação, desembolso e quitação) exigem persistência autoritativa com RLS e encontram-se bloqueadas.'}
          </p>
        </div>
      </div>

      {/* Header com Regras Centrais de Crédito e Aviso de Isenção de Taxas */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Simulação de Empréstimo — Tabela Price</h2>
            <span className="text-[11px] font-bold bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Tarifa Adm: R$ 0,00 (Isento)</span>
            </span>
            <span className="text-[11px] font-semibold bg-blue-100 text-blue-800 px-2.5 py-0.5 rounded-full">
              Juros: {(monthlyRate * 100).toFixed(0)}% a.m.
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-1">
            Juros remuneratórios de <strong>{(monthlyRate * 100).toFixed(0)}% ao mês</strong> sobre o saldo devedor restante utilizando a Tabela Price • Isenção total de tarifas administrativas, TAC ou IOF.
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs">
          <div className="bg-emerald-50 border border-emerald-200 px-3.5 py-2 rounded-xl text-emerald-900 text-right">
            <span className="text-[10px] uppercase font-bold text-emerald-700 block">Caixa Livre para Crédito</span>
            <strong className="text-base font-extrabold">{formatBRL(freeCash)}</strong>
          </div>
        </div>
      </div>

      {/* 4 Cards de Destaque da Simulação Oficial (R$ 500 em 5x) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">Valor Emprestado</span>
          <div className="text-2xl font-black text-slate-900 mt-1">{formatBRL(simResult.principal)}</div>
          <span className="text-[11px] text-slate-500 mt-1 block">Principal liberado ao membro</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">Parcela Mensal</span>
          <div className="text-2xl font-black text-emerald-700 mt-1">{formatBRL(simResult.uniformPayment)}</div>
          <span className="text-[11px] text-slate-500 mt-1 block">
            {simTerm} parcelas (última ajustada para {formatBRL(simResult.lastPayment)})
          </span>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">Total a Receber</span>
          <div className="text-2xl font-black text-slate-900 mt-1">{formatBRL(simResult.totalPayment)}</div>
          <span className="text-[11px] text-slate-500 mt-1 block">Amortização + Juros no período</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">Lucro em Juros</span>
          <div className="text-2xl font-black text-teal-700 mt-1">{formatBRL(simResult.totalInterest)}</div>
          <span className="text-[11px] text-emerald-700 font-medium mt-1 block">Rendimento líquido gerado</span>
        </div>
      </div>

      {/* Grid: Formulário de Simulação vs Demonstrativo Oficial da Tabela Price */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Formulário de Parâmetros (5 Colunas) */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <Calculator className="w-4 h-4 text-emerald-600" />
              <span>Parâmetros do Empréstimo</span>
            </h3>
            <span className="text-[10px] font-mono font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
              Tarifa: R$ 0,00 • {(monthlyRate * 100).toFixed(0)}% a.m.
            </span>
          </div>

          <form onSubmit={handleRequestLoan} className="space-y-4 text-xs">
            {/* Mutuário */}
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Membro Mutuário</label>
              {currentRole === 'TENANT_MEMBER' ? (
                <div className="p-2.5 bg-slate-100 rounded-lg font-bold text-slate-800">
                  {currentMember?.user_name} (Você)
                </div>
              ) : (
                <select
                  value={selectedBorrowerId}
                  onChange={e => setSelectedBorrowerId(e.target.value)}
                  className="w-full p-2 bg-white border border-slate-300 rounded-lg font-medium text-slate-800"
                >
                  {state.memberships
                    .filter(m => m.tenant_id === state.currentTenantId && m.status === 'ATIVA')
                    .map(m => (
                      <option key={m.id} value={m.id}>
                        {m.user_name} {m.user_id === currentTenant?.admin_user_id ? '(Administrador)' : ''}
                      </option>
                    ))}
                </select>
              )}
            </div>

            {/* Principal */}
            <div>
              <div className="flex justify-between font-semibold text-slate-700 mb-1">
                <span>Valor Solicitado (PV)</span>
                <span className="text-emerald-700 font-bold">{formatBRL(simPrincipal)}</span>
              </div>
              <input
                type="range"
                min="100"
                max={Math.max(1000, freeCash)}
                step="50"
                value={simPrincipal}
                onChange={e => setSimPrincipal(Number(e.target.value))}
                className="w-full accent-emerald-600 cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                <span>Mín: R$ 100</span>
                <button
                  type="button"
                  onClick={() => setSimPrincipal(500)}
                  className="text-emerald-700 font-bold hover:underline"
                >
                  Definir R$ 500,00 (Padrão)
                </button>
                <span>Máx: {formatBRL(freeCash)}</span>
              </div>
            </div>

            {/* Quantidade de Parcelas */}
            <div>
              <div className="flex justify-between font-semibold text-slate-700 mb-1">
                <span>Número de Parcelas</span>
                <span className="text-slate-900 font-bold">{simTerm} parcelas mensais</span>
              </div>
              <div className="grid grid-cols-6 gap-1.5">
                {[1, 2, 3, 4, 5, 6].map(n => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setSimTerm(n)}
                    className={`py-1.5 rounded-lg font-bold text-xs cursor-pointer transition-colors ${
                      simTerm === n
                        ? 'bg-emerald-600 text-white shadow-xs'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    {n}x
                  </button>
                ))}
              </div>
            </div>

            {/* Alternador de Modo de Período (Períodos Mensais Completos vs Primeiro Período Irregular) */}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
              <span className="text-[11px] font-bold text-slate-700 block">Regime de Cálculo da Tabela Price:</span>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="periodMode"
                  checked={!useIrregularFirstPeriod}
                  onChange={() => setUseIrregularFirstPeriod(false)}
                  className="accent-emerald-600"
                />
                <span className="text-xs font-semibold text-slate-900">
                  Períodos mensais completos (Sem taxas • Padrão)
                </span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="periodMode"
                  checked={useIrregularFirstPeriod}
                  onChange={() => setUseIrregularFirstPeriod(true)}
                  className="accent-emerald-600"
                />
                <span className="text-xs text-slate-600">
                  Primeiro período proporcional aos dias reais (Cláusula 8.5)
                </span>
              </label>
            </div>

            {/* Resumo da Operação */}
            <div className="p-3.5 rounded-xl bg-emerald-50/70 border border-emerald-200 text-emerald-950 space-y-1.5">
              <div className="flex justify-between text-xs">
                <span>Taxa contratual de juros:</span>
                <strong className="font-bold">{(monthlyRate * 100).toFixed(0)}% ao mês</strong>
              </div>
              <div className="flex justify-between text-xs">
                <span>Taxas adicionais / TAC / IOF:</span>
                <strong className="text-emerald-700 font-bold">R$ 0,00 (ISENTO)</strong>
              </div>
              <div className="flex justify-between text-xs">
                <span>Prestação mensal uniforme:</span>
                <strong className="font-black text-sm text-emerald-900">{formatBRL(simResult.uniformPayment)}</strong>
              </div>
            </div>

            {!simResult.isValidCycle ? (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-[11px] leading-relaxed">
                <AlertCircle className="w-4 h-4 inline mr-1 text-rose-600" />
                {simResult.validationError}
              </div>
            ) : (
              <button
                type="submit"
                disabled={simPrincipal > freeCash}
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl shadow-xs transition-colors cursor-pointer disabled:opacity-40"
              >
                {simPrincipal > freeCash ? 'Saldo Livre Insuficiente' : 'Solicitar Este Empréstimo'}
              </button>
            )}
          </form>
        </div>

        {/* Demonstrativo das Parcelas (7 Colunas) */}
        <div className="lg:col-span-7 space-y-5">
          {/* Tabela do Demonstrativo das Parcelas */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h4 className="font-bold text-slate-900 text-sm">Demonstrativo das {simTerm} Parcelas</h4>
                <p className="text-[11px] text-slate-500">
                  Tabela Price com amortização crescente e juros decrescentes sobre o saldo devedor
                </p>
              </div>
              <span className="text-[10px] font-bold bg-slate-100 text-slate-700 px-2 py-1 rounded-md">
                Última ajustada: {formatBRL(simResult.lastPayment)}
              </span>
            </div>

            {/* Visualização em Tabela para Desktop / Tablet com rolagem horizontal */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[10px]">
                  <tr>
                    <th className="py-2.5 px-3">Parcela</th>
                    <th className="py-2.5 px-3 text-right">Juros ({(monthlyRate * 100).toFixed(0)}%)</th>
                    <th className="py-2.5 px-3 text-right">Amortização</th>
                    <th className="py-2.5 px-3 text-right">Prestação</th>
                    <th className="py-2.5 px-3 text-right font-bold">Saldo Devedor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono">
                  {simResult.installments.map(inst => (
                    <tr key={inst.sequence} className="hover:bg-slate-50/70">
                      <td className="py-2.5 px-3 font-sans font-bold text-slate-900">
                        {inst.sequence}ª
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-700 font-medium">
                        {formatBRL(inst.interestDue)}
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-700 font-medium">
                        {formatBRL(inst.principalDue)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-bold text-emerald-800">
                        {formatBRL(inst.payment)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-bold text-slate-900">
                        {formatBRL(inst.remainingBalance)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-slate-100/80 font-mono font-bold text-slate-900 border-t-2 border-slate-300">
                  <tr>
                    <td className="py-2.5 px-3 font-sans uppercase text-[10px]">Total</td>
                    <td className="py-2.5 px-3 text-right text-teal-800">{formatBRL(simResult.totalInterest)}</td>
                    <td className="py-2.5 px-3 text-right text-slate-900">{formatBRL(simResult.principal)}</td>
                    <td className="py-2.5 px-3 text-right text-emerald-800">{formatBRL(simResult.totalPayment)}</td>
                    <td className="py-2.5 px-3 text-right text-slate-500">R$ 0,00</td>
                  </tr>
                </tfoot>
              </table>
            </div>

            {/* Visualização Mobile em Cards (Anti-Truncamento em Smartphones) */}
            <div className="block sm:hidden space-y-2.5">
              {simResult.installments.map(inst => (
                <div
                  key={inst.sequence}
                  className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between border-b border-slate-200/80 pb-1.5">
                    <span className="font-bold text-slate-900 text-sm">{inst.sequence}ª Parcela</span>
                    <span className="font-extrabold text-emerald-700 font-mono text-sm">
                      {formatBRL(inst.payment)}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div>
                      <span className="text-slate-500 block">Juros ({(monthlyRate * 100).toFixed(0)}%):</span>
                      <strong className="text-teal-700 font-mono">{formatBRL(inst.interestDue)}</strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Amortização:</span>
                      <strong className="text-slate-800 font-mono">{formatBRL(inst.principalDue)}</strong>
                    </div>
                  </div>
                  <div className="pt-1 border-t border-slate-200/60 flex items-center justify-between text-[11px]">
                    <span className="text-slate-500">Saldo Devedor Restante:</span>
                    <strong className="text-slate-900 font-mono">{formatBRL(inst.remainingBalance)}</strong>
                  </div>
                </div>
              ))}
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-xs font-bold text-emerald-950">
                <span>Total a Pagar ({simTerm}x):</span>
                <span className="text-sm font-black text-emerald-800 font-mono">{formatBRL(simResult.totalPayment)}</span>
              </div>
            </div>

            {/* Texto Explicativo Oficial de Funcionamento */}
            <div className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-2">
              <div className="flex items-center gap-1.5 font-bold text-slate-900">
                <Info className="w-4 h-4 text-emerald-600" />
                <span>Como Funciona a Tabela Price:</span>
              </div>
              <p className="leading-relaxed text-slate-600">
                Os juros são calculados a cada mês sobre o saldo devedor restante, não sobre os R$ 500,00 iniciais. Por isso, os juros diminuem e a amortização do principal aumenta a cada parcela.
              </p>
              <div className="p-3 bg-white rounded-lg border border-slate-200/80 text-[11px] text-emerald-950 space-y-1">
                <strong>Resultado final:</strong> você empresta {formatBRL(simResult.principal)} e recebe {formatBRL(simResult.totalPayment)} em {simTerm} meses, sendo {formatBRL(simResult.totalInterest)} de juros, considerando todos os pagamentos em dia e sem taxas adicionais.
              </div>
            </div>
          </div>

          {/* Empréstimos Ativos / Pendentes da Caixinha */}
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
            <h4 className="font-bold text-slate-900 text-xs uppercase tracking-wider">
              Empréstimos Contratados e Pedidos
            </h4>

            {tenantLoans.length === 0 ? (
              <div className="text-center py-8 text-slate-400 text-xs">
                Nenhum empréstimo ativo no momento.
              </div>
            ) : (
              tenantLoans.map(loan => (
                <div key={loan.id} className="border border-slate-200 rounded-xl p-4 space-y-3 bg-slate-50/50">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <strong className="text-slate-900 text-sm">{loan.borrower_name}</strong>
                        {loan.is_admin_loan && (
                          <span className="text-[10px] bg-purple-100 text-purple-800 font-bold px-2 py-0.5 rounded-full">
                            Autoempréstimo Admin (Cláusula 2.5)
                          </span>
                        )}
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          loan.status === 'DESEMBOLSADO'
                            ? 'bg-emerald-100 text-emerald-800'
                            : loan.status === 'APROVADO'
                            ? 'bg-blue-100 text-blue-800'
                            : loan.status === 'QUITADO'
                            ? 'bg-teal-100 text-teal-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}>
                          {loan.status}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        Principal: <strong>{formatBRL(loan.principal)}</strong> • {loan.term_months} parcelas de <strong>{formatBRL(loan.monthly_payment)}</strong>
                      </div>
                    </div>

                    {/* Ações do Admin */}
                    {currentRole === 'TENANT_ADMIN' && loan.status === 'SOLICITADO' && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleApprove(loan.id)}
                          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-lg cursor-pointer"
                        >
                          Aprovar Pedido
                        </button>
                      </div>
                    )}

                    {currentRole === 'TENANT_ADMIN' && loan.status === 'APROVADO' && (
                      <button
                        onClick={() => handleDisbursePix(loan)}
                        className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-lg cursor-pointer shadow-xs flex items-center gap-1.5"
                      >
                        <Send className="w-3.5 h-3.5" />
                        <span>Liberar Empréstimo via Pix</span>
                      </button>
                    )}

                    {loan.status === 'DESEMBOLSADO' && (
                      <button
                        onClick={() => handleEarlySettlement(loan)}
                        className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs rounded-lg cursor-pointer flex items-center gap-1 shadow-xs"
                        title="Quitação com isenção total de juros futuros não incorridos (Cláusula 8.6)"
                      >
                        <ShieldCheck className="w-3.5 h-3.5" />
                        <span>Quitar Antecipadamente</span>
                      </button>
                    )}
                  </div>

                  {/* Parcelas do Empréstimo */}
                  {loan.status === 'DESEMBOLSADO' && (
                    <div className="border-t border-slate-200/80 pt-2.5">
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1.5">
                        Acompanhamento das Parcelas
                      </span>
                      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
                        {loan.installments.map(inst => (
                          <div
                            key={inst.id}
                            className={`p-2.5 rounded-lg border ${
                              inst.status === 'QUITADA'
                                ? 'bg-emerald-50/70 border-emerald-200'
                                : 'bg-white border-slate-200'
                            }`}
                          >
                            <div className="flex justify-between text-[11px] font-bold">
                              <span>{inst.sequence}ª Parcela</span>
                              <span className={inst.status === 'QUITADA' ? 'text-emerald-700' : 'text-slate-600'}>
                                {inst.status}
                              </span>
                            </div>
                            <div className="text-xs font-mono font-bold mt-1 text-slate-800">
                              {formatBRL(inst.principal_due + inst.interest_due)}
                            </div>
                            <div className="text-[10px] text-slate-500">Venc: {formatDateBR(inst.due_date)}</div>

                            {inst.status !== 'QUITADA' && (
                              <button
                                onClick={() =>
                                  setRepayInstallmentModal({
                                    loan,
                                    seq: inst.sequence,
                                    amountDue: inst.principal_due + inst.interest_due - inst.paid_amount,
                                    customAmount: inst.principal_due + inst.interest_due - inst.paid_amount,
                                  })
                                }
                                className="w-full mt-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white text-[10px] font-bold rounded cursor-pointer"
                              >
                                Pagar Parcela
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Modal de Pagamento de Parcela com Imputação em 4 etapas (Cláusula 8.6 / AT-41) */}
      {repayInstallmentModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 border border-slate-200">
            <h3 className="font-bold text-slate-900 text-base">Amortização de Parcela de Empréstimo</h3>
            <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-xs text-blue-950 space-y-1">
              <span className="font-bold block">Ordem Obrigatória de Imputação (Cláusula 8.6):</span>
              <p>(1) Juros remuneratórios vencidos → (2) Mora simples → (3) Multa única R$ 10 → (4) Principal.</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Valor do Pagamento (R$)</label>
              <input
                type="number"
                step="1"
                min="1"
                value={repayInstallmentModal.customAmount}
                onChange={e =>
                  setRepayInstallmentModal({
                    ...repayInstallmentModal,
                    customAmount: Number(e.target.value),
                  })
                }
                className="w-full text-lg font-bold px-3 py-2 border border-slate-300 rounded-lg text-slate-900"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">
                Valor total da parcela: {formatBRL(repayInstallmentModal.amountDue)}
              </span>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setRepayInstallmentModal(null)}
                className="px-4 py-2 text-xs text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
              >
                Cancelar
              </button>
              <button
                onClick={handleExecuteRepayment}
                className="px-5 py-2 text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl cursor-pointer shadow-xs"
              >
                Confirmar Pagamento Pix
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
              Para proteger os dados e o patrimônio da caixinha, nenhuma operação foi gravada em modo offline ou contingência local.
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
