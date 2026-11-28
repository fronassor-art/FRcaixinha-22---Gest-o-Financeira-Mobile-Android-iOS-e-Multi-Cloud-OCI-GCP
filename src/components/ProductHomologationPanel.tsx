import React,{useRef,useState} from 'react';
import {confirmManual,contest,firstDemoCycle,memberObligations,paid,parseDemoMoney,recordManual,reconcileMockProvider,reverseManual,risk,
  type Cycle,type Demo,type Method,type Mode,type Role} from '../services/productHomologationV23';
import {formatBRL} from '../services/financialEngine';
import {newFlow,openFlowCycle,mergeFinance,type Flow} from '../services/integratedProductFlowV23';
import {IntegratedProductWorkspaceV23} from './IntegratedProductWorkspaceV23';
const money=(n:number)=>formatBRL(n/100);
const field='w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm';
const btn='rounded-lg bg-emerald-900 px-3 py-2 text-sm font-semibold text-white';
/** Synthetic workspace mounted separately from real contribution cards. No real ID or store access. */
export function ProductHomologationPanel({role}:{role:Role}){
 const [opened,setOpened]=useState(false);
 return <section className="space-y-3 rounded-xl border-2 border-indigo-200 bg-indigo-50 p-4" aria-label="Homologação fictícia de contribuições">
   <h3 className="font-bold text-indigo-950">Gestão manual e híbrida — homologação</h3>
   <p className="text-sm text-indigo-950">Experimente ciclos, mensalidades, recebimentos, recibos e conciliação com dados exclusivamente fictícios. Não usa sua caixinha real, não envia Pix e não grava no servidor. Os dados desaparecem ao sair.</p>
   <button type="button" className={btn} onClick={()=>setOpened(v=>!v)}>{opened?'Encerrar demonstração e apagar dados fictícios':'Abrir demonstração de mensalidades'}</button>
   {opened&&<Workspace role={role}/>}
 </section>;
}
function Workspace({role}:{role:Role}){
 const admin=role==='TENANT_ADMIN';
 const [d,setD]=useState<Flow>(()=>newFlow(true));
 const [policyAccepted,setPolicyAccepted]=useState(false);
 const ref=useRef(d);
 const [selected,setSelected]=useState(firstDemoCycle.id+'/demo-member-a/'+firstDemoCycle.first);
 const [cycle,setCycle]=useState<Cycle>({...firstDemoCycle,id:'demo-cycle-2',mode:'HYBRID'});
 const [quotaValue,setQuotaValue]=useState('150,00');
 const [amount,setAmount]=useState('75,00');
 const [method,setMethod]=useState<Method>('DINHEIRO');
 const [reference,setReference]=useState('DEMO-REC-001');
 const [evidence,setEvidence]=useState('Recibo fictício conferido');
 const [when,setWhen]=useState(firstDemoCycle.first);
 const [reason,setReason]=useState('Divergência fictícia para revisão');
 const [message,setMessage]=useState('');
 const [checked,setChecked]=useState(false);
 const [asOf,setAsOf]=useState('2027-04-10');
 const [memberView,setMemberView]=useState(!admin);
 const effectiveRole:Role=memberView?'TENANT_MEMBER':'TENANT_ADMIN';
 const visible=memberObligations(d,effectiveRole,'demo-member-a');
 const o=visible.find(x=>x.id===selected)??visible[0];
 const receipts=d.receipts.filter(x=>x.obligationId===o?.id);
 function applyFlow(fn:(current:Flow)=>Flow){try{const next=fn(ref.current);ref.current=next;setD(next);setMessage('Operação fictícia processada. Nenhum dinheiro movimentado.');}catch(e){setMessage(e instanceof Error?e.message:'Operação recusada.');}}
 function apply(fn:(current:Demo)=>Demo){applyFlow(v=>mergeFinance(v,fn(v)));}
 function reset(){const next=newFlow();ref.current=next;setD(next);setPolicyAccepted(false);setChecked(false);setMessage('Ensaio reiniciado, sem dados persistidos.');}
 function changeCycle<K extends keyof Cycle>(key:K,value:Cycle[K]){setCycle(c=>({...c,[key]:value}));}
 return <div className="space-y-4 text-slate-900">
   <p className="rounded-lg bg-white p-2 text-xs font-semibold">AMBIENTE FICTÍCIO · NÃO É SALDO REAL · NÃO É COMPROVANTE BANCÁRIO</p>
   {admin&&<label className="flex gap-2 text-sm"><input type="checkbox" checked={memberView} onChange={e=>{setMemberView(e.target.checked);setMessage('');setChecked(false);}}/> Ensaiar visão do membro fictício A</label>}
   <IntegratedProductWorkspaceV23 flow={d} role={effectiveRole} canAdmin={admin} apply={applyFlow} reset={reset}/>
   {!memberView&&admin&&d.step===5&&<form className="space-y-2 rounded-lg bg-white p-3" onSubmit={e=>{e.preventDefault();applyFlow(v=>openFlowCycle(v,'TENANT_ADMIN',{...cycle,id:'demo-cycle-'+(v.cycles.length+1),cents:parseDemoMoney(quotaValue)},policyAccepted));setPolicyAccepted(false);}}>
     <h4 className="font-semibold">Configurar outro ciclo simultâneo (fictício)</h4>
     <div className="grid gap-2 sm:grid-cols-2">
       {(['start','first','last','closing'] as const).map((k,i)=><label key={k} className="text-sm">{['Início','Primeira contribuição','Última contribuição','Encerramento'][i]}<input required type="date" className={field} value={cycle[k]} onChange={e=>changeCycle(k,e.target.value)}/></label>)}
       <label className="text-sm">Valor da cota (R$)<input required className={field} inputMode="decimal" value={quotaValue} onChange={e=>setQuotaValue(e.target.value)}/></label>
       <label className="text-sm">Cotas por membro fictício<input required className={field} type="number" min="1" max="200" value={cycle.quotas} onChange={e=>changeCycle('quotas',Number(e.target.value))}/></label>
       <label className="text-sm">Percentual administrativo (%)<input required className={field} type="number" min="0" max="100" step="0.01" value={cycle.adminBps/100} onChange={e=>changeCycle('adminBps',Math.round(Number(e.target.value)*100))}/></label>
       <label className="text-sm">Inadimplência — dias<input required className={field} type="number" min="1" max="3650" value={cycle.lateDays} onChange={e=>changeCycle('lateDays',Number(e.target.value))}/></label>
       <label className="text-sm">Competências distintas<input required className={field} type="number" min="1" max="120" value={cycle.lateCompetences} onChange={e=>changeCycle('lateCompetences',Number(e.target.value))}/></label>
       <label className="text-sm">Modo<select className={field} value={cycle.mode} onChange={e=>changeCycle('mode',e.target.value as Mode)}><option value="MANUAL">Manual</option><option value="HYBRID">Híbrido</option><option value="MERCADO_PAGO">Mercado Pago (simulado)</option></select></label>
     </div><label className="flex gap-2 text-sm"><input type="checkbox" checked={policyAccepted} onChange={e=>setPolicyAccepted(e.target.checked)}/> Aceitar política fictícia do ciclo</label><button className={btn} disabled={!policyAccepted} type="submit">Criar ciclo fictício</button>
     <p className="text-xs">Valores e duração configuráveis somente neste demonstrador. A configuração aceita fica congelada.</p>
   </form>}
   <label className="block text-sm">Competência fictícia<select className={field} value={o?.id??''} onChange={e=>{setSelected(e.target.value);setChecked(false);setMessage('');}}>{visible.map(x=><option key={x.id} value={x.id}>{x.cycleId} · {x.member.endsWith('a')?'Membro A':'Membro B'} · {x.due}</option>)}</select></label>
   {o&&<div className="space-y-2 rounded-lg bg-white p-3">
     <p className="text-sm">Modo: {d.cycles.find(c=>c.id===o.cycleId)?.mode} · {d.cycles.find(c=>c.id===o.cycleId)?.adminBps! / 100}% administrador</p>
     <p className="font-semibold">Devido: {money(o.cents)} · Pago na simulação: {money(paid(d,o.id))}</p>
     <p className="text-sm">Em aberto: {money(o.cents-paid(d,o.id))} · {paid(d,o.id)===o.cents?'QUITADA':paid(d,o.id)>0?'PARCIAL':'PENDENTE'} · {o.due<asOf&&paid(d,o.id)<o.cents?'VENCIDA':'Sem atraso aberto'}</p>
     <label className="block text-sm">Data de avaliação de atraso<input className={field} type="date" value={asOf} onChange={e=>setAsOf(e.target.value||firstDemoCycle.first)}/></label>
     {asOf&&<p className="text-sm">Atraso máximo: {risk(d,o.cycleId,o.member,asOf).days} dias · {risk(d,o.cycleId,o.member,asOf).competences} competências. {risk(d,o.cycleId,o.member,asOf).byDays||risk(d,o.cycleId,o.member,asOf).byCompetences?'Revisar política — nenhum capital confiscado.':'Sem gatilho da política fictícia.'}</p>}
     {!memberView&&admin&&<form className="space-y-2" onSubmit={e=>{e.preventDefault();apply(v=>recordManual(v,'TENANT_ADMIN',{obligationId:o.id,reference:reference.trim(),cents:parseDemoMoney(amount),method,date:when,evidence:evidence.trim()}));setChecked(false);}}>
       <h4 className="font-semibold">Registrar recebimento externo</h4>
       <div className="grid gap-2 sm:grid-cols-2">
        <label className="text-sm">Valor recebido (R$)<input className={field} required inputMode="decimal" value={amount} onChange={e=>setAmount(e.target.value)}/></label>
        <label className="text-sm">Meio<select className={field} value={method} onChange={e=>setMethod(e.target.value as Method)}><option value="DINHEIRO">Dinheiro em espécie</option><option value="PIX_EXTERNO">Pix externo</option><option value="TRANSFERENCIA">Transferência</option><option value="DEPOSITO">Depósito</option></select></label>
        <label className="text-sm">Data de ocorrência<input className={field} required type="date" value={when} onChange={e=>setWhen(e.target.value)}/></label>
        <label className="text-sm">Referência fictícia única<input className={field} required maxLength={160} value={reference} onChange={e=>setReference(e.target.value)}/></label>
       </div>
       <label className="block text-sm">Evidência fictícia (não insira dados pessoais)<input className={field} required maxLength={160} value={evidence} onChange={e=>setEvidence(e.target.value)}/></label>
       <button type="submit" className={btn}>Registrar pendente de conferência</button>
       <button type="button" className="ml-2 rounded-lg border px-3 py-2 text-sm" onClick={()=>apply(v=>reconcileMockProvider(v,'TENANT_ADMIN',{obligationId:o.id,reference:reference.trim(),cents:parseDemoMoney(amount),date:when,proof:'DEMO_WEBHOOK_AND_GET'}))}>Simular conciliação Mercado Pago</button>
     </form>}
     <label className="block text-sm">Justificativa fictícia de contestação/estorno<input className={field} value={reason} maxLength={160} onChange={e=>setReason(e.target.value)}/></label>
     {!memberView&&admin&&<label className="flex gap-2 text-sm"><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/> Conferi a evidência fictícia antes da confirmação</label>}
     <h4 className="font-semibold">Recibos gerenciais fictícios</h4>
     {receipts.length===0&&<p className="text-sm">Nenhum recibo nesta competência.</p>}
     {receipts.map(r=><article key={r.id} className="space-y-1 rounded border p-2 text-sm">
       <p className="font-medium">{r.reference} · {money(r.cents)} · {r.state}</p>
       <p>{r.origin} · {r.method} · {r.date} · {r.reconciled?'Conciliado (simulação)':'Sem prova bancária'} · {r.evidence}</p>
       {r.reason&&<p>Justificativa: {r.reason}</p>}
       {!memberView&&admin&&r.state==='PENDING'&&<button className={btn} type="button" disabled={!checked} onClick={()=>{apply(v=>confirmManual(v,'TENANT_ADMIN',r.id,checked));setChecked(false);}}>Confirmar recebimento fictício</button>}
       {memberView&&r.state==='CONFIRMED'&&<button className={btn} type="button" onClick={()=>apply(v=>contest(v,'demo-member-a',r.id,reason.trim()))}>Contestar recibo</button>}
       {!memberView&&admin&&r.origin==='MANUAL'&&!r.reconciled&&(r.state==='CONFIRMED'||r.state==='CONTESTED')&&<button className="rounded border px-3 py-2" type="button" onClick={()=>apply(v=>reverseManual(v,'TENANT_ADMIN',r.id,reason.trim(),when))}>Estornar com compensação</button>}
     </article>)}
     <h4 className="font-semibold">Partidas contábeis fictícias desta competência</h4>
     {d.journal.filter(j=>receipts.some(r=>r.id===j.receiptId)).map((j,i)=><p key={i} className="text-xs">{j.debit} → {j.credit} · {money(j.cents)} (débito/crédito equilibrados)</p>)}
   </div>}
   {message&&<p role="status" className="rounded-lg bg-white p-2 text-sm">{message}</p>}
 </div>;
}
