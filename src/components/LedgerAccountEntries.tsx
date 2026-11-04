import React,{useEffect,useState} from 'react';
import {authService} from '../services/authService';
import {financialApi} from '../services/financialApiService';
import type {DisplayLedgerAccount} from '../services/ledgerDetailBoundary';
import type {LedgerAccountDirectoryItem} from '../services/ledgerAccountDirectoryBoundary';
import type {LedgerAccountJournalPage} from '../services/ledgerAccountJournalBoundary';
interface Props {tenantId:string;account:Pick<DisplayLedgerAccount,'id'|'account_code'|'account_name'>|LedgerAccountDirectoryItem;onClose:()=>void}
interface Result {page:number;status:'loading'|'ready'|'error';data?:LedgerAccountJournalPage}
export const LedgerAccountEntries:React.FC<Props>=({tenantId,account,onClose})=>{
 const [page,setPage]=useState(1);
 const [revision,setRevision]=useState(0);
 const [result,setResult]=useState<Result>({page:1,status:'loading'});
 useEffect(()=>{
  let active=true;
  const snapshot=authService.captureSession();
  setResult({page,status:'loading'});
  financialApi.fetchLedgerAccountJournal(tenantId,account.id,page,25)
   .then(data=>{if(active&&authService.isSessionSnapshotCurrent(snapshot))
     setResult({page,status:'ready',data});})
   .catch(()=>{if(active&&authService.isSessionSnapshotCurrent(snapshot))
     setResult({page,status:'error'});});
  return ()=>{active=false;};
 },[tenantId,account.id,page,revision]);
 const current:Result=result.page===page?result:{page,status:'loading'};
 const fmt=(cents:number)=>new Intl.NumberFormat('pt-BR',
  {style:'currency',currency:'BRL'}).format(cents/100);
 return <section className="rounded-xl border border-slate-200 bg-white p-4 space-y-3"
  aria-label="Extrato paginado da conta selecionada">
  <div className="flex justify-between items-center gap-3">
   <div><h3 className="font-semibold text-slate-900">
     Extrato da conta {account.account_code} — {account.account_name}</h3>
    <p className="text-xs text-slate-600">Página {page} · Consulta parcial, não conciliada</p></div>
   <button type="button" onClick={onClose}
    className="rounded-lg border border-slate-300 px-3 py-2 text-sm">Fechar</button>
  </div>
  {current.status==='loading'&&<p role="status">Carregando lançamentos da conta...</p>}
  {current.status==='error'&&<div role="alert">
   <p className="text-sm text-rose-800">Consulta indisponível. Nenhum lançamento confirmado.</p>
   <button type="button" onClick={()=>setRevision(x=>x+1)}
    className="mt-2 rounded-lg border px-3 py-2 text-sm">Tentar novamente</button>
  </div>}
  {current.status==='ready'&&current.data&&<>
   {current.data.entries.length===0&&<p className="text-sm">Nenhum lançamento nesta página.</p>}
   <div className="space-y-2">{current.data.entries.map(e=><article key={e.id}
    className="rounded-lg border border-slate-100 p-3 text-sm">
     <p className="font-medium">{e.description}</p>
     <p className="text-xs text-slate-600">{e.transaction_date} · Ref.: {e.reference_id}</p>
     <p>{e.entry_type} · {fmt(e.amount_cents)}</p>
   </article>)}</div>
   <div className="flex items-center justify-between gap-3">
    <button type="button" disabled={page<=1} onClick={()=>setPage(p=>p-1)}
     className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">Anterior</button>
    <span className="text-xs text-slate-600">Página {page}</span>
    <button type="button" disabled={!current.data.has_more||page>=1000}
     onClick={()=>setPage(p=>p+1)}
     className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">Próxima</button>
   </div>
   <p className="text-xs text-amber-900">Extrato parcial por conta.
    Não comprova completude do Livro-Razão, conciliação bancária,
    distribuição ou fechamento financeiro.</p>
  </>}
 </section>;
};
