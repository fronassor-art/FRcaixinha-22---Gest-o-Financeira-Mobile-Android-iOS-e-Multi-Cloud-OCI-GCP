import React,{useEffect,useState} from 'react';
import {AppState} from '../services/store';
import {financialApi} from '../services/financialApiService';
import {authService} from '../services/authService';
import {FinancialIntegrityPreview} from '../services/financialIntegrityBoundary';
import {formatBRL} from '../services/financialEngine';

type Snapshot={key:string;status:'loading'|'ready'|'error';data?:FinancialIntegrityPreview};
const cash=(cents:number)=>formatBRL(cents/100);

/** Auditoria interna dos dados — NÃO é saldo bancário. */
export const FinancialIntegrityPanel:React.FC<{state:AppState}>=({state})=>{
  const [revision,setRevision]=useState(0);
  const tenant=state.currentTenantId;
  const role=state.currentRole;
  const key=JSON.stringify([tenant,role,state.currentUserId,2027,revision]);
  const [snapshot,setSnapshot]=useState<Snapshot>({key:'',status:'loading'});
  useEffect(()=>{
    let mounted=true;
    const captured=authService.captureSession();
    if(!tenant||role!=='TENANT_ADMIN'||!state.currentUserId){
      setSnapshot({key,status:'error'});
      return()=>{mounted=false;};
    }
    setSnapshot({key,status:'loading'});
    financialApi.fetchTenantFinancialIntegrityPreview(tenant,2027)
      .then(data=>{
        if(mounted&&authService.isSessionSnapshotCurrent(captured))
          setSnapshot({key,status:'ready',data});
      })
      .catch(()=>{
        if(mounted&&authService.isSessionSnapshotCurrent(captured))
          setSnapshot({key,status:'error'});
      });
    return()=>{mounted=false;};
  },[key,tenant,role,state.currentUserId]);
  if(role!=='TENANT_ADMIN')return null;
  const view=snapshot.key===key?snapshot:{key,status:'loading' as const};
  return <section aria-labelledby="m601-integrity-title"
    className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
    <h3 id="m601-integrity-title" className="text-base font-bold text-slate-900">
      Integridade financeira da caixinha — auditoria cadastral
    </h3>
    <p className="text-sm text-slate-700">
      Conferência cruzada de membros, políticas, contribuições e Livro-Razão
      do ciclo 2027. Não representa conciliação bancária, saldo disponível,
      lucro rateável, fechamento ou autorização de pagamento.
    </p>
    <button type="button" className="rounded-lg border border-slate-300 px-4 py-2"
      onClick={()=>setRevision(n=>n+1)}>Atualizar auditoria</button>
    {view.status==='loading'&&
      <p role="status" className="text-sm text-slate-600">Conferindo registros...</p>}
    {view.status==='error'&&
      <p role="alert" className="text-sm text-rose-800">
        Auditoria indisponível, registros excedidos ou divergentes. Consulte o servidor.
      </p>}
    {view.status==='ready'&&view.data&&
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-900">
          {view.data.status==='REGISTERED_INTEGRITY_ONLY'
            ?'Conferência dos registros concluída — sem comprovação bancária'
            :'Divergências registradas — revisão obrigatória'}
        </p>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div><dt>Pessoas distintas</dt>
            <dd className="font-bold">{view.data.members_distinct}</dd></div>
          <div><dt>Vínculos cadastrados</dt>
            <dd className="font-bold">{view.data.members_links}</dd></div>
          <div><dt>Contribuições cadastradas</dt>
            <dd className="font-bold">{view.data.registered_contributions}</dd></div>
          <div><dt>Contribuições quitadas no cadastro</dt>
            <dd className="font-bold">{view.data.complete_count}</dd></div>
          <div><dt>Total cadastrado</dt>
            <dd className="font-bold">{cash(view.data.registered_due_cents)}</dd></div>
          <div><dt>Pagamentos registrados</dt>
            <dd className="font-bold">{cash(view.data.registered_paid_cents)}</dd></div>
          <div><dt>Saldo cadastral em aberto</dt>
            <dd className="font-bold">{cash(view.data.registered_open_cents)}</dd></div>
          <div><dt>Lançamentos balanceados</dt>
            <dd className="font-bold">
              {view.data.balanced_transactions}/{view.data.ledger_transactions}
            </dd></div>
          <div><dt>Débitos do Livro-Razão</dt>
            <dd className="font-bold">{cash(view.data.ledger_dr_cents)}</dd></div>
          <div><dt>Créditos do Livro-Razão</dt>
            <dd className="font-bold">{cash(view.data.ledger_cr_cents)}</dd></div>
          <div><dt>Pagamentos sem lançamento vinculado</dt>
            <dd className="font-bold">{view.data.missing_ledger_count}</dd></div>
          <div><dt>Lançamentos ligados com diferença</dt>
            <dd className="font-bold">{view.data.incorrect_link_count}</dd></div>
        </dl>
        {view.data.findings.length>0&&
          <div className="rounded-lg bg-rose-50 p-3 text-sm text-rose-900">
            <p className="font-medium">Ocorrências para correção</p>
            <ul className="mt-2 list-disc pl-5">
              {view.data.findings.map(code=><li key={code}>{code}</li>)}
            </ul>
          </div>}
        <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
          Banco não conciliado. Valor disponível, lucro e rateio
          permanecem indefinidos. Nenhuma transferência pode ser feita.
        </p>
      </div>}
  </section>;
};
