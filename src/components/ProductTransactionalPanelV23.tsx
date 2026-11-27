import React,{useEffect,useRef,useState} from 'react';
import {authService} from '../services/authService';
import {productTransactionalApiV23 as api} from '../services/productTransactionalApiV23';
import type {Scope,Directory,Workspace} from '../services/productTransactionalBoundaryV23';
import {formatBRL} from '../services/financialEngine';
const money=(n:number)=>formatBRL(n/100);
const btn='min-h-11 rounded-lg border border-emerald-700 px-3 py-2 text-sm font-semibold disabled:opacity-50';
const field='w-full min-h-11 rounded-lg border border-slate-300 bg-white p-2';
export function ProductTransactionalPanelV23(scope:Scope){
 const {userId,tenantId,role}=scope;
 const [directory,setDirectory]=useState<Directory|null>(null),[workspace,setWorkspace]=useState<Workspace|null>(null);
 const [cycle,setCycle]=useState(''),[offset,setOffset]=useState(0),[directoryOffset,setDirectoryOffset]=useState(0);
 const [busy,setBusy]=useState(false),[message,setMessage]=useState(''),[cap,setCap]=useState(false);
 const seq=useRef(0),mounted=useRef(true);
 useEffect(()=>{mounted.current=true;const clear=()=>{seq.current++;setDirectory(null);setWorkspace(null);setCycle('');setCap(false);setBusy(false);setMessage('Sessão alterada. Consulte novamente.');};
 const unsubscribe=authService.subscribe(clear);return()=>{mounted.current=false;seq.current++;unsubscribe();};},[userId,tenantId,role]);
 async function load(kind:'directory'|'workspace',page:number,id=''){
  const n=++seq.current,snapshot=authService.captureSession();
  const current=()=>mounted.current&&seq.current===n&&authService.isSessionSnapshotCurrent(snapshot);
  setBusy(true);setMessage('');setWorkspace(null);
  if(kind==='directory'){setDirectory(null);setCycle('');setCap(false);}
  try{
   if(kind==='directory'){await api.capabilities(scope);if(!current())return;setCap(true);
    const value=await api.directory(scope,page);if(current()){setDirectory(value);setDirectoryOffset(page);}
   }else{const value=await api.workspace(scope,id,page);if(current()){setWorkspace(value);setOffset(page);}}
  }catch(e){if(current())setMessage(e instanceof Error?e.message:'Consulta indisponível.');}
  finally{if(current())setBusy(false);}
 }
 const choose=(id:string)=>{setCycle(id);setWorkspace(null);setOffset(0);if(id)void load('workspace',0,id);};
 return <section className="rounded-xl border border-emerald-200 bg-white p-4 space-y-3" aria-label="Gestão transacional V2.3">
  <h3 className="font-bold text-emerald-950">Ciclos V2.3 — servidor</h3>
  <p className="text-sm">Consulta autenticada, separada da demonstração. Abertura, aceites, adesões, recebimentos e reservas ainda não autorizados para gravação neste ambiente.</p>
  <button type="button" className={btn} disabled={busy} onClick={()=>void load('directory',0)}>Consultar ciclos no servidor</button>
  {busy&&<p role="status">Consultando servidor…</p>}
  {cap&&<p className="text-xs text-amber-800">Contrato V2.3 reconhecido; operações financeiras bloqueadas.</p>}
  {message&&<p role="alert" className="text-sm text-rose-800">{message}</p>}
  {directory&&<>
   {directory.items.length===0?<p>Nenhum ciclo V2.3 nesta página.</p>:<label className="block text-sm">Ciclo disponível<select className={field} value={cycle} disabled={busy} onChange={e=>choose(e.target.value)}><option value="">Selecione</option>{directory.items.map(c=><option key={c.cycle_id} value={c.cycle_id}>{c.start_date} a {c.closing} · {c.mode} · {c.status} · {money(c.quota_cents)}/cota{c.membership_state==='CONSENTED'?' · adesão pendente':''}</option>)}</select></label>}
   <div className="flex flex-wrap gap-2">{directoryOffset>0&&<button className={btn} disabled={busy} onClick={()=>void load('directory',directoryOffset-50)}>Ciclos anteriores</button>}{directory.has_more&&directoryOffset<10000&&<button className={btn} disabled={busy} onClick={()=>void load('directory',directoryOffset+50)}>Mais ciclos</button>}</div>
  </>}
  {workspace&&<>
   <div className="space-y-1 text-sm"><h4 className="font-semibold">Política registrada</h4>
    <p>Cota: {money(workspace.policy.quota_cents)} · Administração: {workspace.policy.admin_bps/100}% · Atraso: {workspace.policy.late_days} dias / {workspace.policy.late_competences} competências.</p>
    <p>Primeiro vencimento {workspace.policy.first_due} · último {workspace.policy.last_due} · encerramento {workspace.policy.closing}.</p>
    <p className="break-all text-xs">Documento {workspace.policy.document_id} · SHA-256 da política {workspace.policy.policy_hash}</p>
   </div>
   {workspace.summary?<div className="space-y-1 text-sm"><h4 className="font-semibold">{role==='TENANT_ADMIN'?'Resumo do ciclo':'Minhas contribuições'}</h4><p>Devido {money(workspace.summary.obligation_cents)} · pago documentado {money(workspace.summary.paid_cents)} · pendente manual {money(workspace.summary.manual_pending_cents)}.</p><p>Recibos contestados: {workspace.summary.contested_receipts}</p></div>:<p className="text-sm">Consentimento registrado; adesão ainda não confirmada.</p>}
   {workspace.reserves&&<div className="rounded-lg bg-slate-50 p-3 text-sm space-y-1"><h4 className="font-semibold">Reservas gerenciais</h4><p>Documentado {money(workspace.reserves.documented_cents)} · contestado {money(workspace.reserves.contested_cents)} · reservado {money(workspace.reserves.reserved_cents)}.</p><p>Não reservado {money(workspace.reserves.unreserved_documented_cents)} · déficit {money(workspace.reserves.reserve_deficit_cents)}.</p><p className="font-semibold">Disponibilidade bancária autorizada: R$ 0,00. Sem conciliação.</p></div>}
   {workspace.items.map(x=><article className="rounded border p-2 text-sm" key={x.contribution_id}><p className="font-medium">{x.due_date} · {x.payment_status}</p>{role==='TENANT_ADMIN'&&<p className="break-all text-xs">Vínculo {x.membership_id}</p>}<p>Devido {money(x.due_cents)} · pago {money(x.paid_cents)} · pendente de conferência {money(x.pending_manual_cents)}</p></article>)}
   <div className="flex flex-wrap gap-2"><button className={btn} disabled={busy} onClick={()=>void load('workspace',offset,cycle)}>Atualizar ciclo</button>{offset>0&&<button className={btn} disabled={busy} onClick={()=>void load('workspace',offset-50,cycle)}>Competências anteriores</button>}{workspace.has_more&&offset<10000&&<button className={btn} disabled={busy} onClick={()=>void load('workspace',offset+50,cycle)}>Mais competências</button>}</div>
  </>}
 </section>;
}
