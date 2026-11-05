import React, { useEffect, useState } from 'react';
import type { AppState } from '../services/store';
import type { DisplayLoan } from '../services/loanReadBoundary';
import type { LoanSimulation } from '../services/loanSimulationBoundary';
import type { ProviderPixCheckout } from '../services/pixAutomationBoundary';
import { financialApi } from '../services/financialApiService';
import { authService } from '../services/authService';
import { RealPixCheckout } from './RealPixCheckout';

interface Props {
  state: AppState;
  loans: DisplayLoan[];
  simulation: LoanSimulation | null;
  principal: number;
  months: number;
  onRefresh: () => void;
}

export const LoansAutomationPanel: React.FC<Props> = ({
  state, loans, simulation, principal, months, onRefresh,
}) => {
  const [checkout, setCheckout] = useState<ProviderPixCheckout | null>(null);
  const [working, setWorking] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const contextKey = [state.currentUserId,state.currentTenantId,state.currentRole].join(':');
  useEffect(() => {
    setCheckout(null);
    setWorking(null);
    setMessage('');
  }, [contextKey]);

  async function run(key: string, job: () => Promise<string>) {
    const snapshot = authService.captureSession();
    setMessage('Conferindo autorização e persistência no servidor...');
    setWorking(key);
    try {
      const result = await job();
      if (!authService.isSessionSnapshotCurrent(snapshot)) return;
      setMessage(result);
      onRefresh();
    } catch (e) {
      if (authService.isSessionSnapshotCurrent(snapshot))
        setMessage(e instanceof Error ? e.message :
          'Operação financeira não autorizada pelo servidor.');
    } finally {
      if (authService.isSessionSnapshotCurrent(snapshot)) setWorking(null);
    }
  }

  function requestLoan() {
    const tenant = state.currentTenantId;
    if (!tenant || !simulation || state.currentRole !== 'TENANT_MEMBER') return;
    void run('new-loan', async () => {
      const data = await financialApi.requestLoan(tenant, {
        principal, term_months: months,
      });
      if (!data || data.status !== 'SOLICITADO' || typeof data.id !== 'string') {
        throw new Error('Pedido não registrado no banco.');
      }
      return 'Pedido registrado. A decisão depende do Administrador Contratante.';
    });
  }

  function payout(loanId: string) {
    const tenant = state.currentTenantId;
    if (!tenant || state.currentRole !== 'TENANT_ADMIN') return;
    void run(loanId, async () => {
      const preview = await financialApi.loanDisbursementPreview(tenant, loanId);
      if (!preview || preview.destination_registered !== true ||
          preview.reservation_confirmed !== true ||
          preview.pix_out_available !== true) {
        throw new Error('Pix de saída bloqueado: falta cadastrar e validar destino, reservar caixa ou obter autorização Payouts do Mercado Pago.');
      }
      const response = await financialApi.authorizeLoanPixPayout(tenant, loanId);
      if (response?.status === 'PENDENTE_CONCILIACAO') {
        return 'Ordem registrada; aguardando prova de envio ao membro. Não é empréstimo desembolsado.';
      }
      throw new Error('Provedor não confirmou a operação. Consultar protocolo antes de repetir.');
    });
  }

  function installmentPix(loanId: string, installmentId: string) {
    const tenant = state.currentTenantId;
    if (!tenant) return;
    const originalSession = authService.captureSession();
    void run(installmentId, async () => {
      const checkoutResult = await financialApi.createLoanInstallmentPix(
        tenant, loanId, installmentId,
      );
      // A delayed response cannot reopen the previous tenant's Pix after switch.
      if (!authService.isSessionSnapshotCurrent(originalSession)) {
        return 'Contexto alterado. Cobrança descartada da tela.';
      }
      setCheckout(checkoutResult);
      return 'Cobrança Pix criada e vinculada à parcela. Aguardando conciliação.';
    });
  }

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4"
             aria-label="Automação financeira de empréstimos">
      <header>
        <h3 className="font-bold text-slate-900">Gestão automatizada do empréstimo</h3>
        <p className="text-sm text-slate-600">
          Solicitações e ordens são feitas no aplicativo; o Mercado Pago executa
          somente operações externas autorizadas pelo servidor.
        </p>
      </header>
      {state.currentRole === 'TENANT_MEMBER' && simulation && (
        <button type="button" disabled={working !== null}
          onClick={requestLoan}
          className="rounded-lg bg-emerald-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60">
          {working === 'new-loan' ? 'Registrando...' : 'Solicitar empréstimo simulado'}
        </button>
      )}
      {loans.map(loan => (
        <div key={loan.id} className="space-y-2 rounded-xl border border-slate-200 p-3">
          <p className="text-sm font-semibold text-slate-900">
            Empréstimo {loan.id.slice(0,8)} • {loan.status}
          </p>
          {state.currentRole === 'TENANT_ADMIN' && loan.status === 'SOLICITADO' && (
            <p className="text-xs text-amber-900">
              Análise administrativa: aprovação financeira definitiva exige
              reserva atômica e cronograma após o desembolso confirmado.
            </p>
          )}
          {state.currentRole === 'TENANT_ADMIN' && loan.status === 'APROVADO' && (
            <button type="button" disabled={working !== null}
              onClick={() => payout(loan.id)}
              className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-60">
              Validar destino e ordenar Pix ao membro
            </button>
          )}
          {loan.status === 'DESEMBOLSADO' && loan.installments.map(inst => (
            <div key={inst.id} className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span>Parcela {inst.installment_number} • {inst.due_date} • {inst.status}</span>
              {inst.status !== 'QUITADA' && (
                <button type="button" disabled={working !== null}
                  onClick={() => installmentPix(loan.id,inst.id)}
                  className="rounded-lg bg-emerald-900 px-3 py-2 font-semibold text-white disabled:opacity-60">
                  Gerar Pix da parcela
                </button>
              )}
            </div>
          ))}
        </div>
      ))}
      {message && <p role="status"
        className="rounded-lg border border-slate-200 p-3 text-sm">{message}</p>}
      {checkout && state.currentTenantId && (
        <RealPixCheckout checkout={checkout} tenantId={state.currentTenantId}
                         onClose={() => setCheckout(null)} />
      )}
      <p className="text-xs text-amber-900">
        Nenhum botão confirma pagamento por conta própria. Envio, recebimento,
        juros, amortização e comprovantes dependem de conciliação externa.
      </p>
    </section>
  );
};
