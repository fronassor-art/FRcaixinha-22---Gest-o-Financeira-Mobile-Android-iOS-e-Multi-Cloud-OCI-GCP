import React, {useEffect, useRef, useState} from 'react';
import type {AppState} from '../services/store';
import {authService} from '../services/authService';
import {
  specialCreditApi, type CreditCampaign, type CreditGrant,
  type CreditOpportunity, type EligibleMember, type MarketingChannel,
} from '../services/specialCreditApi';

interface Props {state:AppState}
const channels:MarketingChannel[]=['PUSH','EMAIL','WHATSAPP','SMS'];
const money=(raw:string|number)=>new Intl.NumberFormat('pt-BR',{
  style:'currency',currency:'BRL'}).format(Number(raw));
const initialPrefs:Record<MarketingChannel,boolean>={
  PUSH:false,EMAIL:false,WHATSAPP:false,SMS:false,
};
function futureLocal():string{
  const future=new Date(Date.now()+14*24*60*60*1000);
  const local=new Date(future.getTime()-future.getTimezoneOffset()*60000);
  return local.toISOString().slice(0,16);
}
const toUtc=(local:string)=>{
  const date=new Date(local);
  if(!Number.isFinite(date.getTime())) throw new Error('Informe uma validade válida.');
  return date.toISOString();
};

