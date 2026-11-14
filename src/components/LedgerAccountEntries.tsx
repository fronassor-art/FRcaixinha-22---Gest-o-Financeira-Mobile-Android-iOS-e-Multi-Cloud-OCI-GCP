import React,{useEffect,useState} from 'react';
import {authService} from '../services/authService';
import {financialApi} from '../services/financialApiService';
import type {DisplayLedgerAccount} from '../services/ledgerDetailBoundary';
import type {LedgerAccountDirectoryItem} from '../services/ledgerAccountDirectoryBoundary';
import type {LedgerKeysetPage} from '../services/ledgerKeysetBoundary';
import {initialJournalNavigation,nextJournalNavigation,previousJournalNavigation,canAdvanceJournalNavigation} from '../services/ledgerJournalCursorNavigation';
interface Props {tenantId:string;account:Pick<DisplayLedgerAccount,'id'|'account_code'|'account_name'>|LedgerAccountDirectoryItem;onClose:()=>void}
interface Result {key:string;status:'loading'|'ready'|'error';data?:LedgerKeysetPage}
export const LedgerAccountEntries:React.FC<Props>=({tenantId,account,onClose})=>{
 const [nav,setNav]=useState(initialJournalNavigation);
 const [revision,setRevision]=useState(0);
 const cursor=nav.cursors[nav.page-1];
 const key=[tenantId,account.id,nav.page,revision,cursor??'FIRST'].join(':');
 const [result,setResult]=useState<Result>({key:'',status:'loading'});
 useEffect(()=>{
  let active=true;
  const snapshot=authService.captureSession();
  setResult({key,status:'loading'});
  if(cursor===undefined){
   setResult({key,status:'error'});
   return ()=>{active=false;};
  }
  financialApi.fetchLedgerAccountKeyset(tenantId,account.id,cursor,25)
   .then(data=>{if(active&&authService.isSessionSnapshotCurrent(snapshot))
     setResult({key,status:'ready',data});})
   .catch(()=>{if(active&&authService.isSessionSnapshotCurrent(snapshot))
     setResult({key,status:'error'});});
  return ()=>{active=false;};
 },[key,tenantId,account.id,cursor]);
 const current:Result=result.key===key?result:{key,status:'loading'};
 const fmt=(cents:number)=>new Intl.NumberFormat('pt-BR',
  {style:'currency',currency:'BRL'}).format(cents/100);
 const previous=()=>{
  if(current.status==='ready'&&nav.page>1)setNav(previousJournalNavigation);
 };
 const canMoveNext=current.status==='ready'&&!!current.data&&
   canAdvanceJournalNavigation(nav,current.data);
 const next=()=>{
  if(!canMoveNext||!current.data)return;
  setNav(old=>nextJournalNavigation(old,current.data!));
 };
 return <section className="rounded-xl border border-slate-200 bg-white p-4 space-y-3"
  aria-label="Extrato paginado da conta selecionada">
  <div className="flex justify-between items-center gap-3">
   <div><h3 className="font-semibold text-slate-900">
     Extrato da conta {account.account_code} — {account.account_name}</h3>
    <p className="text-xs text-slate-600">Página {nav.page} · Consulta parcial, não conciliada</p></div>
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
    <button type="button" disabled={nav.page<=1} onClick={previous}
     className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">Anterior</button>
    <span className="text-xs text-slate-600">Página {nav.page}</span>
    <button type="button" disabled={!canMoveNext}
     onClick={next}
     className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">Próxima</button>
   </div>
   {current.data.has_more && nav.page<1000 && !canMoveNext&&
    <p role="alert" className="text-xs text-rose-800">
     Continuação do extrato bloqueada por cursor repetido ou inválido.
     Nenhum saldo financeiro foi confirmado.
    </p>}
   {nav.page>=1000&&current.data.has_more&&<p role="status" className="text-xs text-amber-900">
    Limite de páginas de homologação atingido. A consulta permanece parcial.
   </p>}
   <p className="text-xs text-amber-900">Extrato parcial por conta.
    Não comprova completude do Livro-Razão, conciliação bancária,
    distribuição ou fechamento financeiro.</p>
  </>}
 </section>;
};
