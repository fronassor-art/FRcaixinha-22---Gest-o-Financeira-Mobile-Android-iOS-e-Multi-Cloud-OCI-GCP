import React, { useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { AppState } from '../services/store';
import { financialApi } from '../services/financialApiService';
import { DisplayContribution, contributionScopeKey } from '../services/contributionsData';
import { formatBRL } from '../services/financialEngine';
import { authService } from '../services/authService';
import { RealPixCheckout } from './RealPixCheckout';
import type { ProviderPixCheckout } from '../services/pixAutomationBoundary';
import {CycleContributionPolicy,parseCyclePriceInput} from '../services/cyclePriceBoundary';

interface ContributionsViewProps {
  state: AppState;
  onOpenPixModal: (params: {
    title: string; amount: number; description: string; recipientName: string;
    referenceId: string; onConfirm: () => void;
  }) => void;
}

type Result = { key: string; status: 'loading' | 'ready' | 'error'; items: DisplayContribution[]; message?: string };

export const ContributionsView: React.FC<ContributionsViewProps> = ({ state }) => {
  // O papel integra a chave: uma resposta do perfil administrador nunca pode ser exibida no perfil membro.
  const key = contributionScopeKey(state.currentUserId, state.currentTenantId, state.currentRole);
  const [revision, setRevision] = useState(0);
  const [checkout, setCheckout] = useState<ProviderPixCheckout | null>(null);
  const [pixBusyId, setPixBusyId] = useState<string | null>(null);
  const [pixCapability,setPixCapability]=useState<{key:string;enabled:boolean}>({key:'',enabled:false});
  const [pixFeedback, setPixFeedback] = useState('');
  const [cyclePrice,setCyclePrice]=useState<{key:string;policy:CycleContributionPolicy|null;error:string}>({key:'',policy:null,error:''});
  const [cycleInput,setCycleInput]=useState('');
  const [cycleReason,setCycleReason]=useState('');
  const [cycleBusy,setCycleBusy]=useState(false);
  const [cycleMessage,setCycleMessage]=useState('');
  useEffect(() => {
    // Never keep another tenant's QR or financial feedback after role switch.
    setCheckout(null);
    setPixFeedback('');
    setPixBusyId(null);
    setPixCapability({key:'',enabled:false});
    setCyclePrice({key:'',policy:null,error:''});
    setCycleMessage('');
    setCycleInput('');
    setCycleReason('');
    setCycleBusy(false);
  }, [key]);
  const [result, setResult] = useState<Result>({ key: '', status: 'loading', items: [] });

  useEffect(() => {
    let active = true;
    const tenant = state.currentTenantId;
    setResult({ key, status: 'loading', items: [] });
    if (!tenant || !state.currentUserId || state.currentRole === 'MASTER') {
      setResult({ key, status: 'error', items: [], message: 'Não há uma caixinha disponível para esta conta.' });
      return () => { active = false; };
    }
    financialApi.fetchPixAutomationCapabilities(tenant).then(value => {
      if(active)setPixCapability({key,enabled:value.pix_collection_enabled===true});
    }).catch(()=>{if(active)setPixCapability({key,enabled:false});});
    financialApi.fetchContributions(tenant).then(items => {
      if (active) setResult({ key, status: 'ready', items });
    }).catch(() => {
      if (active) setResult({ key, status: 'error', items: [], message: 'Não foi possível carregar as contribuições. Verifique a conexão e tente novamente.' });
    });
    return () => { active = false; };
  }, [key, revision, state.currentRole]);

  // M20400: admin-only policy retrieval; never show tenant A data in tenant B.
  useEffect(()=>{
    let active=true;
    if(state.currentRole==='TENANT_ADMIN' && state.currentTenantId){
      financialApi.fetchCycleContributionPolicy(state.currentTenantId).then(policy=>{
        if(!active)return;
        setCyclePrice({key,policy,error:''});
        setCycleInput((policy.amount_cents/100).toFixed(2).replace('.',','));
      }).catch(()=>{
        if(active)setCyclePrice({key,policy:null,error:
          'Política do ciclo indisponível. Confirme a migração 042 e a sessão.'});
      });
    }
    return ()=>{active=false};
  },[key,state.currentRole,state.currentTenantId]);

  async function submitCyclePrice(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();
    if(state.currentRole!=='TENANT_ADMIN'||!state.currentTenantId)return;
    const policy=cyclePrice.key===key?cyclePrice.policy:null;
    if(!policy)return;
    try{
      const amount=parseCyclePriceInput(cycleInput);
      if(cycleReason.trim().length<12||cycleReason.trim().length>500)
        throw new Error('Informe um motivo de auditoria com pelo menos 12 caracteres.');
      const snapshot=authService.captureSession();
      setCycleBusy(true);setCycleMessage('');
      const response=await financialApi.changeCycleContributionPrice(
        state.currentTenantId,policy.cycle_id,amount,cycleReason.trim());
      if(!authService.isSessionSnapshotCurrent(snapshot))return;
      setCycleMessage(response.change_status==='APPLIED'
        ? 'Valor atualizado e auditado. Nenhuma contribuição anterior foi modificada.'
        : 'Solicitação de revisão registrada. Cobranças já emitidas não foram alteradas.');
      const revised=await financialApi.fetchCycleContributionPolicy(state.currentTenantId);
      if(authService.isSessionSnapshotCurrent(snapshot))
        setCyclePrice({key,policy:revised,error:''});
    }catch(error){
      setCycleMessage(error instanceof Error?error.message:'Não foi possível registrar a revisão.');
    }finally{setCycleBusy(false);}
  }

  async function generateMonthlyPix(contributionId: string) {
    const tenant = state.currentTenantId;
    if (!tenant || !(pixCapability.key===key && pixCapability.enabled)) {
      setPixFeedback('Pix indisponível: integração de pagamentos ainda não autorizada.');
      return;
    }
    const snapshot = authService.captureSession();
    const startKey = key;
    setPixBusyId(contributionId);
    setPixFeedback('Solicitando QR Code vinculado à competência...');
    setCheckout(null);
    try {
      const response = await financialApi.createContributionPix(tenant, contributionId);
      if (!authService.isSessionSnapshotCurrent(snapshot) ||
          startKey !== contributionScopeKey(state.currentUserId, state.currentTenantId, state.currentRole)) return;
      setCheckout(response);
      setPixFeedback('Cobrança identificada. Aguarde a confirmação externa.');
    } catch (error) {
      if (authService.isSessionSnapshotCurrent(snapshot)) {
        setPixFeedback(error instanceof Error ? error.message :
          'Pix indisponível até integração e conciliação homologadas.');
      }
    } finally {
      if (authService.isSessionSnapshotCurrent(snapshot)) setPixBusyId(null);
    }
  }

  const pixEnabled=pixCapability.key===key && pixCapability.enabled;
  // Nunca mostre a resposta da conta anterior durante uma troca de sessão.
  const current = result.key === key ? result : { key, status: 'loading' as const, items: [] };
  return (
    <section className="space-y-4" aria-labelledby="contributions-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="contributions-title" className="text-lg font-bold text-slate-900">Contribuições</h2>
          <p className="text-sm text-slate-600">Valores consultados no servidor da sua caixinha.</p>
        </div>
        <button type="button" onClick={() => setRevision(n => n + 1)}
          className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-50">
          <RefreshCw className="h-4 w-4" aria-hidden="true" /> Atualizar
        </button>
      </div>
      {!pixEnabled && <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
        Pagamentos por Pix ainda não estão disponíveis. Nenhum valor é marcado como pago sem conciliação.
      </p>}
      {state.currentRole==='TENANT_ADMIN' && cyclePrice.key===key && (
        <section aria-label="Valor da contribuição por ciclo" className="space-y-3 rounded-xl border border-emerald-200 bg-white p-4">
          <h3 className="font-semibold text-emerald-950">Valor por cota do ciclo</h3>
          {cyclePrice.error && <p role="alert" className="text-sm text-rose-800">{cyclePrice.error}</p>}
          {cyclePrice.policy && <>
            <p className="text-sm text-slate-700">
              Ciclo {cyclePrice.policy.cycle_year} ({cyclePrice.policy.start_date.split('-').reverse().join('/')} a {cyclePrice.policy.end_date.split('-').reverse().join('/')}) · valor registrado: <strong>{formatBRL(cyclePrice.policy.amount_cents/100)}</strong>.
            </p>
            {cyclePrice.policy.registered_contributions>0 && <p className="text-sm text-amber-800">
              Existem {cyclePrice.policy.registered_contributions} competências registradas. Mudanças precisam de revisão auditada e não alteram cobranças automaticamente.
            </p>}
            {cyclePrice.policy.pending_requested_cents!==null && <p className="text-sm text-amber-800">
              Revisão solicitada: {formatBRL(cyclePrice.policy.pending_requested_cents/100)} (ainda não aplicada).
            </p>}
            <form className="grid gap-3 sm:grid-cols-2" onSubmit={event=>{void submitCyclePrice(event);}}>
              <label className="grid gap-1 text-sm text-slate-800">
                Novo valor por cota (R$)
                <input value={cycleInput} onChange={e=>setCycleInput(e.target.value)}
                  inputMode="decimal" maxLength={10} aria-label="Novo valor por cota"
                  className="rounded-lg border border-slate-300 px-3 py-2" required/>
              </label>
              <label className="grid gap-1 text-sm text-slate-800">
                Motivo da alteração
                <input value={cycleReason} onChange={e=>setCycleReason(e.target.value)}
                  maxLength={500} minLength={12} aria-label="Motivo da alteração da cota"
                  className="rounded-lg border border-slate-300 px-3 py-2" required/>
              </label>
              <button type="submit" disabled={cycleBusy}
                className="rounded-lg bg-emerald-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50 sm:col-span-2">
                {cycleBusy?'Registrando...':cyclePrice.policy.can_edit?'Salvar valor por cota e auditar':'Solicitar revisão auditada de valor'}
              </button>
            </form>
          </>}
          {cycleMessage && <p role="status" className="text-sm text-slate-800">{cycleMessage}</p>}
        </section>
      )}
      {pixFeedback && <p role="status" className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-800">
        {pixFeedback}
      </p>}
      <div aria-live="polite">
        {current.status === 'loading' && <p className="py-4 text-sm text-slate-600">Carregando contribuições...</p>}
        {current.status === 'error' && <div role="alert" className="flex gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"><AlertTriangle className="h-5 w-5 shrink-0" aria-hidden="true" />{current.message}</div>}
        {current.status === 'ready' && current.items.length === 0 && <p className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Nenhuma contribuição encontrada para esta conta.</p>}
        {current.status === 'ready' && current.items.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {current.items.map(c => (
              <article key={c.id} className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0"><h3 className="break-words font-semibold text-slate-900">{c.member_name || 'Contribuição'}</h3><p className="text-sm text-slate-600">Competência {c.competence}</p></div>
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-800">{c.payment_status}</span>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-x-3 gap-y-3 text-sm">
                  <div><dt className="text-slate-600">Vencimento</dt><dd className="font-medium text-slate-900">{c.due_date.split('-').reverse().join('/')}</dd></div>
                  <div><dt className="text-slate-600">Situação</dt><dd className="break-words font-medium text-slate-900">{c.due_status.replaceAll('_', ' ')}</dd></div>
                  <div><dt className="text-slate-600">Valor devido</dt><dd className="font-semibold text-slate-900">{formatBRL(c.amount_due)}</dd></div>
                  <div><dt className="text-slate-600">Valor pago</dt><dd className="font-semibold text-slate-900">{formatBRL(c.amount_paid)}</dd></div>
                  <div className="col-span-2 border-t border-slate-100 pt-3"><dt className="text-slate-600">Saldo em aberto</dt><dd className="text-base font-bold text-slate-900">{formatBRL(Math.max(0, c.amount_due - c.amount_paid))}</dd></div>
                </dl>
                {c.payment_status !== 'QUITADA' && c.amount_due > c.amount_paid && (
                  <button type="button"
                    disabled={!pixEnabled || pixBusyId !== null}
                    onClick={() => generateMonthlyPix(c.id)}
                    className="mt-4 w-full rounded-lg bg-emerald-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60">
                    {!pixEnabled ? 'Pix indisponível — aguardando integração' : pixBusyId === c.id ? 'Solicitando...' : 'Gerar Pix desta competência'}
                  </button>
                )}
              </article>
            ))}
          </div>
        )}
      </div>
      {checkout && state.currentTenantId && (
        <RealPixCheckout checkout={checkout} tenantId={state.currentTenantId}
                         onClose={() => setCheckout(null)} />
      )}
    </section>
  );
};
