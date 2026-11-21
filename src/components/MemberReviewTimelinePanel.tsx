import React,{useEffect,useRef,useState} from 'react';
import {AppState} from '../services/store';
import {authService} from '../services/authService';
import {financialApi} from '../services/financialApiService';
import {LifecycleItem} from '../services/memberLifecycleBoundary';
import {
  ReviewCapabilities,ReviewKind,ReviewTimeline
} from '../services/memberReviewBoundary';

type Snapshot={key:string,status:'loading'|'ready'|'error',data?:ReviewTimeline};
const DOC='CI-DOCUMENT-REVIEW-2027';

/** M1081: consulta e resposta auditável a um pedido — zero mudança patrimonial. */
export const MemberReviewTimelinePanel:React.FC<{
  state:AppState;request:LifecycleItem;onUpdated:()=>void
}>=({state,request,onUpdated})=>{
  const tenant=state.currentTenantId;
  const role=state.currentRole;
  const [revision,setRevision]=useState(0);
  const [cap,setCap]=useState<ReviewCapabilities|null>(null);
  const [timeline,setTimeline]=useState<Snapshot>({key:'',status:'loading'});
  const [kind,setKind]=useState<ReviewKind>('ADMIN_DOCUMENTS_REQUESTED');
  const [reference,setReference]=useState(DOC);
  const [confirmed,setConfirmed]=useState(false);
  const [sending,setSending]=useState(false);
  const [submitStatus,setSubmitStatus]=useState<'idle'|'success'|'error'>('idle');
  const requestKey=useRef<string|null>(null);
  const key=JSON.stringify([tenant,role,state.currentUserId,request.id,revision]);

  useEffect(()=>{
    let active=true;
    const session=authService.captureSession();
    setCap(null);setTimeline({key,status:'loading'});
    if(!tenant||!['TENANT_MEMBER','TENANT_ADMIN'].includes(role))
      return()=>{active=false};
    financialApi.fetchReviewCapabilities(tenant,2027).then(x=>{
      if(active&&authService.isSessionSnapshotCurrent(session))setCap(x);
    }).catch(()=>{
      if(active&&authService.isSessionSnapshotCurrent(session))setCap(null);
    });
    financialApi.fetchMemberReviewTimeline(tenant,2027,request.id).then(x=>{
      if(active&&authService.isSessionSnapshotCurrent(session))
        setTimeline({key,status:'ready',data:x});
    }).catch(()=>{
      if(active&&authService.isSessionSnapshotCurrent(session))
        setTimeline({key,status:'error'});
    });
    return()=>{active=false};
  },[key,tenant,role,state.currentUserId,request.id]);

  const current=timeline.key===key?timeline:{key,status:'loading' as const};
  const last=current.data?.latest_event_kind;
  const terminal=last==='ADMIN_REVIEW_ACCEPTED_SANDBOX'||
                 last==='ADMIN_REVIEW_REJECTED_SANDBOX';
  const selfReview=role==='TENANT_ADMIN'&&request.requested_by_user_id===state.currentUserId;
  const allowed=role==='TENANT_MEMBER'
    ?cap?.can_submit_contestation===true &&
      request.membership_id===current.data?.membership_id &&
      (last==='ADMIN_DOCUMENTS_REQUESTED'||
       last==='ADMIN_REVIEW_REJECTED_SANDBOX'||
       (request.request_kind==='DELINQUENCY_REVIEW'&&last===null))
    :cap?.can_review_independently===true&&!selfReview&&
      !terminal;
  const chosenKind:ReviewKind=role==='TENANT_MEMBER'?'MEMBER_CONTESTED':kind;
  const canSubmit=allowed&&confirmed&&current.status==='ready'&&!sending&&
                  /^[A-Za-z0-9._:-]{8,120}$/.test(reference);
  const submit=async()=>{
    if(!canSubmit||!tenant)return;
    const snapshot=authService.captureSession();
    setSending(true);setSubmitStatus('idle');
    try{
      if(!requestKey.current){
        if(!globalThis.crypto?.randomUUID)throw Error('UUID seguro indisponível');
        requestKey.current=globalThis.crypto.randomUUID();
      }
      await financialApi.submitMemberReviewEventSandbox(
        tenant,2027,request.id,chosenKind,requestKey.current,reference
      );
      if(!authService.isSessionSnapshotCurrent(snapshot))return;
      setSubmitStatus('success');setConfirmed(false);
      requestKey.current=null;
      setRevision(x=>x+1);onUpdated();
    }catch{
      if(authService.isSessionSnapshotCurrent(snapshot))setSubmitStatus('error');
    }finally{
      if(authService.isSessionSnapshotCurrent(snapshot))setSending(false);
    }
  };

  if(!tenant||!['TENANT_MEMBER','TENANT_ADMIN'].includes(role))return null;
  return <section className="mt-3 rounded-lg border border-slate-300 p-3 space-y-3"
    aria-label="Análise documental de solicitação">
    <h4 className="font-semibold">Análise e contestação — apenas homologação</h4>
    {current.status==='loading'&&
      <p role="status">Consultando eventos do pedido...</p>}
    {current.status==='error'&&
      <p role="alert">Histórico de revisão indisponível. É necessária a migration 029
        em um banco de homologação; nenhum estado foi alterado.</p>}
    {current.status==='ready'&&current.data&&
      <>
        <p>Etapa documental: {current.data.pending_technical_review
          ?'em análise':'revisão documental concluída'}. Isso não altera
          direitos ou obrigações financeiras.</p>
        <ol className="space-y-2 list-decimal pl-4 text-sm">
          {current.data.items.map(item=><li key={item.event_id}>
            <strong>{item.event_kind}</strong> — evidência: {item.evidence_reference}
            <span className="block text-slate-600">Evento #{item.event_seq}</span>
          </li>)}
        </ol>
        {current.data.items.length===0&&
          <p className="text-sm">Ainda não há eventos de revisão.</p>}
      </>}
    {selfReview&&
      <p className="text-sm text-amber-900">
        Outra pessoa administradora deve revisar este pedido.
        Autoaprovação não é permitida.
      </p>}
    {cap?.schema_ready===false&&
      <p className="text-sm text-amber-900">
        Migração 029 não instalada; ações de teste desabilitadas.
      </p>}
    {allowed&&current.status==='ready'&&
      <div className="space-y-3">
        {role==='TENANT_ADMIN'&&
          <label className="block text-sm">
            Registro documental técnico
            <select value={kind} className="block mt-1 w-full rounded-lg border p-2"
              onChange={e=>{
                setKind(e.target.value as ReviewKind);
                requestKey.current=null;setConfirmed(false);setSubmitStatus('idle');
              }}>
              <option value="ADMIN_DOCUMENTS_REQUESTED">Solicitar documentos</option>
              <option value="ADMIN_REVIEW_ACCEPTED_SANDBOX">Aceitar análise documental de teste</option>
              <option value="ADMIN_REVIEW_REJECTED_SANDBOX">Rejeitar análise documental de teste</option>
            </select>
          </label>}
        <label className="block text-sm">
          Referência técnica do documento (sem dados pessoais)
          <input className="block mt-1 w-full rounded-lg border p-2"
            value={reference} maxLength={120}
            onChange={e=>{
              setReference(e.target.value);
              requestKey.current=null;setConfirmed(false);setSubmitStatus('idle');
            }}/>
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={confirmed}
            onChange={e=>setConfirmed(e.target.checked)}/>
          <span>Confirmo este evento sintético. Não é aprovação jurídica,
            não bloqueia membro, não muda rateio e não faz Pix.</span>
        </label>
        <button type="button" disabled={!canSubmit} onClick={submit}
          className="rounded-lg border border-slate-300 px-4 py-2 disabled:opacity-50">
          {sending?'Registrando evento...':
           role==='TENANT_MEMBER'?'Registrar contestação de teste':
           'Registrar decisão documental de teste'}
        </button>
      </div>}
    {submitStatus==='success'&&
      <p role="status">Evento documental confirmado no banco de homologação.</p>}
    {submitStatus==='error'&&
      <p role="alert">Registro não confirmado. A mesma chave será usada na
        próxima tentativa para evitar duplicação.</p>}
    <p className="text-xs text-amber-900">
      Evento registrado não autoriza fechamento, lucro, restituição, Pix ou
      alteração de associação. Dados cadastrais não são prova bancária.
    </p>
  </section>;
};
