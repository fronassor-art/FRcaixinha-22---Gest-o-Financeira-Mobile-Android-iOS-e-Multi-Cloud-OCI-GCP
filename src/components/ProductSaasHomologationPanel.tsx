import React,{useState} from 'react';
import {expandedDemoCapacity,previewDemoLicense} from '../services/productHomologationV23';
import {formatBRL} from '../services/financialEngine';
export function ProductSaasHomologationPanel({role}:{role:'MASTER'|'TENANT_ADMIN'}){
 const [open,setOpen]=useState(false);
 return <section className="rounded-xl border-2 border-indigo-200 bg-indigo-50 p-4 space-y-2">
  <h3 className="font-bold">Contratação SaaS — homologação V2.3</h3>
  <p className="text-sm">Receita da plataforma exclusivamente de assinaturas. Plano Ampliado: {expandedDemoCapacity.members} membros e {expandedDemoCapacity.quotas} cotas em demonstração; venda real desabilitada.</p>
  <button type="button" className="rounded border bg-white p-2" onClick={()=>setOpen(x=>!x)}>{open?'Encerrar ensaio':'Ensaiar contratação e Pix'}</button>
  {open&&<SaasDemo role={role}/>}
 </section>
}
function SaasDemo({role}:{role:'MASTER'|'TENANT_ADMIN'}){
 const [monthly,setMonthly]=useState('100,00'),[annual,setAnnual]=useState('1000,00');
 const [period,setPeriod]=useState<'MONTHLY'|'ANNUAL'>('MONTHLY');
 const [members,setMembers]=useState(200),[quotas,setQuotas]=useState(400);
 const [step,setStep]=useState(0),[result,setResult]=useState(''),[accepted,setAccepted]=useState(false);
 const field='rounded border bg-white p-2 w-full';
 const steps=['Convite fictício Master → Administrador','Cadastro fictício','Escolha da oferta e contrato SaaS','Aceite fictício do contrato','Intenção Pix Mercado Pago fictícia','Conferência do pagamento fictício','Preparação de ciclo e convite de membros'];
 function advance(){try{if(step===3&&!accepted)throw Error('Aceite explícito necessário para o ensaio.');if(step===4){const p=previewDemoLicense(monthly,annual,period,members,quotas);setResult('Intenção fictícia de '+formatBRL(p.amountCents/100)+' · sem QR real, sem licença ativa.');}if(step<steps.length-1)setStep(step+1);}catch(e){setResult(e instanceof Error?e.message:'Dados inválidos.');}}
 return <div className="space-y-2 rounded-lg bg-white p-3 text-sm">
  <p className="font-semibold">Ensaio isolado ({role==='MASTER'?'Master':'Administrador'}). Nenhum convite, aceite ou pagamento real é enviado.</p>
  <p>Etapa {step+1}/{steps.length}: {steps[step]}</p>
  {step<=2&&<div className="grid gap-2 sm:grid-cols-2">
   <label>Mensal (R$) — valor de teste<input className={field} value={monthly} onChange={e=>setMonthly(e.target.value)}/></label>
   <label>Anual (R$) — independente<input className={field} value={annual} onChange={e=>setAnnual(e.target.value)}/></label>
   <label>Periodicidade<select className={field} value={period} onChange={e=>setPeriod(e.target.value as typeof period)}><option value="MONTHLY">Mensal</option><option value="ANNUAL">Anual</option></select></label>
   <label>Membros<input className={field} type="number" value={members} onChange={e=>setMembers(Number(e.target.value))}/></label>
   <label>Cotas<input className={field} type="number" value={quotas} onChange={e=>setQuotas(Number(e.target.value))}/></label>
  </div>}
  {step===3&&<label className="flex gap-2"><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/> Simular aceite (não gera contrato real)</label>}
  {result&&<p role="status">{result}</p>}
  {step<steps.length-1?<button type="button" className="rounded bg-emerald-900 p-2 text-white" onClick={advance}>Próxima etapa fictícia</button>:<p>Ensaio encerrado. Nenhuma licença ou caixinha ativada. A mensalidade do membro é outra obrigação, acessível em Contribuições.</p>}
 </div>
}
