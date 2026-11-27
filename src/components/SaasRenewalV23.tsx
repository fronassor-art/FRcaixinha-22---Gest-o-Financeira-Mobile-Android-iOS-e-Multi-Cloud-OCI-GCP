import React,{useEffect,useRef,useState} from 'react';
import {authService,getApiBaseUrl} from '../services/authService';
import {readRenewal,prepareRenewal,type RenewalOverview} from '../services/saasRenewalV23';
import type {AdminScope} from '../services/onboardingReadbackV23';
import type {Transport} from '../services/productTransactionalBoundaryV23';
const transport:Transport={origin:getApiBaseUrl,captureSession:()=>authService.captureSession(),isCurrent:s=>authService.isSessionSnapshotCurrent(s),getUser:()=>authService.getUser(),invalidateIfCurrent:s=>authService.invalidateSessionIfCurrent(s),send:(u,o)=>fetch(u,o)};
const money=(n:number)=>(n/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const when=(v:string)=>new Date(v).toLocaleString('pt-BR',{timeZone:'America/Belem'});
const labels:Record<string,string>={CURRENT:'Vigente',SCHEDULED:'Período futuro pago',EXPIRED:'Vencida',SUSPENDED:'Suspensa',REFUNDED:'Estorno integral',PENDING:'Aguardando conciliação',REVIEW_REQUIRED:'Revisão necessária',PAYMENT_REVIEW:'Recebimento em revisão independente — não realizar novo pagamento',CI_RECONCILED:'Conciliada em CI',CANCELED:'Oferta expirada cancelada com prova em CI'};
const btn='min-h-11 rounded border border-emerald-700 px-3 text-sm disabled:opacity-50';
function scope():AdminScope{const u=authService.getUser();if(!u||u.role!=='TENANT_ADMIN'||!u.tenantId)throw Error('Sessão alterada.');return {userId:u.id,tenantId:u.tenantId,role:u.role};}
export function SaasRenewalV23(){
 const [view,setView]=useState<RenewalOverview|null>(null),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[period,setPeriod]=useState<'MONTHLY'|'ANNUAL'>('MONTHLY'),[accepted,setAccepted]=useState(false),[prepared,setPrepared]=useState('');
 const seq=useRef(0);
 function clear(){seq.current++;setView(null);setBusy(false);setNotice('');setAccepted(false);setPrepared('');setPeriod('MONTHLY');}
 useEffect(()=>{clear();const stop=authService.subscribe(clear);return()=>{seq.current++;stop();};},[]);
 async function load(){clear();const n=++seq.current,snap=authService.captureSession(),valid=()=>n===seq.current&&authService.isSessionSnapshotCurrent(snap);setBusy(true);
  try{const data=await readRenewal(transport,scope());if(valid())setView(data);}
  catch(e){if(valid())setNotice(e instanceof Error?e.message:'Consulta indisponível.');}
  finally{if(valid())setBusy(false);}
 }
 function prepare(){try{if(!view)throw Error('Oferta indisponível.');const p=prepareRenewal(scope(),view,crypto.randomUUID(),period,accepted);setPrepared(money(p.body.cents)+' · '+(p.body.period==='MONTHLY'?'mensal':'anual')+' — seleção local descartada; não enviada.');setAccepted(false);}catch{setPrepared('');setNotice('Confira novamente a oferta e a sessão.');}}
 return <section aria-label="Renovação da assinatura" className="border rounded-lg bg-white text-slate-900 p-3 space-y-2">
  <h5 className="font-semibold">Minha assinatura — renovação</h5>
  <p className="text-xs">Homologação candidata: sem cobrança, renovação automática, Pix ou ativação real. A assinatura não altera os ciclos das caixinhas.</p>
  <button type="button" className={btn} disabled={busy} onClick={()=>void load()}>Consultar vigência e renovação</button>
  {view&&<>
   <p className="text-xs">Consulta sintética em {when(view.observed_at)} (Belém). Atualize antes de conferir.</p>
   <p className="font-semibold text-sm">{view.access==='CURRENT'?'Licença vigente em CI':'Continuidade de direitos e obrigações; novos compromissos bloqueados'}</p>
   {view.segments.map(s=><article key={s.entitlement_id} className="border rounded p-2 text-sm"><p>{s.tier} · {s.period==='MONTHLY'?'Mensal':'Anual'} · {money(s.cents)}</p><p>{labels[s.state]} · {when(s.valid_from)} até {when(s.valid_until)} (fim exclusivo)</p></article>)}
   {view.renewals.map(s=><article key={s.request_id} className="border rounded p-2 text-sm"><p>Renovação {s.period==='MONTHLY'?'mensal':'anual'} · {money(s.cents)}</p><p>{labels[s.state]}</p>{s.state==='PENDING'&&<p>Validade da oferta de teste: {when(s.expires_at)}</p>}</article>)}
   {view.offer?<div className="space-y-2">
    <p className="text-sm">{view.segments.some(s=>s.entitlement_id===view.offer?.predecessor&&s.state==='REFUNDED')?'Regularização após estorno — nova oferta':'Oferta'} {view.offer.tier} · {view.offer.members_limit} membros / {view.offer.quotas_limit} cotas</p>
    <p className="text-sm">Mensal {money(view.offer.monthly_cents)} · Anual {money(view.offer.annual_cents)}</p>
    <article className="text-sm"><p>Contrato A · {view.document.version} · somente CI</p><p className="break-all text-xs">{view.document.document_hash}</p><p>{view.document.text}</p></article>
    <label className="block text-sm">Periodicidade<select className="w-full min-h-11 border rounded p-2" value={period} onChange={e=>{setPeriod(e.target.value as typeof period);setAccepted(false);setPrepared('');}}><option value="MONTHLY">Mensal</option><option value="ANNUAL">Anual</option></select></label>
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={accepted} onChange={e=>{setAccepted(e.target.checked);setPrepared('');}}/> Conferi a oferta e o instrumento apenas para preparação local.</label>
    <button type="button" className={btn} disabled={!accepted||busy} onClick={prepare}>Preparar renovação local</button>
    {prepared&&<p role="status" className="text-sm">{prepared}</p>}
   </div>:<p className="text-sm">Nenhuma nova oferta elegível nesta consulta. Pendências exigem revisão.</p>}
  </>}
  {notice&&<p role="status" className="text-sm">{notice}</p>}
 </section>;
}
