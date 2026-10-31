import React, { useState } from 'react';
import { BookOpen, CheckCircle, Scale, Shield, ArrowDownLeft, ArrowUpRight, DollarSign, Lock } from 'lucide-react';
import { AppState } from '../services/store';
import { formatBRL, formatDateBR } from '../services/financialEngine';

interface LedgerViewProps {
  state: AppState;
}

export const LedgerView: React.FC<LedgerViewProps> = ({ state }) => {
  const currentTenant = state.tenants.find(t => t.id === state.currentTenantId);
  const tenantAccounts = state.ledgerAccounts.filter(a => a.tenant_id === state.currentTenantId);
  const tenantTxs = state.ledgerTransactions.filter(t => t.tenant_id === state.currentTenantId);

  const [expandedTxId, setExpandedTxId] = useState<string | null>(null);

  // Balanço Contábil
  const totalAssets = tenantAccounts
    .filter(a => a.kind === 'ATIVO')
    .reduce((acc, a) => acc + a.balance_cents, 0) / 100;

  const totalLiabilities = tenantAccounts
    .filter(a => a.kind === 'PASSIVO' || a.kind === 'PATRIMONIO_LIQUIDO')
    .reduce((acc, a) => acc + a.balance_cents, 0) / 100;

  const totalRevenues = tenantAccounts
    .filter(a => a.kind === 'RECEITA')
    .reduce((acc, a) => acc + a.balance_cents, 0) / 100;

  const isBalanced = Math.abs(totalAssets - (totalLiabilities + totalRevenues)) < 0.01;

  return (
    <div className="space-y-6">
      {/* Header com Princípio Contábil */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Livro-Razão Contábil (Partidas Dobradas)</h2>
            <span className="text-[11px] font-semibold bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full">
              Centavos Exatos • Cláusula 7.2
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-1">
            Contabilidade autoritativa: Toda entrada ou saída exige <strong>Σ Débitos = Σ Créditos</strong>. Proibida alteração manual silenciosa de saldo.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-xl">
            <Scale className="w-4 h-4 text-emerald-600" />
            <span>Balanço Equilibrado ({isBalanced ? 'CONFERIDO' : 'DIVERGÊNCIA'})</span>
          </div>
        </div>
      </div>

      {/* Plano de Contas / Balancete */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
        <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-emerald-600" />
          <span>Plano de Contas da Caixinha ({currentTenant?.display_name})</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {tenantAccounts.map(account => (
            <div key={account.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-1">
              <div className="flex items-center justify-between text-[10px] font-mono font-bold text-slate-500">
                <span>{account.account_code}</span>
                <span className="px-1.5 py-0.5 bg-slate-200 rounded text-slate-700">{account.kind}</span>
              </div>
              <strong className="block text-xs text-slate-800 leading-tight">{account.account_name}</strong>
              <div className="text-lg font-extrabold text-slate-900 pt-1 font-mono">
                {formatBRL(account.balance_cents / 100)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Livro Diário de Lançamentos */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs space-y-0">
        <div className="p-5 border-b border-slate-200 flex items-center justify-between">
          <h3 className="font-bold text-slate-900 text-sm">Registro Cronológico de Transações (Journal)</h3>
          <span className="text-xs text-slate-500">Lançamentos indivisíveis, idempotentes e auditáveis</span>
        </div>

        <div className="divide-y divide-slate-100">
          {tenantTxs.map(tx => {
            const isExpanded = expandedTxId === tx.id;
            const totalDebits = tx.entries.filter(e => e.direction === 'DEBIT').reduce((acc, e) => acc + e.amount_cents, 0) / 100;
            const totalCredits = tx.entries.filter(e => e.direction === 'CREDIT').reduce((acc, e) => acc + e.amount_cents, 0) / 100;

            return (
              <div key={tx.id} className="p-4 hover:bg-slate-50 transition-colors">
                <div
                  onClick={() => setExpandedTxId(isExpanded ? null : tx.id)}
                  className="flex flex-wrap items-center justify-between gap-3 cursor-pointer"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-700">
                      {tx.business_type === 'CONTRIBUTION_PAYMENT' ? (
                        <ArrowDownLeft className="w-4 h-4 text-emerald-600" />
                      ) : (
                        <ArrowUpRight className="w-4 h-4 text-blue-600" />
                      )}
                    </div>
                    <div>
                      <strong className="text-xs text-slate-900">{tx.description}</strong>
                      <div className="text-[11px] text-slate-500 font-mono">
                        ID: {tx.id} • {formatDateBR(tx.posted_at)} • Tipo: {tx.business_type}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-xs font-mono">
                    <span className="font-bold text-slate-900">{formatBRL(totalDebits)}</span>
                    <span className="text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded text-[10px]">
                      {tx.status}
                    </span>
                  </div>
                </div>

                {/* Detalhamento das Partidas Dobradas */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-slate-100 space-y-2 bg-slate-100/60 p-3 rounded-xl animate-in fade-in">
                    <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider block">
                      Partidas Dobradas ({tx.entries.length} lançamentos)
                    </span>
                    <div className="space-y-1 text-xs font-mono">
                      {tx.entries.map(entry => (
                        <div key={entry.id} className="flex justify-between items-center text-[11px]">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                entry.direction === 'DEBIT'
                                  ? 'bg-rose-100 text-rose-800'
                                  : 'bg-emerald-100 text-emerald-800'
                              }`}
                            >
                              {entry.direction === 'DEBIT' ? 'DÉBITO (+)' : 'CRÉDITO (-)'}
                            </span>
                            <span className="text-slate-800">{entry.account_name}</span>
                          </div>
                          <span className="font-bold text-slate-900">
                            {formatBRL(entry.amount_cents / 100)}
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="flex justify-between border-t border-slate-200 pt-1 text-[10px] font-bold text-slate-600">
                      <span>Total Débitos: {formatBRL(totalDebits)}</span>
                      <span>Total Créditos: {formatBRL(totalCredits)}</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
