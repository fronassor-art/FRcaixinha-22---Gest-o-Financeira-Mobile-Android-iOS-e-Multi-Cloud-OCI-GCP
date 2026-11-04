import React,{useEffect,useState} from 'react';
import {AppState} from '../services/store';
import {authService} from '../services/authService';
import {financialApi} from '../services/financialApiService';
import {LifecycleQueue} from '../services/memberLifecycleBoundary';

type Snapshot={key:string,status:'loading'|'ready'|'error',data?:LifecycleQueue};
/** M761: painel de solicitações do ciclo, somente histórico e homologação. */
export const MemberLifecyclePanel:React.FC<{state:AppState}>=({state})=>{
 const tenant=state.currentTenantId;
 const role=state.currentRole;
 const [refresh,setRefresh]=useState(0);
 const key=JSON.stringify([tenant,role,state.currentUserId,2027,refresh]);
 const [view,setView]=useState<Snapshot>({key:'',status:'loading'});
 useEffect(()=>{
   let mounted=true;
   const s=authService.captureSession();
   if(!tenant||!['TENANT_ADMIN','TENANT_MEMBER'].includes(role)){
     setView({key,status:'error'});
     return ()=>{mounted=false};
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
 if(!tenant||!['TENANT_ADMIN','TENANT_MEMBER'].includes(role))return null;
 const current=view.key===key?view:{key,status:'loading' as const};
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
             <div>Situação: análise pendente</div>
             <div>Protocolo: {item.policy_reference}</div>
           </li>
         )}
       </ul>
       <p className="rounded-lg bg-amber-50 p-3 text-amber-900">
         Efeito financeiro: nenhum. Direitos, principal e rateio não
         são alterados por registros de homologação.
       </p>
     </div>}
 </section>;
};