/** M39015: UI ligada à API real (sandbox), nunca a fixtures de crédito fictício. */
export const SpecialCreditView:React.FC<Props>=({state})=>{
  const tenant=state.currentTenantId;
  const role=state.currentRole;
  const key=[state.currentUserId,tenant,role].join(':');
  const latest=useRef(key); latest.current=key;
  const [revision,setRevision]=useState(0);
  const [loading,setLoading]=useState(true);
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const [enabled,setEnabled]=useState(false);
  const [members,setMembers]=useState<EligibleMember[]>([]);
  const [selected,setSelected]=useState<string[]>([]);
  const [grants,setGrants]=useState<CreditGrant[]>([]);
  const [campaigns,setCampaigns]=useState<CreditCampaign[]>([]);
  const [opportunities,setOpportunities]=useState<CreditOpportunity[]>([]);
  const [prefs,setPrefs]=useState<Record<MarketingChannel,boolean>>(initialPrefs);
  const [limit,setLimit]=useState('5000.00');
  const [validity,setValidity]=useState(futureLocal);
  const [justification,setJustification]=useState('');
  const [title,setTitle]=useState('Oportunidade especial da sua caixinha');
  const [body,setBody]=useState('Você pode consultar uma simulação de crédito especial no FR Finance. A oferta está sujeita à análise final.');
  const [months,setMonths]=useState(3);
  const [simulation,setSimulation]=useState('');

  useEffect(()=>{
    let active=true;
    const snapshot=authService.captureSession();
    setLoading(true);setMessage('');setEnabled(false);
    setMembers([]);setSelected([]);setGrants([]);setCampaigns([]);
    setOpportunities([]);setPrefs(initialPrefs);setSimulation('');
    if(!tenant || role==='MASTER' || !state.currentUserId){
      setMessage('Selecione uma caixinha e entre como administrador ou membro.');
      setLoading(false);return()=>{active=false;};
    }
    const load=async()=>{
      try{
        const cap=await specialCreditApi.capabilities(tenant);
        if(!cap.sandbox_enabled) throw new Error('Crédito Especial ainda não habilitado para homologação.');
        if(role==='TENANT_ADMIN'){
          const [ms,gs,cs]=await Promise.all([
            specialCreditApi.members(tenant),
            specialCreditApi.grants(tenant),
            specialCreditApi.campaigns(tenant),
          ]);
          if(active&&latest.current===key&&authService.isSessionSnapshotCurrent(snapshot)){
            setMembers(ms);setGrants(gs);setCampaigns(cs);setEnabled(true);
          }
        }else if(role==='TENANT_MEMBER'){
          const [op,p]=await Promise.all([
            specialCreditApi.opportunities(tenant),
            specialCreditApi.preferences(tenant),
          ]);
          if(active&&latest.current===key&&authService.isSessionSnapshotCurrent(snapshot)){
            setOpportunities(op);setPrefs(p.preferences);setEnabled(true);
          }
        }
      }catch(error){
        if(active&&latest.current===key&&authService.isSessionSnapshotCurrent(snapshot))
          setMessage(error instanceof Error?error.message:'Não foi possível consultar o módulo.');
      }finally{
        if(active&&latest.current===key&&authService.isSessionSnapshotCurrent(snapshot))
          setLoading(false);
      }
    };
    void load();
    return()=>{active=false;};
  },[key,revision,tenant,role,state.currentUserId]);

  async function run(task:()=>Promise<unknown>,success:string){
    if(!tenant||busy)return;
    const before=key; const snapshot=authService.captureSession();
    setBusy(true);setMessage('');
    try{
      await task();
      if(latest.current!==before||!authService.isSessionSnapshotCurrent(snapshot))return;
      setMessage(success);setRevision(n=>n+1);
    }catch(error){
      if(latest.current===before&&authService.isSessionSnapshotCurrent(snapshot))
        setMessage(error instanceof Error?error.message:'Operação recusada.');
    }finally{
      if(latest.current===before&&authService.isSessionSnapshotCurrent(snapshot))
        setBusy(false);
    }
  }
  const toggle=(id:string)=>{
    setSelected(current=>current.includes(id)?current.filter(x=>x!==id):[...current,id]);
  };

  if(role==='MASTER') return null;
  return <section aria-labelledby="special-credit-title"
    className="space-y-4 rounded-2xl border border-emerald-200 bg-white p-4 sm:p-5">
    <header className="space-y-1">
      <h3 id="special-credit-title" className="text-lg font-bold text-emerald-950">
        {role==='TENANT_ADMIN'?'Crédito Especial • Campanhas':'Minhas Oportunidades de Crédito'}
      </h3>
      <p className="text-sm text-slate-700">
        Crédito extraordinário autoriza solicitar uma análise excepcional.
        Não representa aprovação financeira, reserva, empréstimo desembolsado nem Pix.
      </p>
      <p className="text-xs font-semibold text-amber-800">
        Ambiente de homologação. Push, e-mail, WhatsApp, SMS e Pix reais não são enviados.
      </p>
    </header>
    <button type="button" onClick={()=>setRevision(n=>n+1)}
      className="rounded-lg border border-emerald-700 px-3 py-2 text-sm text-emerald-900">
      Atualizar oportunidades
    </button>
    {loading&&<p role="status">Consultando o banco de homologação...</p>}
    {message&&<p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">{message}</p>}

    {!loading&&enabled&&role==='TENANT_ADMIN'&&tenant&&<>
      <div className="space-y-3 rounded-xl border p-3">
        <h4 className="font-semibold">1. Selecionar membros e conceder limite especial</h4>
        <p className="text-xs text-slate-600">
          Cada seleção cria uma autorização própria. A capacidade financeira e os contratos
          continuam sujeitos à avaliação antes de qualquer empréstimo.
        </p>
        <div className="max-h-48 space-y-2 overflow-y-auto" role="group" aria-label="Membros da caixinha">
          {members.length===0&&<p>Nenhum membro ativo encontrado.</p>}
          {members.map(m=><label key={m.id} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={selected.includes(m.id)} onChange={()=>toggle(m.id)}/>
            <span>{m.name}</span>
          </label>)}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-sm">Limite excepcional (R$)
            <input type="number" min="0.01" max="50000" step="0.01"
              value={limit} onChange={e=>setLimit(e.target.value)}
              className="rounded-lg border p-2"/>
          </label>
          <label className="grid gap-1 text-sm">Validade
            <input type="datetime-local" value={validity}
              onChange={e=>setValidity(e.target.value)}
              className="rounded-lg border p-2"/>
          </label>
        </div>
        <label className="grid gap-1 text-sm">Justificativa e avaliação de risco (obrigatória)
          <textarea rows={3} value={justification} maxLength={2000}
            onChange={e=>setJustification(e.target.value)}
            placeholder="Registrar análise financeira, exposição, disponibilidade e justificativa..."
            className="rounded-lg border p-2"/>
        </label>
        <button disabled={busy||selected.length===0||justification.trim().length<20}
          type="button" onClick={()=>void run(
            ()=>specialCreditApi.grant(tenant,selected,limit,toUtc(validity),justification),
            'Autorizações de solicitação extraordinária registradas.')}
          className="rounded-lg bg-emerald-800 px-4 py-2 font-semibold text-white disabled:opacity-40">
          Registrar autorização especial
        </button>
      </div>
      <div className="space-y-3 rounded-xl border p-3">
        <h4 className="font-semibold">2. Criar campanha para as autorizações</h4>
        <p className="text-xs text-slate-600">
          Selecione as autorizações individuais ativas. A campanha será salva em rascunho.
        </p>
        <div className="max-h-52 space-y-2 overflow-y-auto">
          {grants.filter(g=>g.status==='ACTIVE').map(g=><label key={g.id}
            className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 p-2 text-sm">
            <span>
              <input type="checkbox" checked={selected.includes(g.id)}
                onChange={()=>toggle(g.id)} className="mr-2"/>
              {g.member_name} • {money(g.ceiling_brl)}
            </span>
            <button type="button" disabled={busy}
              onClick={()=>void run(()=>specialCreditApi.revoke(tenant,g.id),
                'Autorização revogada para novas solicitações.')}
              className="text-xs text-rose-800 underline">Revogar</button>
          </label>)}
        </div>
        <label className="grid gap-1 text-sm">Título da campanha
          <input value={title} maxLength={100} onChange={e=>setTitle(e.target.value)}
            className="rounded-lg border p-2"/>
        </label>
        <label className="grid gap-1 text-sm">Mensagem promocional
          <textarea rows={3} maxLength={500} value={body}
            onChange={e=>setBody(e.target.value)} className="rounded-lg border p-2"/>
        </label>
        <button disabled={busy||!grants.some(g=>selected.includes(g.id)&&g.status==='ACTIVE')}
          type="button" onClick={()=>void run(
            ()=>specialCreditApi.createCampaign(tenant,
                grants.filter(g=>selected.includes(g.id)&&g.status==='ACTIVE').map(g=>g.id),
                title,body,toUtc(validity)),
            'Rascunho criado. Revise antes de publicar.')}
          className="rounded-lg bg-emerald-800 px-4 py-2 font-semibold text-white disabled:opacity-40">
          Salvar rascunho de campanha
        </button>
        <div className="space-y-2">
          {campaigns.map(c=><div key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-2 text-sm">
            <div><strong>{c.title}</strong><p>{c.recipients} destinatário(s) • {c.status}</p></div>
            {c.status==='DRAFT'&&<button disabled={busy} type="button"
              onClick={()=>void run(()=>specialCreditApi.publish(tenant,c.id),
                'Campanha publicada na caixa interna. Entregas externas permanecem bloqueadas.')}
              className="rounded-lg border border-emerald-700 px-3 py-2">
              Publicar internamente
            </button>}
            {c.status!=='CANCELLED'&&<button disabled={busy} type="button"
              onClick={()=>void run(()=>specialCreditApi.cancel(tenant,c.id),
                'Campanha cancelada.')}
              className="rounded-lg border border-rose-600 px-3 py-2 text-rose-700">
              Cancelar
            </button>}
          </div>)}
        </div>
      </div>
      <p className="rounded-lg bg-emerald-50 p-3 text-xs">
        Canais previstos no mesmo pacote: Push prioritário, e-mail, WhatsApp e SMS.
        Todos exigem homologação e ativação próprias. Nenhum envio externo está habilitado.
      </p>
    </>}

    {!loading&&enabled&&role==='TENANT_MEMBER'&&tenant&&<>
      {opportunities.length===0&&<p className="rounded-lg border p-3 text-sm">
        Não há oportunidades especiais publicadas para esta conta.
      </p>}
      {opportunities.map(o=><article key={o.recipient_id} className="space-y-2 rounded-xl border p-3">
        <p className="font-semibold">{o.title}</p>
        <p className="text-xl font-bold">{money(o.ceiling_brl)}</p>
        <p className="text-sm">{o.message}</p>
        <p className="text-xs text-slate-600">
          Limite para simulação até {new Date(o.expires_at).toLocaleString('pt-BR')}.
          Nenhum valor aprovado ou liberado.
        </p>
        <p className="text-xs">Resposta: {o.response_status}</p>
        {o.response_status==='PENDING'&&<div className="flex flex-wrap gap-2">
          <button type="button" disabled={busy}
            onClick={()=>void run(()=>specialCreditApi.reply(tenant,o.recipient_id,'INTERESTED'),
              'Interesse registrado; nenhuma contratação ocorreu.')}
            className="rounded-lg bg-emerald-800 px-3 py-2 text-sm text-white">Tenho interesse</button>
          <button type="button" disabled={busy}
            onClick={()=>void run(()=>specialCreditApi.reply(tenant,o.recipient_id,'DECLINED'),
              'Oportunidade recusada, sem prejuízo aos seus direitos.')}
            className="rounded-lg border px-3 py-2 text-sm">Não tenho interesse</button>
        </div>}
        {o.response_status!=='DECLINED'&&<div className="space-y-2 border-t pt-2">
          <label className="flex items-center gap-2 text-sm">Parcelas para simulação
            <select value={months} onChange={e=>setMonths(Number(e.target.value))}
              className="rounded-lg border p-2">
              {[1,2,3,4,5,6].map(n=><option value={n} key={n}>{n}</option>)}
            </select>
          </label>
          <button disabled={busy} type="button"
            onClick={()=>void run(async()=>{
              const result=await specialCreditApi.simulate(tenant,o.grant_id,o.ceiling_brl,months);
              if(latest.current===key)setSimulation(
                'Simulação: prestação '+money(result.simulation.uniform_payment)+
                ', total '+money(result.simulation.total_payable)+
                '. Nenhum empréstimo foi solicitado.');
            },'Simulação concluída sem movimento financeiro.')}
            className="rounded-lg border border-emerald-700 px-3 py-2 text-sm">
            Simular valor extraordinário
          </button>
        </div>}
      </article>)}
      {simulation&&<p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm">{simulation}</p>}
      <div className="space-y-3 rounded-xl border p-3">
        <h4 className="font-semibold">Preferências promocionais por canal</h4>
        <p className="text-xs text-slate-600">As preferências não ativam serviços reais nem substituem a autorização do provedor.</p>
        {channels.map(ch=><label key={ch} className="flex items-center justify-between gap-2 text-sm">
          <span>{ch==='PUSH'?'Push Android (prioritário)':ch}</span>
          <input type="checkbox" checked={prefs[ch]??false} disabled={busy}
            onChange={e=>void run(
              ()=>specialCreditApi.changePreference(tenant,ch,e.target.checked),
              'Preferência '+ch+' atualizada. Nenhuma mensagem externa enviada.')}/>
        </label>)}
      </div>
    </>}
  </section>;
};
