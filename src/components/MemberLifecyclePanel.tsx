import React,{useEffect,useRef,useState} from 'react';
import {AppState} from '../services/store';
import {authService} from '../services/authService';
import {financialApi} from '../services/financialApiService';
import {LifecycleQueue,LifecycleCapabilities,LifecycleClosingGates} from '../services/memberLifecycleBoundary';
import {MemberReviewTimelinePanel} from './MemberReviewTimelinePanel';
import {TenantMember} from '../services/tenantReadBoundary';

type Snapshot={key:string,status:'loading'|'ready'|'error',data?:LifecycleQueue};
type Submission={status:'idle'|'sending'|'success'|'error',id?:string};
/** M921+: criação de pedidos APENAS no sandbox anunciado pelo backend. */
export const MemberLifecyclePanel:React.FC<{state:AppState}>=({state})=>{
 const tenant=state.currentTenantId;
 const role=state.currentRole;
 const [refresh,setRefresh]=useState(0);
 const key=JSON.stringify([tenant,role,state.currentUserId,2027,refresh]);
 const [view,setView]=useState<Snapshot>({key:'',status:'loading'});
 const [cap,setCap]=useState<LifecycleCapabilities|null>(null);
 const [closing,setClosing]=useState<LifecycleClosingGates|null>(null);
 const [members,setMembers]=useState<TenantMember[]>([]);
 const [selected,setSelected]=useState('');
 const [selectedReview,setSelectedReview]=useState('');
 const [confirmed,setConfirmed]=useState(false);
 const [submission,setSubmission]=useState<Submission>({status:'idle'});
 const requestKey=useRef<string|null>(null);

 useEffect(()=>{
   let mounted=true;
   const s=authService.captureSession();
   setCap(null);setMembers([]);setSelected('');setSelectedReview('');setConfirmed(false);
   setSubmission({status:'idle'});requestKey.current=null;
   if(!tenant||!['TENANT_ADMIN','TENANT_MEMBER'].includes(role))
     return()=>{mounted=false;};
   financialApi.fetchMemberLifecycleCapabilities(tenant,2027).then(data=>{
     if(mounted&&authService.isSessionSnapshotCurrent(s))setCap(data);
   }).catch(()=>{if(mounted&&authService.isSessionSnapshotCurrent(s))setCap(null)});
   if(role==='TENANT_ADMIN'){
     financialApi.fetchTenantMembers(tenant).then(data=>{
       if(mounted&&authService.isSessionSnapshotCurrent(s))
         setMembers(data.members.filter(x=>x.role==='TENANT_MEMBER'&&x.status==='ATIVA'));
     }).catch(()=>{if(mounted&&authService.isSessionSnapshotCurrent(s))setMembers([])});
   }
   return ()=>{mounted=false;};
 },[tenant,role,state.currentUserId]);

 useEffect(()=>{
   let mounted=true;
   const s=authService.captureSession();
   if(!tenant||!['TENANT_ADMIN','TENANT_MEMBER'].includes(role)){
     setView({key,status:'error'});
     return ()=>{mounted=false;};
   }
   setView({key,status:'loading'});
   financialApi.fetchMemberLifecycleQueue(tenant,2027)
     .then(data=>{
       if(mounted&&authService.isSessionSnapshotCurrent(s))
         setView({key,status:'ready',data});
     })
     .catch(()=>{
       if(mounted&&authService.isSessionSnapshotCurrent(s))
         setView({key,status:'error'});
     });
   return ()=>{mounted=false;};
 },[key,tenant,role,state.currentUserId]);

 useEffect(()=>{
   let mounted=true;
   const snapshot=authService.captureSession();
   setClosing(null);
   if(!tenant||role!=='TENANT_ADMIN')
     return()=>{mounted=false;};
   financialApi.fetchLifecycleClosingGates(tenant,2027)
     .then(data=>{
       if(mounted&&authService.isSessionSnapshotCurrent(snapshot))
         setClosing(data);
     })
     .catch(()=>{
       if(mounted&&authService.isSessionSnapshotCurrent(snapshot))
         setClosing(null);
     });
   return()=>{mounted=false;};
 },[tenant,role,state.currentUserId,refresh]);

 if(!tenant||!['TENANT_ADMIN','TENANT_MEMBER'].includes(role))return null;
 const current=view.key===key?view:{key,status:'loading' as const};
 const ownCap=cap?.tenant_id===tenant&&cap.role===role?cap:null;
 const canSubmit=role==='TENANT_MEMBER'
   ?ownCap?.can_submit_voluntary_exit===true
   :ownCap?.can_submit_delinquency_review===true;
 const supported=canSubmit&&confirmed&&
   (role==='TENANT_MEMBER'||selected.length>0)&&
   submission.status!=='sending';
 const submit=async()=>{
   if(!supported||!tenant)return;
   setSubmission({status:'sending'});
   const snapshot=authService.captureSession();
   try{
     if(!requestKey.current){
       if(!globalThis.crypto?.randomUUID)throw Error('UUID seguro não disponível');
       requestKey.current=globalThis.crypto.randomUUID();
     }
     const record=await financialApi.submitMemberLifecycleSandbox(
       tenant,2027,role==='TENANT_MEMBER'
         ?'VOLUNTARY_EXIT':'DELINQUENCY_REVIEW',
       requestKey.current,
       role==='TENANT_ADMIN'?selected:undefined
     );
     if(!authService.isSessionSnapshotCurrent(snapshot))return;
     setSubmission({status:'success',id:record.id});
     setConfirmed(false);
     requestKey.current=null;
     setRefresh(n=>n+1);
   }catch{
     if(authService.isSessionSnapshotCurrent(snapshot))
       setSubmission({status:'error'});
   }
 };

 return <section aria-labelledby="lifecycle-title"
   className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
   <h3 id="lifecycle-title" className="text-base font-bold text-slate-900">
     Solicitações e revisão de membros — ciclo 2027
   </h3>
   <p className="text-sm text-slate-700">
     Fila de homologação com rastreabilidade de saídas voluntárias e pedidos
     de revisão de inadimplência. Registrar um pedido não encerra vínculo,
     não exclui rateio, não devolve dinheiro e não executa Pix.
   </p>
   <button type="button" className="rounded-lg border border-slate-300 px-4 py-2"
     onClick={()=>setRefresh(n=>n+1)}>Atualizar histórico</button>
   {current.status==='loading'&&
     <p role="status" className="text-sm">Consultando solicitações...</p>}
   {current.status==='error'&&
     <p role="status" className="text-sm text-amber-900">
       Histórico não disponível nesta instalação. A migration 028 e a
       configuração de homologação isolada precisam estar ativadas no servidor.
       Nenhum pedido ou direito foi alterado.
     </p>}
   {current.status==='ready'&&current.data&&
     <div className="space-y-2 text-sm">
       <p>{current.data.items.length} solicitação(ões) registradas na fila.</p>
       <ul className="space-y-2">
         {current.data.items.map(item=>
           <li key={item.id} className="rounded-lg border border-slate-200 p-3">
             <strong>{item.request_kind==='VOLUNTARY_EXIT'
               ?'Saída voluntária':'Revisão de inadimplência'}</strong>
             <div>Identificador: {item.id}</div>
             <div>Vínculo: {item.membership_id}</div>
             <div>Situação documental: {item.technical_review_pending
               ?'revisão pendente':'revisão técnica concluída'}</div>
             {item.latest_review_event&&
               <div>Último evento: {item.latest_review_event}</div>}
             <div className="text-xs text-slate-600">
               O pedido original continua preservado. A situação documental
               não determina bloqueio, restituição ou direito ao rateio.
             </div>
             <div>Protocolo de teste: {item.policy_reference}</div>
             <button type="button"
               className="rounded-lg border border-slate-300 px-3 py-1 mt-2"
               onClick={()=>setSelectedReview(
                 selectedReview===item.id?'':item.id
               )}>
               {selectedReview===item.id?'Ocultar análise':'Ver análise e contestação'}
             </button>
             {selectedReview===item.id&&
               <MemberReviewTimelinePanel
                 key={item.id} state={state} request={item}
                 onUpdated={()=>setRefresh(n=>n+1)}/>}

           </li>
         )}
       </ul>
       <p className="rounded-lg bg-amber-50 p-3 text-amber-900">
         Efeito financeiro: nenhum. Direitos, principal e rateio não
         são alterados por registros de homologação.
       </p>
     </div>}
   {role==='TENANT_ADMIN'&&closing?.tenant_id===tenant&&
     <div className="rounded-lg border border-amber-200 p-3 text-sm space-y-1">
       <p className="font-semibold">Pendências registradas para o fechamento</p>
       <p>Saídas voluntárias pendentes: {closing.pending_voluntary_exits}</p>
       <p>Revisões de inadimplência pendentes: {closing.pending_delinquency_reviews}</p>
       <p>Contribuições sem quitação cadastral: {closing.registered_unsettled_contributions}</p>
       <p>Empréstimos não encerrados: {closing.unclosed_loans}</p>
       <p className="font-semibold text-amber-900">
         Fechamento, rateio e pagamento permanecem indisponíveis.
         Nenhum desses dados é saldo bancário conciliado.
       </p>
     </div>}
   {ownCap?.schema_ready===false&&
     <p className="text-sm text-amber-900">
       Este banco não contém a migration 028. A criação de solicitações permanece desabilitada.
     </p>}
   {canSubmit&&
     <div className="rounded-xl border border-slate-300 p-4 space-y-3">
       <p className="font-medium text-sm">
         {role==='TENANT_MEMBER'
           ?'Registrar solicitação de saída VOLUNTÁRIA no laboratório'
           :'Abrir revisão de inadimplência no laboratório'}
       </p>
       {role==='TENANT_ADMIN'&&
         <label className="block text-sm">
           Membro ativo
           <select value={selected} onChange={e=>{
             setSelected(e.target.value);
             setConfirmed(false);requestKey.current=null;
             setSubmission({status:'idle'});
           }} className="block mt-1 w-full rounded-lg border p-2">
             <option value="">Selecione o membro</option>
             {members.map(member=><option key={member.id} value={member.id}>
               {member.name}
             </option>)}
           </select>
         </label>}
       <label className="flex gap-2 items-start text-sm">
         <input type="checkbox" checked={confirmed}
           onChange={e=>setConfirmed(e.target.checked)}/>
         <span>Confirmo que este é um TESTE em ambiente isolado, sem
           desligamento, multa, perda de rateio ou pagamento real.</span>
       </label>
       <button type="button" disabled={!supported} onClick={submit}
         className="rounded-lg border border-slate-300 px-4 py-2 disabled:opacity-50">
         {submission.status==='sending'?'Registrando teste...':'Registrar solicitação sintética'}
       </button>
       {submission.status==='success'&&
         <p role="status" className="text-sm text-emerald-900">
           Pedido sintético registrado: {submission.id}. Nenhum efeito financeiro.
         </p>}
       {submission.status==='error'&&
         <p role="alert" className="text-sm text-rose-900">
           Registro não confirmado. O pedido pode ter sido recebido;
           tente novamente para conferir sem duplicar.
         </p>}
     </div>}
   {!canSubmit&&
     <p className="text-xs text-slate-600">
       Criação de solicitações indisponível fora do sandbox autorizado pelo servidor.
     </p>}
 </section>;
};
