import React, { useEffect, useRef, useState } from 'react';
import { AppState } from '../services/store';
import { financialApi } from '../services/financialApiService';
import type {DisplayLoan} from '../services/loanReadBoundary';
import type {LoanSimulation} from '../services/loanSimulationBoundary';
import {loanSimulationFailureMessage} from '../services/loanSimulationFeedback';
import {authService} from '../services/authService';

interface Props { state: AppState }
type State = { key: string; status: 'loading' | 'ready' | 'error'; loans: DisplayLoan[] };

export const ServerLoansView: React.FC<Props> = ({ state }) => {
  const [revision, setRevision] = useState(0);
  const key = [state.currentUserId, state.currentRole, state.currentTenantId, revision].join(':');
  const latestKey = useRef(key);
  latestKey.current = key;
  const simulationRequestId = useRef(0);
  const [result, setResult] = useState<State>({ key: '', status: 'loading', loans: [] });
  const [amount, setAmount] = useState('500');
  const [months, setMonths] = useState('5');
  const [simulation, setSimulation] = useState<LoanSimulation | null>(null);
  const [simulationStatus, setSimulationStatus] = useState('');

  useEffect(() => {
    let active = true;
    const snapshot = authService.captureSession();
    simulationRequestId.current++;
    setSimulation(null);
    setSimulationStatus('');
    setResult({ key, status: 'loading', loans: [] });
    if (state.currentRole === 'MASTER' || !state.currentTenantId || !state.currentUserId) {
      setResult({ key, status: 'error', loans: [] });
      return () => { active = false; };
    }
    financialApi.fetchLoans(state.currentTenantId).then(loans => {
      if (active && authService.isSessionSnapshotCurrent(snapshot))
        setResult({ key, status: 'ready', loans });
    }).catch(() => {
      if (active && authService.isSessionSnapshotCurrent(snapshot))
        setResult({ key, status: 'error', loans: [] });
    });
    return () => { active = false; };
  }, [key, revision]);

  const current: State = result.key === key
    ? result : { key, status: 'loading', loans: [] };
  const format = (n: number) => new Intl.NumberFormat('pt-BR',
    { style: 'currency', currency: 'BRL' }).format(Number(n));

  async function runSimulation(event: React.FormEvent) {
    event.preventDefault();
    const requestId=++simulationRequestId.current;
    setSimulation(null);
    setSimulationStatus('Calculando no FastAPI...');
    const principal = Number(amount);
    const term_months = Number(months);
    if (!Number.isFinite(principal) || principal <= 0 || principal > 50000 ||
        !Number.isInteger(term_months) || term_months < 1 || term_months > 6) {
      setSimulationStatus('Informe um valor de 0,01 a 50.000 e de 1 a 6 parcelas.');
      return;
    }
    const requestedKey = key;
    try {
      const data = await financialApi.simulateLoan(state.currentTenantId, { principal, term_months });
      if (requestedKey !== latestKey.current || requestId !== simulationRequestId.current) return;
      setSimulation(data);
      setSimulationStatus('Simulação matemática concluída no servidor. Não equivale a oferta, aprovação ou desembolso.');
    } catch (error: unknown) {
      if (requestedKey === latestKey.current && requestId === simulationRequestId.current) {
        setSimulationStatus(loanSimulationFailureMessage(error));
      }
    }
  }

  return (
    <section className="space-y-5">
      <header className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-bold text-slate-900">
          {state.currentRole === 'TENANT_ADMIN' ? 'Empréstimos da Caixinha' : 'Meus Empréstimos'}
        </h2>
        <p className="text-sm text-slate-700">
          Consultas autorizadas no PostgreSQL. O administrador visualiza somente sua caixinha;
          o membro visualiza somente seus próprios empréstimos.
        </p>
        <button type="button" onClick={() => setRevision(n => n + 1)}
          className="mt-3 rounded-lg border border-slate-300 px-4 py-2 text-sm">Atualizar</button>
      </header>
      {current.status === 'loading' && <p role="status">Carregando empréstimos...</p>}
      {current.status === 'error' && <p role="alert" className="rounded-xl bg-rose-50 p-4 text-rose-900">
        Não foi possível consultar os empréstimos. Nenhum dado demonstrativo será exibido.
      </p>}
      {current.status === 'ready' && current.loans.length === 0 && (
        <p className="rounded-xl border border-slate-200 bg-white p-4">
          Nenhum empréstimo registrado para esta conta.
        </p>
      )}
      {current.status === 'ready' && current.loans.map(loan => (
        <article key={loan.id} className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="font-semibold text-slate-900">{loan.borrower_name || 'Empréstimo'}</h3>
          <p className="text-sm text-slate-600">Situação: {loan.status} • {loan.term_months} parcelas</p>
          <p className="mt-2 text-sm text-slate-700">
            Principal: {format(loan.principal)} • Prestação: {format(loan.monthly_payment)}
          </p>
          <p className="text-sm text-slate-700">Juros calculados: {format(loan.total_interest)}</p>
          <div className="mt-3 text-sm text-slate-600">
            {loan.installments.map(inst => (
              <p key={inst.id}>Parcela {inst.installment_number}: {inst.due_date} • {inst.status}</p>
            ))}
          </div>
        </article>
      ))}

      <form onSubmit={runSimulation} className="rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="font-semibold text-slate-900">Simulação Tabela Price — ambiente de testes</h3>
        <p className="mt-1 text-sm text-slate-600">
          Este cálculo é ilustrativo. Taxas e prazos definitivos dependem da política
          vigente da caixinha, da elegibilidade e das autorizações contratuais.
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-sm text-slate-800">
            Valor (R$)
            <input type="number" min="0.01" max="50000" step="0.01" value={amount}
              onChange={event => {
                simulationRequestId.current++;
                setSimulation(null);
                setSimulationStatus('');
                setAmount(event.target.value);
              }}
              className="rounded-lg border border-slate-300 p-2"/>
          </label>
          <label className="grid gap-1 text-sm text-slate-800">
            Quantidade de parcelas
            <select value={months} onChange={event => {
                simulationRequestId.current++;
                setSimulation(null);
                setSimulationStatus('');
                setMonths(event.target.value);
              }}
              className="rounded-lg border border-slate-300 p-2">
              {[1,2,3,4,5,6].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <button type="submit" className="rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white">
            Simular no servidor
          </button>
        </div>
        {simulationStatus && <p role="status" className="mt-3 text-sm">{simulationStatus}</p>}
        {simulation && <div className="mt-3 space-y-1 text-sm">
          <p>Taxa da política vigente da caixinha: {(Number(simulation.monthly_rate) * 100).toFixed(2)}% a.m.</p>
          <p>Prestação uniforme: {format(simulation.uniform_payment)}</p>
          <p>Última prestação: {format(simulation.last_payment)}</p>
          <p>Juros: {format(simulation.total_interest)} • Total: {format(simulation.total_payable)}</p>
        </div>}
      </form>
      <p className="rounded-xl bg-amber-50 p-4 text-sm text-amber-950">
        Solicitação, aprovação, liberação, recebimento e quitação reais permanecerão
        indisponíveis até completar as respectivas integrações e validações.
      </p>
    </section>
  );
};
