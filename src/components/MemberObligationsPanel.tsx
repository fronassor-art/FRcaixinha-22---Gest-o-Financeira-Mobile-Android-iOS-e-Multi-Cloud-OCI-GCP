import React,{useEffect,useState} from 'react';
import {AppState} from '../services/store';
import {authService} from '../services/authService';
import {financialApi} from '../services/financialApiService';
import {formatBRL} from '../services/financialEngine';
import {TenantMember} from '../services/tenantReadBoundary';
import {MemberObligationsPreview} from '../services/memberObligationsBoundary';

type Result={key:string,status:'loading'|'ready'|'error',data?:MemberObligationsPreview};
const cash=(n:number)=>formatBRL(n/100);
function belemToday():string{
 const parts=new Intl.DateTimeFormat('en-US',{
  timeZone:'America/Belem',year:'numeric',month:'2-digit',day:'2-digit'
 }).formatToParts(new Date());
 const find=(name:string)=>parts.find(p=>p.type===name)?.value||'';
 return find('year')+'-'+find('month')+'-'+find('day');
}

/** Histórico de obrigações registrado no banco, NÃO dívida bancária atestada. */
export const MemberObligationsPanel:React.FC<{state:AppState}>=({state})=>{
 const tenant=state.currentTenantId;
 const role=state.currentRole;
 const [asOf,setAsOf]=useState(belemToday);
 const [members,setMembers]=useState<TenantMember[]>([]);
 const [memberId,setMemberId]=useState('');
 const [revision,setRevision]=useState(0);
 const key=JSON.stringify([
   tenant,role,state.currentUserId,2027,asOf,memberId,revision
 ]);
 const [result,setResult]=useState<Result>({key:'',status:'loading'});

 useEffect(()=>{
  let active=true;
  const snapshot=authService.captureSession();
  setMembers([]);setMemberId('');setResult({key:'',status:'loading'});
  if(tenant&&role==='TENANT_ADMIN'){
   financialApi.fetchTenantMembers(tenant).then(data=>{
    if(active&&authService.isSessionSnapshotCurrent(snapshot))
      setMembers(data.members.filter(m=>m.role==='TENANT_MEMBER'));
   }).catch(()=>{
    if(active&&authService.isSessionSnapshotCurrent(snapshot))setMembers([]);
   });
  }
  return()=>{active=false};
 },[tenant,role,state.currentUserId]);

 const check=()=>{
  if(!tenant||!state.currentUserId||
     !['TENANT_MEMBER','TENANT_ADMIN'].includes(role)||
     (role==='TENANT_ADMIN'&&!memberId))return;
  const snapshot=authService.captureSession();
  const newKey=JSON.stringify([
    tenant,role,state.currentUserId,2027,asOf,memberId,revision+1
  ]);
  setRevision(n=>n+1);setResult({key:newKey,status:'loading'});
  financialApi.fetchMemberObligationsPreview(
    tenant,2027,asOf,role==='TENANT_ADMIN'?memberId:undefined
  ).then(data=>{
    if(authService.isSessionSnapshotCurrent(snapshot))
      setResult({key:newKey,status:'ready',data});
  }).catch(()=>{
    if(authService.isSessionSnapshotCurrent(snapshot))
      setResult({key:newKey,status:'error'});
  });
 };
 if(!tenant||!['TENANT_MEMBER','TENANT_ADMIN'].includes(role))return null;
 const current=result.key===key?result:null;
 return <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-4"
   aria-labelledby="member-obligations-title">
   <h3 id="member-obligations-title" className="text-base font-bold">
     Conferência de obrigações por membro — prévia
   </h3>
   <p className="text-sm text-slate-700">
     Consulta de contribuições e parcelas registradas no servidor. Uma proposta
     de empréstimo não é dívida, e juros futuros não são juros vencidos.
     Não existe nesta tela valor autorizado para restituição ou cobrança.
   </p>
   {role==='TENANT_ADMIN'&&
     <label className="block space-y-1 text-sm">
       Membro da própria caixinha
       <select value={memberId} className="block w-full border rounded-lg p-2"
         onChange={e=>{setMemberId(e.target.value);setResult({key:'',status:'loading'});}}>
         <option value="">Selecione um membro</option>
         {members.map(m=><option value={m.id} key={m.id}>
           {m.name} — {m.status}
         </option>)}
       </select>
     </label>}
   <label className="block space-y-1 text-sm">
     Data de referência do cenário
     <input type="date" min="2020-01-01" max="2100-12-31"
       className="block border rounded-lg p-2"
       value={asOf}
       onChange={e=>{setAsOf(e.target.value);setResult({key:'',status:'loading'});}}/>
   </label>
   <button type="button" onClick={check}
     disabled={role==='TENANT_ADMIN'&&!memberId}
     className="border rounded-lg px-4 py-2 disabled:opacity-50">
     Conferir obrigações cadastradas
   </button>
   {current?.status==='loading'&&
     <p role="status">Conferindo registros...</p>}
   {current?.status==='error'&&
     <p role="alert" className="text-rose-800">
       Conferência indisponível ou com dados inconsistentes. Nenhuma cobrança
       ou restituição foi calculada.
     </p>}
   {current?.status==='ready'&&current.data&&
     <div className="space-y-3 text-sm">
       <dl className="grid grid-cols-2 gap-3">
         <div><dt>Contribuições no ciclo</dt>
           <dd className="font-bold">{current.data.contribution_count}</dd></div>
         <div><dt>Contribuições vencidas em aberto</dt>
           <dd className="font-bold">{current.data.contribution_overdue_count}</dd></div>
         <div><dt>Contribuições em aberto no cadastro</dt>
           <dd className="font-bold">{cash(current.data.contribution_open_cents)}</dd></div>
         <div><dt>Contribuições com vencimento até a data</dt>
           <dd className="font-bold">{cash(current.data.contribution_now_open_cents)}</dd></div>
         <div><dt>Propostas de empréstimo não liberadas</dt>
           <dd className="font-bold">{current.data.loan_proposal_count}</dd></div>
         <div><dt>Empréstimos registrados como desembolsados</dt>
           <dd className="font-bold">{current.data.loan_active_count}</dd></div>
         <div><dt>Principal de parcelas vencidas/atuais registrado</dt>
           <dd className="font-bold">{cash(current.data.loan_now_principal_cents)}</dd></div>
         <div><dt>Juros de parcelas vencidas/atuais registrados</dt>
           <dd className="font-bold">{cash(current.data.loan_now_interest_cents)}</dd></div>
         <div><dt>Principal futuro programado</dt>
           <dd className="font-bold">{cash(current.data.loan_future_principal_cents)}</dd></div>
         <div><dt>Juros futuros programados (não exigíveis agora)</dt>
           <dd className="font-bold">{cash(current.data.loan_future_interest_cents)}</dd></div>
         <div className="col-span-2"><dt>Total cadastral com vencimento até a data</dt>
           <dd className="font-bold">{cash(current.data.registered_now_open_cents)}</dd></div>
       </dl>
       {current.data.loan_unscheduled_count>0&&
         <p role="alert" className="text-rose-900">
           Há {current.data.loan_unscheduled_count} empréstimo(s) sem cronograma.
           A apuração está incompleta e não pode ser utilizada para liquidação.
         </p>}
       <p className="rounded-lg bg-amber-50 p-3 text-amber-900">
         Esta conferência representa apenas saldos e cronogramas cadastrados,
         não conciliação bancária. Mora, multa, capital a restituir e lucro
         permanecem indeterminados. Nenhum débito pode ser compensado contra
         direitos do membro e nenhum Pix pode ser emitido por esta prévia.
       </p>
     </div>}
 </section>;
};
