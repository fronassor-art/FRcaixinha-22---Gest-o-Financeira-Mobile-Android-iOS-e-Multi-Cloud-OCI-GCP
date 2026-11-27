import {OnboardingFormsV23} from './OnboardingFormsV23';
import {OnboardingReadbackV23} from './OnboardingReadbackV23';
import React,{useEffect,useRef,useState} from 'react';
import {getApiBaseUrl,authService} from '../services/authService';
import {readOnboardingGate,onboardingSteps,type OnboardingAudience} from '../services/onboardingBoundaryV23';
export function OnboardingGateV23({audience}:{audience:OnboardingAudience}){
 const [status,setStatus]=useState<'UNCHECKED'|'LOADING'|'BLOCKED'|'UNAVAILABLE'>('UNCHECKED');
 const seq=useRef(0);
 useEffect(()=>{
  const clear=()=>{seq.current++;setStatus('UNCHECKED');};
  clear();const stop=authService.subscribe(clear);
  return()=>{seq.current++;stop();};
 },[audience]);
 async function check(){
  const n=++seq.current;setStatus('LOADING');
  try{await readOnboardingGate(getApiBaseUrl(),(url,options)=>fetch(url,options));if(seq.current===n)setStatus('BLOCKED');}
  catch{if(seq.current===n)setStatus('UNAVAILABLE');}
 }
 return <section aria-label="Jornada de contratação V2.3" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-slate-900 space-y-2">
  <h4 className="font-semibold">Jornada de contratação V2.3</h4>
  <ol className="list-decimal pl-5 text-sm">{onboardingSteps[audience].map(step=><li key={step}>{step}</li>)}</ol>
  <p className="text-xs">Etapas previstas, não concluídas. Nenhuma criação de conta, convite, aceite ou pagamento real por este painel.</p>
  <button type="button" disabled={status==='LOADING'} onClick={()=>void check()} className="min-h-11 rounded border border-emerald-700 px-3 text-sm">Consultar bloqueio no servidor</button>
  {(audience==='MASTER'||audience==='TENANT_ADMIN')&&<OnboardingReadbackV23 audience={audience}/>}
  {audience!=='TENANT_MEMBER'&&<OnboardingFormsV23 audience={audience}/>}
  <p role="status" className="text-sm">{status==='BLOCKED'?'Bloqueio V2.3 confirmado pelo servidor.':status==='UNAVAILABLE'?'Servidor indisponível ou incompatível. Operações continuam bloqueadas.':status==='LOADING'?'Consultando…':'Operações reais bloqueadas; disponibilidade não consultada.'}</p>
 </section>;
}
