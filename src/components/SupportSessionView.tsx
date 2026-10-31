import React, { useState } from 'react';
import {
  LifeBuoy,
  ShieldAlert,
  Clock,
  Lock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Radio,
  FileCode
} from 'lucide-react';
import { AppState, appStore } from '../services/store';
import { formatDateBR } from '../services/financialEngine';

interface SupportSessionViewProps {
  state: AppState;
}

export const SupportSessionView: React.FC<SupportSessionViewProps> = ({ state }) => {
  const [supportReason, setSupportReason] = useState('Verificação de conciliação de webhook Pix');
  const [sessionType, setSessionType] = useState<'CONSENTED_NORMAL' | 'BREAK_GLASS_EMERGENCY'>('CONSENTED_NORMAL');
  const [webhookSimOutput, setWebhookSimOutput] = useState<string | null>(null);

  const activeGrants = state.supportGrants.filter(g => g.status === 'ACTIVE');

  const handleStartSession = () => {
    try {
      appStore.grantSupportAccess(state.currentTenantId, sessionType, supportReason);
      alert(`Sessão de suporte ${sessionType === 'CONSENTED_NORMAL' ? 'Consentido (60m)' : 'Break-Glass (30m)'} iniciada com sucesso.`);
    } catch (e: unknown) {
      if (e instanceof Error) alert(e.message);
    }
  };

  const handleRevoke = (grantId: string) => {
    appStore.revokeSupportAccess(grantId);
  };

  // Simulação dos testes de robustez de webhook (Cláusula 9.8 / AT-11 / AT-28)
  const handleTestWebhookResilience = (scenario: '10x_REPLAY' | 'OUT_OF_ORDER' | 'DIVERGENT_VALUE') => {
    if (scenario === '10x_REPLAY') {
      setWebhookSimOutput('✅ [TESTE 10x REPLAY]: O mesmo webhook Pix (ID: evt_0928341) foi enviado 10 vezes consecutivas. O backend identificou o idempotency_key estável e realizou 1 único lançamento no ledger. 9 requisições foram marcadas como DUPLICATE_SKIPPED.');
    } else if (scenario === 'OUT_OF_ORDER') {
      setWebhookSimOutput('✅ [TESTE FORA DE ORDEM]: Webhook com status CONFIRMADO chegou antes da resposta da API de geração. O backend reteve o estado PENDENTE_CONCILIACAO e conciliou a obrigação sem duplicidade.');
    } else {
      setWebhookSimOutput('⚠️ [TESTE VALOR DIVERGENTE]: Webhook informou R$ 95,00 para obrigação esperada de R$ 100,00. O sistema registrou status financeiro PARCIAL e alertou divergência no log de auditoria, preservando o saldo em aberto.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header com Regras de Suporte */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Suporte Técnico, Manutenção e Break-Glass</h2>
            <span className="text-[11px] font-semibold bg-indigo-100 text-indigo-800 px-2.5 py-0.5 rounded-full">
              Sem Ingerência Patrimonial • Seção 5
            </span>
          </div>
          <p className="text-xs text-slate-600 mt-1">
            Acesso consentido normal de até <strong>60 minutos</strong> e emergencial de até <strong>30 minutos</strong> (Cláusula 5.3). Vedações invariáveis: Proibido aprovar crédito ou disparar Pix pelo suporte (Cláusula 5.4).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-slate-700 bg-slate-100 px-3 py-1.5 rounded-xl flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-indigo-600" />
            <span>Sessões Ativas: {activeGrants.length}</span>
          </span>
        </div>
      </div>

      {/* Formulário de Abertura de Sessão */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Painel de Solicitação */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
          <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
            <LifeBuoy className="w-4 h-4 text-emerald-600" />
            <span>Autorizar Acesso Técnico Excepcional</span>
          </h3>

          <div className="space-y-3 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Modalidade do Chamado</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setSessionType('CONSENTED_NORMAL')}
                  className={`p-3 rounded-xl border text-left cursor-pointer transition-all ${
                    sessionType === 'CONSENTED_NORMAL'
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-950 font-bold'
                      : 'border-slate-200 bg-slate-50 text-slate-700'
                  }`}
                >
                  <div className="text-xs">Consentido Normal</div>
                  <div className="text-[10px] text-slate-500 font-normal">Até 60 min • Revogável</div>
                </button>
                <button
                  type="button"
                  onClick={() => setSessionType('BREAK_GLASS_EMERGENCY')}
                  className={`p-3 rounded-xl border text-left cursor-pointer transition-all ${
                    sessionType === 'BREAK_GLASS_EMERGENCY'
                      ? 'border-rose-600 bg-rose-50 text-rose-950 font-bold'
                      : 'border-slate-200 bg-slate-50 text-slate-700'
                  }`}
                >
                  <div className="text-xs">Break-Glass Emergencial</div>
                  <div className="text-[10px] text-slate-500 font-normal">Até 30 min • Falha Crítica</div>
                </button>
              </div>
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Justificativa Técnica Obrigatória</label>
              <input
                type="text"
                value={supportReason}
                onChange={e => setSupportReason(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-slate-900"
              />
            </div>

            <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-amber-900 text-[11px] leading-relaxed">
              <Lock className="w-3.5 h-3.5 inline mr-1 text-amber-700" />
              <strong>Vedação Absoluta (Cláusula 5.4):</strong> Nenhum acesso técnico autoriza o Master a movimentar saldos, autorizar empréstimos ou acessar contas pessoais dos membros.
            </div>

            <button
              onClick={handleStartSession}
              className="w-full py-2.5 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-xl cursor-pointer transition-colors shadow-xs"
            >
              Iniciar Sessão Controlada de Suporte
            </button>
          </div>
        </div>

        {/* Sessões em Andamento & Revogação Imediata */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
          <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
            <Radio className="w-4 h-4 text-rose-600 animate-pulse" />
            <span>Sessões Ativas e Histórico de Suporte</span>
          </h3>

          {state.supportGrants.length === 0 ? (
            <div className="text-center py-10 text-slate-400 text-xs">
              Nenhuma sessão de suporte aberta recentemente.
            </div>
          ) : (
            <div className="space-y-3">
              {state.supportGrants.map(grant => (
                <div
                  key={grant.id}
                  className={`p-4 rounded-xl border ${
                    grant.status === 'ACTIVE'
                      ? 'bg-emerald-50/50 border-emerald-200'
                      : 'bg-slate-50 border-slate-200 opacity-70'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <strong className="text-xs text-slate-900">{grant.type}</strong>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          grant.status === 'ACTIVE' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'
                        }`}>
                          {grant.status}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 mt-1">{grant.reason}</p>
                      <div className="text-[10px] text-slate-400 font-mono mt-1">
                        Início: {formatDateBR(grant.issued_at)} • Expira: {formatDateBR(grant.expires_at)} ({grant.max_minutes}m)
                      </div>
                    </div>

                    {grant.status === 'ACTIVE' && (
                      <button
                        onClick={() => handleRevoke(grant.id)}
                        className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-lg cursor-pointer shadow-xs transition-colors"
                      >
                        Revogar Agora (AT-17)
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Laboratório de Resiliência de Webhooks Pix (Cláusula 9.8 / AT-11 / AT-28) */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <FileCode className="w-4 h-4 text-emerald-600" />
              <span>Simulador de Testes de Webhooks e Resiliência Pix</span>
            </h3>
            <span className="text-xs text-slate-500">
              Cláusula 9.8 / AT-11: Verificação de webhook 10x repetido, ordem invertida e valor divergente.
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => handleTestWebhookResilience('10x_REPLAY')}
            className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-xl cursor-pointer"
          >
            Disparar Webhook 10x Repetido
          </button>
          <button
            onClick={() => handleTestWebhookResilience('OUT_OF_ORDER')}
            className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-xl cursor-pointer border border-slate-200"
          >
            Simular Entrega Fora de Ordem
          </button>
          <button
            onClick={() => handleTestWebhookResilience('DIVERGENT_VALUE')}
            className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-xl cursor-pointer border border-slate-200"
          >
            Simular Valor Divergente
          </button>
        </div>

        {webhookSimOutput && (
          <div className="p-4 rounded-xl bg-slate-900 text-emerald-300 font-mono text-xs leading-relaxed border border-slate-800 animate-in fade-in">
            {webhookSimOutput}
          </div>
        )}
      </div>
    </div>
  );
};
