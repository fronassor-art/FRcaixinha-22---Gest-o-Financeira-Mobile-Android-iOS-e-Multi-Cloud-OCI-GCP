import React,{useEffect,useState} from 'react';
import {AppState} from '../services/store';
import {financialApi} from '../services/financialApiService';
import {MemberAnnualPreview} from '../services/memberAnnualPreview';
import {formatBRL} from '../services/financialEngine';

type Result={key:string,status:'loading'|'ready'|'error',data?:MemberAnnualPreview};
export const MemberAnnualPreviewView:React.FC<{state:AppState}>=({state})=>{
  const key=JSON.stringify([
    state.currentUserId,state.currentTenantId,state.currentRole,2027
  ]);
  const [revision,setRevision]=useState(0);
  const [result,setResult]=useState<Result>({key:'',status:'loading'});
  useEffect(()=>{
    let active=true;
    const tenant=state.currentTenantId;
    setResult({key,status:'loading'});
    if(!tenant||!state.currentUserId||
      !['TENANT_MEMBER','TENANT_ADMIN'].includes(state.currentRole)){
      setResult({key,status:'error'});
      return ()=>{active=false;};
    }
    const request=state.currentRole==='TENANT_ADMIN'
      ?financialApi.fetchAdminAnnualPreview(tenant,2027)
      :financialApi.fetchMemberAnnualPreview(tenant,2027);
    request.then(data=>{if(active)setResult({key,status:'ready',data});})
      .catch(()=>{if(active)setResult({key,status:'error'});});
    return ()=>{active=false;};
  },[key,revision]);
  const current=result.key===key?result:{key,status:'loading' as const};
  return <section aria-labelledby="member-annual-title" className="space-y-4">
    <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
      <h2 id="member-annual-title" className="text-lg font-bold text-slate-900">
        {state.currentRole==='TENANT_ADMIN'
          ?'Fechamento — prévia operacional 2027':'Meu resultado anual — 2027'}
      </h2>
      <p className="text-sm text-slate-700">
        {state.currentRole==='TENANT_ADMIN'
          ?'Prévia consolidada das contribuições cadastradas na sua caixinha, sem fechamento, lucro ou conciliação.'
          :'Prévia individual das suas contribuições registradas no servidor. Não é fechamento, lucro ou confirmação bancária.'}
      </p>
      <button type="button" onClick={()=>setRevision(n=>n+1)}
        className="rounded-lg border border-slate-300 px-4 py-2 font-medium text-slate-800">
        Atualizar demonstrativo
      </button>
    </div>
    {current.status==='loading'&&
      <p role="status" className="text-sm text-slate-700">Consultando demonstrativo...</p>}
    {current.status==='error'&&
      <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
        Demonstrativo indisponível. Verifique o servidor e a sessão ativa.
      </p>}
    {current.status==='ready'&&current.data&&
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <dl className="grid grid-cols-2 gap-4">
          <div><dt className="text-sm text-slate-600">Contribuições previstas</dt>
            <dd className="text-xl font-bold text-slate-900">{current.data.contribution_count}</dd></div>
          <div><dt className="text-sm text-slate-600">Ainda pendentes</dt>
            <dd className="text-xl font-bold text-slate-900">{current.data.pending_count}</dd></div>
          <div><dt className="text-sm text-slate-600">Total devido</dt>
            <dd className="font-bold text-slate-900">{formatBRL(current.data.total_due)}</dd></div>
          <div><dt className="text-sm text-slate-600">Valor registrado como pago</dt>
            <dd className="font-bold text-slate-900">{formatBRL(current.data.amount_paid_recorded)}</dd></div>
          <div className="col-span-2"><dt className="text-sm text-slate-600">Saldo pendente</dt>
            <dd className="text-xl font-bold text-slate-900">{formatBRL(current.data.remaining_due)}</dd></div>
        </dl>
        <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
          Lucro, rendimentos e rateio anual ainda não apurados nem autorizados.
          Nenhuma transferência foi executada por esta consulta.
        </p>
      </div>}
  </section>;
};
