import React, { useEffect, useState } from 'react';
import { BriefcaseBusiness, ChevronLeft, ChevronRight, RefreshCw, Search, ShieldCheck } from 'lucide-react';
import { financialApi } from '../services/financialApiService';
import { MasterRegistryPage, RegistryStatus, REGISTRY_STATES } from '../services/masterRegistry';
import { AppState } from '../services/store';

type RegistryResult = {
  key: string; status:'loading'|'ready'|'error'; data?:MasterRegistryPage;
};
const statusLabel:Record<RegistryStatus,string>={
  TODOS:'Todos os estados', RASCUNHO_INATIVO:'Rascunho inativo',
  ATIVO:'Ativa', SUSPENSO:'Suspensa', ENCERRADO:'Encerrada',
};

/** Gestão cadastral somente leitura. A API valida MASTER e RLS. */
export const MasterTenantRegistryView:React.FC<{state:AppState}>=({state})=>{
  const [input,setInput]=useState('');
  const [search,setSearch]=useState('');
  const [status,setStatus]=useState<RegistryStatus>('TODOS');
  const [page,setPage]=useState(1);
  const [revision,setRevision]=useState(0);
  const scope=[state.currentUserId,state.currentRole,state.currentTenantId].join(':');
  const key=[scope,search,status,page,revision].join('|');
  const [result,setResult]=useState<RegistryResult>({key:'',status:'loading'});

  useEffect(()=>{
    if(state.currentRole!=='MASTER') return;
    let active=true;
    setResult({key,status:'loading'});
    financialApi.fetchMasterTenantRegistry({search,status,page,pageSize:20})
      .then(data=>{
        if(active) setResult({key,status:'ready',data});
      })
      .catch(()=>{
        if(active) setResult({key,status:'error'});
      });
    return ()=>{active=false;};
  },[key,state.currentRole]);

  if(state.currentRole!=='MASTER')return (
    <section role="alert">Acesso exclusivo de governança da plataforma.</section>
  );
  const current=result.key===key?result:{key,status:'loading' as const};
  const data=current.status==='ready'?current.data:undefined;
  return <section className="space-y-4" aria-label="Cadastro de caixinhas da plataforma">
    <div className="fr-green-card rounded-[24px] p-5 text-white">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-extrabold text-[#f7d988]">Gestão de caixinhas</h2>
          <p className="mt-1 text-sm text-emerald-50/85">
            Inventário cadastral da plataforma, sem acesso a finanças dos membros.
          </p>
        </div>
        <ShieldCheck className="h-6 w-6 shrink-0 text-[#f1d485]" aria-hidden="true"/>
      </div>
      <p className="mt-4 text-xs text-emerald-100/85">
        Convites e alterações de acesso aguardam implementação e aprovação.
        Nenhuma conta é criada, ativada ou suspensa por esta tela.
      </p>
    </div>

    {data&&<div className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Totais por estado">
      {REGISTRY_STATES.map(item=><article key={item}
        className="fr-light-card rounded-2xl p-3">
        <div className="text-xs font-semibold text-[#4c6958]">{statusLabel[item]}</div>
        <div className="mt-1 text-2xl font-extrabold text-[#0a4831]">
          {data.status_counts[item]}
        </div>
      </article>)}
    </div>}

    <form className="fr-light-card space-y-3 rounded-2xl p-4"
      onSubmit={event=>{event.preventDefault();setSearch(input.trim());setPage(1);}}>
      <label htmlFor="registry-search" className="block text-sm font-semibold text-[#153e2a]">
        Localizar caixinha
      </label>
      <div className="flex gap-2">
        <input id="registry-search" value={input} maxLength={80}
          onChange={event=>setInput(event.target.value)}
          placeholder="Buscar pelo nome" className="min-h-11 min-w-0 flex-1 rounded-lg border border-[#a6c3a8] bg-white px-3 text-base text-[#173e2c]"/>
        <button type="submit"
          className="fr-gold-button min-h-11 rounded-lg px-4 text-sm font-semibold">
          <Search className="mr-1 inline h-4 w-4" aria-hidden="true"/>Buscar
        </button>
      </div>
      <label htmlFor="registry-state" className="block text-sm font-semibold text-[#153e2a]">
        Filtrar por estado
      </label>
      <select id="registry-state" value={status}
        onChange={event=>{setStatus(event.target.value as RegistryStatus);setPage(1);}}
        className="min-h-11 w-full rounded-lg border border-[#a6c3a8] bg-white px-3 text-base text-[#173e2c]">
        {(['TODOS',...REGISTRY_STATES] as RegistryStatus[]).map(item=>
          <option key={item} value={item}>{statusLabel[item]}</option>)}
      </select>
    </form>

    {current.status==='error'&&<div role="alert" className="fr-light-card rounded-xl p-4">
      <p className="text-sm text-[#713626]">Não foi possível consultar os dados cadastrais.</p>
      <button type="button" onClick={()=>setRevision(v=>v+1)}
        className="mt-3 flex min-h-10 items-center gap-2 text-sm font-semibold text-[#075337]">
        <RefreshCw className="h-4 w-4"/>Tentar novamente
      </button>
    </div>}

    {current.status==='loading'&&<p role="status" className="text-sm text-[#4e6859]">
      Carregando cadastro autorizado...
    </p>}

    {data&&<div className="fr-light-card space-y-2 rounded-2xl p-4">
      <div className="flex justify-between gap-3">
        <h3 className="font-bold text-[#153e2a]">Caixinhas cadastradas</h3>
        <span className="text-sm text-[#547260]">{data.total} resultado(s)</span>
      </div>
      {data.tenants.length===0
        ? <p className="py-4 text-sm text-[#52665b]">Nenhuma caixinha encontrada.</p>
        : <ul className="divide-y divide-[#dceadd]">
          {data.tenants.map(tenant=><li key={tenant.id} className="space-y-1 py-3">
            <div className="flex items-center gap-2">
              <BriefcaseBusiness className="h-4 w-4 shrink-0 text-[#986d1f]"/>
              <strong className="min-w-0 flex-1 break-words text-sm text-[#183d2b]">
                {tenant.display_name}
              </strong>
            </div>
            <p className="text-xs text-[#52705c]">
              {statusLabel[tenant.status]}{tenant.is_owner_box?' · Caixinha inaugural':''}
            </p>
            <p className="break-all text-[11px] text-[#687b6d]">
              Responsável cadastral: {tenant.admin_user_id}
            </p>
            <p className="text-[11px] text-[#687b6d]">
              Registro: {new Date(tenant.created_at).toLocaleDateString('pt-BR')}
            </p>
          </li>)}
        </ul>}
      <div className="flex items-center justify-between border-t border-[#dceadd] pt-3">
        <button type="button" disabled={page===1}
          onClick={()=>setPage(p=>Math.max(1,p-1))}
          className="flex min-h-11 items-center gap-1 rounded-lg border px-3 text-sm disabled:opacity-40">
          <ChevronLeft className="h-4 w-4"/>Anterior
        </button>
        <span className="text-sm text-[#48604f]">Página {data.page}</span>
        <button type="button" disabled={!data.has_more}
          onClick={()=>setPage(p=>p+1)}
          className="flex min-h-11 items-center gap-1 rounded-lg border px-3 text-sm disabled:opacity-40">
          Próxima<ChevronRight className="h-4 w-4"/>
        </button>
      </div>
      <p className="text-xs text-[#6a806f]">
        A identidade do responsável é exibida somente por UUID. Dados pessoais,
        saldos e informações de membros não são consultados.
      </p>
    </div>}
  </section>;
};
