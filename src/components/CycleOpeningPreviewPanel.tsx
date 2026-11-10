import React, { useEffect, useState, useRef } from 'react';
import {financialApi} from '../services/financialApiService';
import {authService} from '../services/authService';
import {parseCyclePriceInput} from '../services/cyclePriceBoundary';
import {CycleOpeningPreview} from '../services/cycleOpeningBoundary';
import {formatBRL} from '../services/financialEngine';

/** Admin-only interface. The server enforces the role and cannot create cycles here. */
export const CycleOpeningPreviewPanel:React.FC<{tenantId:string;suggestedYear?:number}> = ({tenantId,suggestedYear})=>{
 const [year,setYear]=useState('');
 const [amount,setAmount]=useState('');
 const [reason,setReason]=useState('');
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [preview,setPreview]=useState<CycleOpeningPreview|null>(null);
 const [opening,setOpening]=useState(false);
 const [opened,setOpened]=useState(false);
 const [openMessage,setOpenMessage]=useState('');
 const attempt=useRef<{fingerprint:string;key:string}|null>(null);
 useEffect(()=>{
   if(Number.isInteger(suggestedYear) && Number(suggestedYear)<=2100)
     setYear(String(suggestedYear));
 },[suggestedYear]);
 async function submit(event:React.FormEvent<HTMLFormElement>){
   event.preventDefault();
   if(busy)return;
   const yr=Number(year);
   if(!Number.isSafeInteger(yr)||yr<2027||yr>2100){
     setError('Informe o ano completo do próximo ciclo.');return;
   }
   if(reason.trim().length<12||reason.trim().length>500){
     setError('Justificativa deve conter de 12 a 500 caracteres.');return;
   }
   let cents:number;
   try{cents=parseCyclePriceInput(amount);}catch(e){
     setError(e instanceof Error?e.message:'Valor por cota inválido.');return;
   }
   const snapshot=authService.captureSession();
   setBusy(true);setError('');setPreview(null);setOpenMessage('');setOpened(false);
   try{
     const result=await financialApi.previewCycleOpening(tenantId,yr,cents,reason.trim());
     if(authService.isSessionSnapshotCurrent(snapshot))setPreview(result);
   }catch(e){
     if(authService.isSessionSnapshotCurrent(snapshot))
       setError(e instanceof Error?e.message:'A prévia não foi autorizada.');
   }finally{
     if(authService.isSessionSnapshotCurrent(snapshot))setBusy(false);
   }
 }
 async function openConfirmed(){
   if(!preview||!preview.cycle_creation_enabled||!preview.preconditions_satisfied||opening||opened)return;
   let selected:number;
   try{selected=parseCyclePriceInput(amount);}catch{
     setOpenMessage('Valor inválido. Consulte novamente a prévia.');return;
   }
   if(preview.amount_cents!==selected||preview.year!==Number(year)){
     setOpenMessage('O valor ou ano mudou. Consulte novamente a prévia antes de abrir.');return;
   }
   const fingerprint=JSON.stringify([tenantId,preview.year,selected,reason.trim()]);
   if(!attempt.current||attempt.current.fingerprint!==fingerprint)
     attempt.current={fingerprint,key:crypto.randomUUID()};
   const snapshot=authService.captureSession();
   setOpening(true);setOpenMessage('');
   try{
     const result=await financialApi.openCycle(tenantId,preview.year,selected,reason.trim(),attempt.current.key);
     if(authService.isSessionSnapshotCurrent(snapshot)){
       setOpened(true);setOpenMessage('Ciclo aberto com valor escolhido de '+formatBRL(result.amount_cents/100)+'.');
     }
   }catch(err){
     if(authService.isSessionSnapshotCurrent(snapshot))
       setOpenMessage(err instanceof Error?err.message:'Abertura não confirmada.');
   }finally{
     if(authService.isSessionSnapshotCurrent(snapshot))setOpening(false);
   }
 }
 return <section aria-label="Preparação de novo ciclo" className="space-y-3 rounded-xl border border-emerald-200 bg-white p-4">
  <h3 className="font-semibold text-emerald-950">Preparar novo ciclo</h3>
  <p className="text-sm text-slate-700">Escolha o valor por cota da sua caixinha, a partir de R$ 150,00. Cada ciclo tem sua própria política. A prévia não cria ciclos. A abertura exige confirmação do administrador e autorização no servidor.</p>
  <form onSubmit={event=>{void submit(event);}} className="grid gap-3 sm:grid-cols-2">
    <label className="grid gap-1 text-sm text-slate-800">Ano do ciclo
      <input aria-label="Ano do próximo ciclo" required type="number" min="2027" max="2100"
        value={year} onChange={e=>{setYear(e.target.value);setPreview(null);}}
        className="rounded-lg border border-slate-300 px-3 py-2"/>
    </label>
    <label className="grid gap-1 text-sm text-slate-800">Valor escolhido por cota (R$)
      <input aria-label="Valor por cota do próximo ciclo" required inputMode="decimal"
        placeholder="Digite o valor escolhido" value={amount} onChange={e=>{setAmount(e.target.value);setPreview(null);}}
        className="rounded-lg border border-slate-300 px-3 py-2"/>
    </label>
    <label className="grid gap-1 text-sm text-slate-800 sm:col-span-2">Justificativa de abertura
      <input aria-label="Motivo do valor escolhido" required minLength={12} maxLength={500}
        value={reason} onChange={e=>{setReason(e.target.value);setPreview(null);}}
        className="rounded-lg border border-slate-300 px-3 py-2"/>
    </label>
    <button type="submit" disabled={busy}
      className="rounded-lg bg-emerald-900 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50 sm:col-span-2">
      {busy?'Verificando...':'Conferir prévia do ciclo'}
    </button>
  </form>
  {error&&<p role="alert" className="text-sm text-rose-800">{error}</p>}
  {preview&&<div role="status" className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800">
    <p>Prévia {preview.year}: <strong>{formatBRL(preview.amount_cents/100)}</strong> por cota.</p>
    {preview.blocked_reasons.length>0
      ? <p>Ainda bloqueado: {preview.blocked_reasons.join(', ')}</p>
      : <p>Condições preliminares atendidas. {preview.cycle_creation_enabled?'Confirme a abertura com o valor escolhido.':'Abertura efetiva ainda não liberada.'}</p>}
    {preview.cycle_creation_enabled&&preview.preconditions_satisfied&&<button type="button"
       disabled={opening||opened} onClick={()=>{void openConfirmed();}}
       className="mt-3 w-full rounded-lg bg-emerald-900 px-4 py-3 font-semibold text-white disabled:opacity-50">
       {opening?'Abrindo...':opened?'Ciclo criado':'Confirmar abertura do ciclo'}
    </button>}
    <p>{opened?'Abertura registrada e auditada.':'A prévia não cria ciclos.'} Nenhuma cobrança anterior foi alterada.</p>
  </div>}
  {openMessage&&<p role="status" className="text-sm text-emerald-950">{openMessage}</p>}
 </section>;
};
