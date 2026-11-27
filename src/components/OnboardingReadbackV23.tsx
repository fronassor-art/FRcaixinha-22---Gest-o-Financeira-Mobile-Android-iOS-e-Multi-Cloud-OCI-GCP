import React,{useEffect,useRef,useState} from 'react';
import {authService,getApiBaseUrl} from '../services/authService';
import {readOnboarding,prepareCheckout,type OnboardingScope,type Offers,type DocumentReadback,type CheckoutStatus} from '../services/onboardingReadbackV23';
import type {Transport} from '../services/productTransactionalBoundaryV23';
const transport:Transport={origin:getApiBaseUrl,captureSession:()=>authService.captureSession(),isCurrent:s=>authService.isSessionSnapshotCurrent(s),getUser:()=>authService.getUser(),invalidateIfCurrent:s=>authService.invalidateSessionIfCurrent(s),send:(url,options)=>fetch(url,options)};
const field='w-full min-h-11 rounded border border-slate-300 bg-white p-2 text-sm';
const btn='min-h-11 rounded border border-emerald-700 px-3 text-sm disabled:opacity-50';
const brl=(c:number)=>(c/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
export function OnboardingReadbackV23({audience}:{audience:'MASTER'|'TENANT_ADMIN'}){
 const [docId,setDocId]=useState(''),[intent,setIntent]=useState(''),[document,setDocument]=useState<DocumentReadback|null>(null),[offers,setOffers]=useState<Offers|null>(null),[status,setStatus]=useState<CheckoutStatus|null>(null);
 const [selected,setSelected]=useState(''),[period,setPeriod]=useState<'MONTHLY'|'ANNUAL'>('MONTHLY'),[accepted,setAccepted]=useState(false),[prepared,setPrepared]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
 const seq=useRef(0);
 function clear(){seq.current++;setDocument(null);setOffers(null);setStatus(null);setSelected('');setAccepted(false);setPrepared('');setMessage('');setBusy(false);}
 useEffect(()=>{clear();setDocId('');setIntent('');const stop=authService.subscribe(()=>{clear();setDocId('');setIntent('');});return()=>{seq.current++;stop();};},[audience]);
 function currentScope():OnboardingScope{
  const u=authService.getUser();
  if(!u||u.role!==audience)throw Error('Sessão alterada.');
  if(audience==='MASTER'){if(u.tenantId)throw Error('Contexto incompatível.');return {userId:u.id,tenantId:null,role:'MASTER'};}
  if(!u.tenantId)throw Error('Caixinha indisponível.');
  return {userId:u.id,tenantId:u.tenantId,role:'TENANT_ADMIN'};
 }
 async function load(kind:'document'|'offers'|'status'){
  clear();const n=++seq.current;const snap=authService.captureSession();const valid=()=>seq.current===n&&authService.isSessionSnapshotCurrent(snap);
  setBusy(true);
  try{
   const s=currentScope(),result=await readOnboarding(transport,s,kind==='offers'?{kind}:{kind,id:kind==='document'?docId:intent});
   if(!valid())return;
   if(kind==='document')setDocument(result as DocumentReadback);
   else if(kind==='offers')setOffers(result as Offers);
   else setStatus(result as CheckoutStatus);
  }catch(e){if(valid())setMessage(e instanceof Error?e.message:'Consulta indisponível.');}
  finally{if(valid())setBusy(false);}
 }
 function prepare(){try{const s=currentScope();if(s.role!=='TENANT_ADMIN'||!offers)throw Error('Oferta indisponível.');const p=prepareCheckout(s,offers,selected,period,accepted);setPrepared(brl(p.accepted_cents)+' · '+(p.period==='MONTHLY'?'mensal':'anual'));}catch{setPrepared('');setMessage('Confira a oferta e a sessão.');}}
 const selectedOffer=offers?.offers.find(o=>o.price_version===selected);
 return <section className="border rounded-lg p-3 space-y-2 bg-white text-slate-900" aria-label="Conferência de contratação V2.3">
  <h5 className="font-semibold">Documentos e oferta versionada</h5>
  <p className="text-xs">Consulta candidata. Somente texto sintético de CI com SHA-256 conferido; não é contrato publicado. Não informe senhas, CPF, tokens ou comprovantes reais.</p>
  <label className="block text-sm">Referência do Contrato {audience==='MASTER'?'A':'B'} (UUID)<input className={field} value={docId} maxLength={36} onChange={e=>{clear();setDocId(e.target.value);}}/></label>
  <button type="button" className={btn} disabled={busy||!docId} onClick={()=>void load('document')}>Conferir texto e versão</button>
  {document&&<article className="text-sm space-y-1"><p className="font-semibold">Versão {document.version} · somente CI</p><p className="break-all text-xs">{document.document_hash}</p><p className="whitespace-pre-wrap">{document.text}</p></article>}
  {audience==='TENANT_ADMIN'&&<>
    <button type="button" className={btn} disabled={busy} onClick={()=>void load('offers')}>Consultar ofertas de assinatura</button>
    {offers&&<>{offers.offers.length===0?<p className="text-sm">Nenhuma oferta inicial disponível.</p>:<>
    <label className="block text-sm">Plano<select className={field} value={selected} onChange={e=>{setSelected(e.target.value);setAccepted(false);setPrepared('');}}><option value="">Selecione</option>{offers.offers.map(o=><option key={o.price_version} value={o.price_version}>{o.tier} · {o.members_limit} membros / {o.quotas_limit} cotas</option>)}</select></label>
    {selectedOffer&&<p className="text-sm">Mensal {brl(selectedOffer.monthly_cents)} · Anual {brl(selectedOffer.annual_cents)}</p>}
    <label className="block text-sm">Periodicidade<select className={field} value={period} onChange={e=>{setPeriod(e.target.value as typeof period);setAccepted(false);setPrepared('');}}><option value="MONTHLY">Mensal</option><option value="ANNUAL">Anual</option></select></label>
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={accepted} onChange={e=>{setAccepted(e.target.checked);setPrepared('');}}/> Conferi a oferta somente para preparação local.</label>
    <button type="button" className={btn} disabled={!selectedOffer||!accepted||busy} onClick={prepare}>Preparar seleção</button>{prepared&&<p className="text-sm">{prepared} — não enviado, nenhum pagamento.</p>}
    </>}</>}
    <label className="block text-sm">Referência da preparação de pagamento (ID da intenção)<input className={field} maxLength={36} value={intent} onChange={e=>{clear();setIntent(e.target.value);}}/></label>
    <button type="button" className={btn} disabled={busy||!intent} onClick={()=>void load('status')}>Consultar estado da conciliação</button>
    {status&&<p className="text-sm">{status.state==='CI_RECONCILED'?'Conciliado somente em CI':'Pendente'} · {brl(status.cents)} · nenhum pagamento real autorizado.</p>}
  </>}
  {message&&<p role="status" className="text-sm">{message}</p>}
 </section>;
}
