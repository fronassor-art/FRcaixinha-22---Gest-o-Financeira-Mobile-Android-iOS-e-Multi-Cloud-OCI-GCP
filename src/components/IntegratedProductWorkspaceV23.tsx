import React,{useState} from 'react';
import {acceptMember,balances,integratedJournal,decideCredit,demoOffer,disburseCredit,expense,importBatch,inviteMember,onboarding,offerCredit,previewClosing,price,repayCredit,requestCredit,requestExit,respondCredit,settleClosing,type Flow} from '../services/integratedProductFlowV23';
import {parseDemoMoney,type Role} from '../services/productHomologationV23';
import {formatBRL} from '../services/financialEngine';
const field='w-full rounded border border-slate-300 bg-white p-2';
const btn='rounded bg-emerald-900 px-3 py-2 text-sm text-white';
const money=(n:number)=>formatBRL(n/100);
type Props={flow:Flow;role:Role;canAdmin:boolean;apply:(fn:(f:Flow)=>Flow)=>void;reset:()=>void};
export function IntegratedProductWorkspaceV23({flow:f,role,canAdmin,apply,reset}:Props){
 const admin=role==='TENANT_ADMIN'&&canAdmin;
 const [cycleId,setCycleId]=useState(''),[member,setMember]=useState('demo-member-a');
 const [date,setDate]=useState('2026-12-10'),[cutoff,setCutoff]=useState('');
 const [reference,setReference]=useState('DEMO-EVENT-001'),[evidence,setEvidence]=useState('Evidência fictícia');
 const [amount,setAmount]=useState('25,00'),[quotas,setQuotas]=useState(1);
 const [accepted,setAccepted]=useState(false),[multi,setMulti]=useState(false);
 const [monthly,setMonthly]=useState(demoOffer.monthly),[annual,setAnnual]=useState(demoOffer.annual),[period,setPeriod]=useState<'MONTHLY'|'ANNUAL'>('MONTHLY');
 const [rate,setRate]=useState('2'),[term,setTerm]=useState(2);
 const [review,setReview]=useState<ReturnType<typeof previewClosing>|null>(null);
 const [preview,setPreview]=useState(''),[error,setError]=useState('');
 const c=f.cycles.find(x=>x.id===cycleId)??f.cycles[0];
 const stage=['Convite Master → Admin','Cadastro e identidade fictícios','Oferta SaaS','Aceite Contrato A','Pix SaaS e conferência fictícios','Licença fictícia apta'];
 const own='demo-member-a';
 const cycle=c?.id??'';
 const loans=f.loans.filter(l=>l.cycleId===cycle&&(admin||l.member===own));
 const campaigns=f.campaigns.filter(o=>o.cycleId===cycle&&(admin||o.members.includes(own)));
 const admissions=f.admissions.filter(a=>a.cycleId===cycle&&(admin||a.member===own));
 function act(fn:(v:Flow)=>Flow){setReview(null);setPreview('');apply(fn);}
 function local(fn:()=>void){try{fn();setError('');}catch(e){setError(e instanceof Error?e.message:'Dados inválidos.');}}
 const bps=()=>{const n=Number(rate);if(!/^\d{1,3}(\.\d{1,2})?$/.test(rate)||n>100)throw Error('Taxa mensal fictícia inválida.');return Math.round(n*100);};
 return <section className="space-y-3 rounded-xl bg-white p-3 border border-indigo-200">
   <h4 className="font-bold">Jornada integrada V2.3</h4>
   <p className="text-xs">Mesmo conjunto de dados fictícios das contribuições. Nenhuma licença, conta, comunicação ou operação real.</p>
   {admin&&<button type="button" className="rounded border px-2 py-2 text-sm" onClick={()=>{reset();setReview(null);setPreview('');setAccepted(false);}}>Reiniciar ensaio completo do convite Master</button>}
   {admin&&<div className="rounded border p-2 space-y-2">
     <p className="font-semibold">Contratação: {stage[f.step]}</p>
     {f.step===2&&<div className="grid gap-2 sm:grid-cols-2">
       <label className="text-sm">Mensal<input className={field} value={monthly} onChange={e=>setMonthly(e.target.value)}/></label>
       <label className="text-sm">Anual<input className={field} value={annual} onChange={e=>setAnnual(e.target.value)}/></label>
       <label className="text-sm">Periodicidade<select className={field} value={period} onChange={e=>setPeriod(e.target.value as typeof period)}><option value="MONTHLY">Mensal</option><option value="ANNUAL">Anual</option></select></label>
       <p className="text-sm">Ampliado: 200 membros / 400 cotas; exclusivo SaaS.</p>
     </div>}
     {f.step===3&&<label className="flex gap-2 text-sm"><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/> Aceite simulado do Contrato A</label>}
     {f.step<5&&<button type="button" className={btn} onClick={()=>act(v=>onboarding(v,v.step===0?'MASTER':'TENANT_ADMIN',(['INVITE','REGISTER','OFFER','ACCEPT','PAY'] as const)[v.step],{...demoOffer,monthly,annual,period},v.step===3?(accepted?'DEMO_CONTRATO_A_ACCEPTED':''):v.step===4?'DEMO_PIX_WEBHOOK_GET_SETTLEMENT':undefined))}>Executar etapa fictícia</button>}
     {f.step===5&&<p className="text-sm">Licença de teste confirmada; configure os ciclos no formulário abaixo. Nenhuma ativação real.</p>}
   </div>}
   {c&&<>
    <label className="block text-sm">Ciclo em análise<select className={field} value={cycle} onChange={e=>{setCycleId(e.target.value);setReview(null);setPreview('');setAccepted(false);}}>{f.cycles.map(x=><option key={x.id} value={x.id}>{x.id} · {x.start} a {x.closing}</option>)}</select></label>
    <p className="text-sm font-semibold">{f.settled.includes(cycle)?'Liquidado em simulação':'Em homologação'}</p>
    {admin&&<div className="grid gap-2 sm:grid-cols-2">
      <label className="text-sm">Membro fictício<select className={field} value={member} onChange={e=>{setMember(e.target.value);setAccepted(false);}}><option value="demo-member-a">Membro A</option><option value="demo-member-b">Membro B</option><option value="demo-member-c">Membro C</option></select></label>
      <label className="text-sm">Cotas no convite<input className={field} type="number" min="1" max="400" value={quotas} onChange={e=>setQuotas(Number(e.target.value))}/></label>
    </div>}
    <div className="grid gap-2 sm:grid-cols-2">
      <label className="text-sm">Data civil da operação<input type="date" className={field} value={date} onChange={e=>{setDate(e.target.value);setReview(null);setPreview('');}}/></label>
      <label className="text-sm">Valor (R$)<input className={field} inputMode="decimal" value={amount} onChange={e=>{setAmount(e.target.value);setPreview('');setAccepted(false);}}/></label>
      {admin&&<><label className="text-sm">Referência DEMO única<input className={field} value={reference} onChange={e=>setReference(e.target.value)}/></label><label className="text-sm">Evidência fictícia<input className={field} maxLength={160} value={evidence} onChange={e=>setEvidence(e.target.value)}/></label></>}
    </div>
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/> Confirmar aceite/evidência da etapa de teste selecionada</label>
    <div className="space-y-2 border-t pt-2">
      <h5 className="font-semibold">Convites e Contrato B</h5>
      {admin&&<button className={btn} type="button" onClick={()=>act(v=>inviteMember(v,'TENANT_ADMIN',cycle,member,quotas,date))}>Convidar membro fictício</button>}
      {admissions.map(a=><div key={a.member} className="text-sm border rounded p-2">
        {a.member} · {a.quotas} cota(s) · {a.joined} · {a.state}
        {a.state==='INVITED'&&<button className="ml-2 underline" type="button" disabled={!accepted} onClick={()=>act(v=>acceptMember(v,a.member,cycle,accepted))}>Ensaiar aceite do membro</button>}
        {!admin&&a.state==='ACCEPTED'&&<button className="ml-2 underline" type="button" onClick={()=>act(v=>requestExit(v,own,cycle))}>Solicitar saída, preservar direitos</button>}
      </div>)}
    </div>
    {admin&&<div className="space-y-2 border-t pt-2">
      <h5 className="font-semibold">Caixa, despesas e importação auditada</h5>
      {(()=>{const b=balances(f,cycle);return <p className="text-sm">Caixa manual líquido {money(b.manual)} · PSP simulado {money(b.provider)} · caixa de teste {money(b.cash)} · reservado {money(b.reserved)} · disponível manual {money(b.manualAvailable)} · capital reconhecido {money(b.capital)}.</p>})()}
      <button className={btn} type="button" disabled={!accepted} onClick={()=>act(v=>expense(v,'TENANT_ADMIN',cycle,parseDemoMoney(amount),date,reference,evidence))}>Registrar despesa externa conferida</button>
      <button className="ml-2 rounded border p-2 text-sm" type="button" disabled={!accepted} onClick={()=>act(v=>{const o=v.obligations.find(o=>o.cycleId===cycle&&o.member===member&&o.due<=date);if(!o)throw Error('Nenhuma obrigação da adesão até a data de corte.');return importBatch(v,'TENANT_ADMIN',cycle,reference+'-BATCH',date,[{obligationId:o.id,reference,cents:parseDemoMoney(amount),method:'DINHEIRO',date,evidence}],accepted);})}>Importar recebimento histórico fictício pendente</button>
      <p className="text-xs">Importação usa corte escolhido e obrigação existente; confirme a evidência na contribuição. Não importa dados reais ou inventa saldo inicial.</p>
      {f.cashEvents.filter(e=>e.cycleId===cycle).map(e=><p key={e.id} className="text-xs">{e.date} · {e.kind} · {money(e.cents)} · {e.reference}</p>)}
      <details><summary className="text-sm font-semibold">Livro-Razão integrado fictício</summary>{integratedJournal(f,cycle).map((j,i)=><p key={j.id+':'+i} className="text-xs">{j.debit} → {j.credit} · {money(j.cents)}</p>)}</details>
    </div>}
    <div className="space-y-2 border-t pt-2">
     <h5 className="font-semibold">Crédito Especial e consentimento</h5>
     {admin&&<><label className="flex gap-2 text-sm"><input type="checkbox" checked={multi} onChange={e=>setMulti(e.target.checked)}/> Oferta múltipla a membros ativos</label>
      <button className={btn} type="button" onClick={()=>act(v=>offerCredit(v,'TENANT_ADMIN',cycle,multi?v.admissions.filter(a=>a.cycleId===cycle&&a.state==='ACCEPTED').map(a=>a.member):[member],parseDemoMoney(amount),date))}>Criar oferta fictícia (data = validade)</button></>}
     {campaigns.map(o=><div key={o.id} className="text-sm rounded border p-2">
      {money(o.amount)} · válida até {o.validUntil} · {admin?o.members.join(', '):o.responses[own]??'Sem resposta'}
      {!admin&&<div><button className="mr-3 underline" type="button" onClick={()=>act(v=>respondCredit(v,own,o.id,'INTERESTED',date))}>Tenho interesse</button><button className="underline" type="button" onClick={()=>act(v=>respondCredit(v,own,o.id,'DECLINED',date))}>Recusar</button></div>}
     </div>)}
     <p className="text-xs">Oferta não é concessão de crédito; nenhum push, e-mail, WhatsApp ou SMS real.</p>
    </div>
    <div className="space-y-2 border-t pt-2">
     <h5 className="font-semibold">Crédito interno — Price, reserva e recebimento</h5>
     {!admin&&<><div className="grid gap-2 sm:grid-cols-2">
      <label className="text-sm">Taxa mensal fictícia (%)<input className={field} value={rate} onChange={e=>{setRate(e.target.value);setPreview('');setAccepted(false);}}/></label>
      <label className="text-sm">Parcelas<input className={field} type="number" min="1" max="12" value={term} onChange={e=>{setTerm(Number(e.target.value));setPreview('');setAccepted(false);}}/></label></div>
      <button className={btn} type="button" onClick={()=>local(()=>{const p=price(c,parseDemoMoney(amount),bps(),term,date);setPreview(p.map(i=>i.due+' '+money(i.principal+i.interest)+' (principal '+money(i.principal)+', juros '+money(i.interest)+')').join(' | '));setAccepted(false);})}>Simular Price</button>
      {preview&&<p className="text-sm">{preview}</p>}
      <button className="ml-2 rounded border p-2" type="button" disabled={!preview||!accepted} onClick={()=>act(v=>requestCredit(v,own,cycle,parseDemoMoney(amount),bps(),term,date,accepted))}>Solicitar crédito fictício</button></>}
     {loans.map(l=><div key={l.id} className="rounded border p-2 text-sm space-y-1">
      <p>{l.id} · {l.member} · {money(l.principal)} · {l.state}</p>
      {l.installments.map(i=><p key={i.due}>{i.due} · principal {money(i.principal-i.paidPrincipal)} · juros {money(i.interest-i.paidInterest)}</p>)}
      {admin&&l.state==='REQUESTED'&&<><button className={btn} type="button" onClick={()=>act(v=>decideCredit(v,'TENANT_ADMIN',l.id,true))}>Aprovar e reservar</button><button type="button" className="ml-2 underline" onClick={()=>act(v=>decideCredit(v,'TENANT_ADMIN',l.id,false))}>Recusar</button></>}
      {admin&&l.state==='RESERVED'&&<button className={btn} type="button" disabled={!accepted} onClick={()=>act(v=>disburseCredit(v,'TENANT_ADMIN',l.id,date,reference,evidence))}>Registrar desembolso fictício</button>}
      {admin&&l.state==='DISBURSED'&&<button className={btn} type="button" disabled={!accepted} onClick={()=>act(v=>repayCredit(v,'TENANT_ADMIN',l.id,parseDemoMoney(amount),date,reference,evidence))}>Registrar parcela fictícia na data de vencimento</button>}
     </div>)}
    </div>
    {admin&&<div className="space-y-2 border-t pt-2">
     <h5 className="font-semibold">Capital-Dias, resultado e encerramento</h5>
     <label className="block text-sm">Corte exclusivo (escolha expressa, diferente da data-alvo de liquidação)<input className={field} type="date" value={cutoff} onChange={e=>{setCutoff(e.target.value);setReview(null);}}/></label>
     <button className={btn} type="button" onClick={()=>local(()=>setReview(previewClosing(f,'TENANT_ADMIN',cycle,cutoff)))}>Apurar prévia com dados do ciclo</button>
     {review&&<div className="space-y-1 text-sm">
       <p>Lucro líquido: {money(Number(review.net))} · Administração {money(Number(review.admin))} · Membros {money(Number(review.memberPool))} · Pendente {money(Number(review.pending))}</p>
       {review.rows.map(x=><p key={x.member}>{x.member}: capital {money(x.capital)}, lucro {money(x.profit)}, peso {x.weight} centavos-dias</p>)}
       <p>{review.ready?'Conferência fictícia apta':'Pendências, insuficiência de caixa ou evidência: liquidação bloqueada.'}</p>
       <button className={btn} type="button" disabled={!review.ready||!accepted} onClick={()=>act(v=>settleClosing(v,'TENANT_ADMIN',review,date,reference,evidence))}>Registrar liquidação externa fictícia conferida</button>
     </div>}
    </div>}
   </>}
   {error&&<p role="alert" className="text-rose-800 text-sm">{error}</p>}
 </section>;
}
