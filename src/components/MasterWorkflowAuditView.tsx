import React,{useEffect,useState} from 'react';
import {RefreshCw,ShieldAlert} from 'lucide-react';
import {financialApi} from '../services/financialApiService';
import {
  WorkflowContract,WorkflowPreview,WorkflowState,ActorRole,WORKFLOW_STATES,
} from '../services/masterWorkflow';
import {AppState} from '../services/store';

const readable:Record<WorkflowState,string>={
  REQUESTED:'Solicitado',EMAIL_VERIFIED:'E-mail verificado',
  MASTER_REVIEW:'Revisão Master',APPROVED:'Aprovado (hipotético)',
  INVITE_PREPARED:'Convite preparado',DELIVERED:'Entregue',
  ACCEPTED:'Aceito',ACTIVE:'Ativo (hipotético)',
  REJECTED:'Rejeitado',REVOKED:'Revogado',EXPIRED:'Expirado',
};
export const MasterWorkflowAuditView:React.FC<{state:AppState}>=({state})=>{
  const scope=[state.currentUserId,state.currentRole,state.currentTenantId].join('|');
  const [contract,setContract]=useState<{scope:string;status:'loading'|'ready'|'error';data?:WorkflowContract}>({
    scope:'',status:'loading',
  });
  const [retry,setRetry]=useState(0);
  const key=scope+'|'+retry;
  const [current,setCurrent]=useState<WorkflowState>('REQUESTED');
  const [proposed,setProposed]=useState<WorkflowState>('EMAIL_VERIFIED');
  const [actor,setActor]=useState<ActorRole>('MASTER');
  const [selfApproval,setSelfApproval]=useState(false);
  const [emailVerified,setEmailVerified]=useState(false);
  const [tenantActive,setTenantActive]=useState(false);
  const [independentApproval,setIndependentApproval]=useState(false);
  const [tokenValid,setTokenValid]=useState(false);
  const [replay,setReplay]=useState(false);
  const [expected,setExpected]=useState(0);
  const [observed,setObserved]=useState(0);
  const [result,setResult]=useState<WorkflowPreview|null>(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(false);

  useEffect(()=>{
    if(state.currentRole!=='MASTER')return;
    let alive=true;
    setContract({scope:key,status:'loading'});
    financialApi.fetchMasterWorkflowContract()
      .then(data=>{if(alive)setContract({scope:key,status:'ready',data});})
      .catch(()=>{if(alive)setContract({scope:key,status:'error'});});
    return ()=>{alive=false;};
  },[key,state.currentRole]);
  useEffect(()=>{
    setResult(null);setError('');setLoading(false);
  },[scope]);
  if(state.currentRole!=='MASTER'){
    return <section role="alert">Simulação exclusiva do Master.</section>;
  }
  const active=contract.scope===key?contract:{scope:key,status:'loading' as const};
  const data=active.status==='ready'?active.data:undefined;
  const preview=async(event:React.FormEvent)=>{
    event.preventDefault();if(!data||loading)return;
    setError('');setResult(null);setLoading(true);
    try{
      const id=crypto.randomUUID();
      const response=await financialApi.previewMasterWorkflowTransition({
        currentState:current,proposedState:proposed,actorRole:actor,
        candidateIsActor:selfApproval,emailVerified,tenantActive,
        independentApproval,tokenValid,expectedRevision:expected,
        observedRevision:observed,idempotencyKey:id,
        previouslyUsedKeys:replay?[id]:[],
      });
      setResult(response);
    }catch{
      setError('Falha na simulação. Nenhuma operação foi executada.');
    }finally{setLoading(false);}
  };
  return <section className="fr-light-card space-y-3 rounded-2xl p-4"
    aria-label="Simulação de fluxo e auditoria">
    <h3 className="text-lg font-bold text-[#123d2b]">Simulador de fluxo e auditoria</h3>
    <p className="text-sm text-[#52685a]">
      Testa cenários fictícios de convite. Nada é gravado, auditado ou enviado.
    </p>
    {active.status==='loading'&&<p role="status">Carregando regras do fluxo...</p>}
    {active.status==='error'&&<div role="alert">
      <p>Contrato do fluxo indisponível; simulação bloqueada.</p>
      <button type="button" onClick={()=>setRetry(n=>n+1)}
        className="mt-2 flex min-h-11 items-center gap-2 text-[#075337]">
        <RefreshCw className="h-4 w-4"/>Tentar novamente
      </button>
    </div>}
    {data&&<form className="space-y-3" onSubmit={preview}>
      <label htmlFor="flow-current" className="block text-sm font-semibold">Estado atual hipotético</label>
      <select id="flow-current" value={current} onChange={e=>setCurrent(e.target.value as WorkflowState)}
        className="min-h-11 w-full rounded-lg border bg-white px-3 text-base">
        {WORKFLOW_STATES.map(x=><option key={x} value={x}>{readable[x]}</option>)}
      </select>
      <label htmlFor="flow-proposed" className="block text-sm font-semibold">Próxima etapa pretendida</label>
      <select id="flow-proposed" value={proposed} onChange={e=>setProposed(e.target.value as WorkflowState)}
        className="min-h-11 w-full rounded-lg border bg-white px-3 text-base">
        {WORKFLOW_STATES.map(x=><option key={x} value={x}>{readable[x]}</option>)}
      </select>
      <label htmlFor="flow-actor" className="block text-sm font-semibold">Papel do ator hipotético</label>
      <select id="flow-actor" value={actor} onChange={e=>setActor(e.target.value as ActorRole)}
        className="min-h-11 w-full rounded-lg border bg-white px-3 text-base">
        <option value="MASTER">Master</option>
        <option value="TENANT_ADMIN">Administrador de caixinha</option>
        <option value="TENANT_MEMBER">Membro</option>
      </select>
      <div className="space-y-2">
        {([
          ['candidate',selfApproval,setSelfApproval,'Candidato é o próprio aprovador'],
          ['email',emailVerified,setEmailVerified,'E-mail validado (simulado)'],
          ['tenant',tenantActive,setTenantActive,'Caixinha ativa (simulado)'],
          ['dual',independentApproval,setIndependentApproval,'Aprovação independente (simulada)'],
          ['token',tokenValid,setTokenValid,'Token dentro da validade (simulado)'],
          ['replay',replay,setReplay,'Simular reutilização de chave de idempotência'],
        ] as const).map(([id,checked,change,label])=>
          <label key={id} className="flex min-h-10 items-center gap-3 text-sm text-[#274b38]">
            <input type="checkbox" checked={checked}
              onChange={e=>change(e.target.checked)} className="h-5 w-5"/>
            {label}
          </label>)}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="flow-expected" className="block text-sm font-semibold">Revisão esperada</label>
          <input id="flow-expected" type="number" min={0} max={1000000}
            value={expected} onChange={e=>setExpected(Number(e.target.value))}
            className="min-h-11 w-full rounded-lg border bg-white px-3 text-base"/>
        </div>
        <div>
          <label htmlFor="flow-observed" className="block text-sm font-semibold">Revisão observada</label>
          <input id="flow-observed" type="number" min={0} max={1000000}
            value={observed} onChange={e=>setObserved(Number(e.target.value))}
            className="min-h-11 w-full rounded-lg border bg-white px-3 text-base"/>
        </div>
      </div>
      <button type="submit" disabled={loading}
        className="fr-gold-button min-h-11 w-full rounded-lg px-3 text-sm font-semibold disabled:opacity-60">
        {loading?'Simulando...':'Simular transição sem executar'}
      </button>
    </form>}
    {error&&<p role="alert" className="text-sm text-[#8f3828]">{error}</p>}
    {result&&<div role="status" className="rounded-xl border border-[#dcbf81] p-3">
      <div className="flex items-center gap-2 font-bold text-[#8b4b1d]">
        <ShieldAlert className="h-5 w-5"/>Execução real bloqueada
      </div>
      <p className="mt-2 text-sm text-[#405d4b]">
        Transição prevista no desenho: {result.graph_valid?'Sim':'Não'}.
        Conflito de revisão: {result.revision_conflict?'Sim':'Não'}.
        Reutilização de chave: {result.idempotency_replay_detected?'Sim':'Não'}.
      </p>
      <p className="mt-2 text-xs text-[#52685a]">
        Motivos: {result.reasons.join(', ')}
      </p>
      <p className="mt-2 break-all text-[11px] text-[#64796a]">
        Impressão digital da simulação (não é auditoria):
        {result.scenario_fingerprint}
      </p>
      <strong className="mt-2 block text-sm text-[#8b4b1d]">
        Nenhum convite, auditoria persistida ou alteração de conta.
      </strong>
    </div>}
    {data&&<div className="rounded-xl border border-[#d3dfd3] p-3">
      <p className="font-semibold text-sm text-[#153e2a]">
        Contrato futuro de auditoria · {data.proposed_audit_fields.length} campos
      </p>
      <p className="mt-1 text-xs text-[#52685a]">
        Os {data.transaction_guards.length} controles transacionais exigem aprovação
        específica; não estão operacionais.
      </p>
    </div>}
  </section>;
};
