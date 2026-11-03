import React, {useEffect,useState} from 'react';
import {ChevronLeft,ChevronRight,RefreshCw,Search,ShieldCheck,Users} from 'lucide-react';
import {financialApi} from '../services/financialApiService';
import {MasterAdminRegistryPage} from '../services/masterAdminRegistry';
import {AppState} from '../services/store';

type Result={key:string;status:'loading'|'ready'|'error';data?:MasterAdminRegistryPage};

/** Governança somente leitura: não altera contas, acesso ou movimentações. */
export const MasterAdminRegistryView:React.FC<{state:AppState}>=({state})=>{
  const [input,setInput]=useState('');
  const [search,setSearch]=useState('');
  const [page,setPage]=useState(1);
  const [revision,setRevision]=useState(0);
  const scope=[state.currentUserId,state.currentRole,state.currentTenantId].join(':');
  const key=[scope,search,page,revision].join('|');
  const [result,setResult]=useState<Result>({key:'',status:'loading'});

  useEffect(()=>{
    if(state.currentRole!=='MASTER')return;
    let alive=true;
    setResult({key,status:'loading'});
    financialApi.fetchMasterAdminRegistry({search,page,pageSize:20})
      .then(data=>{if(alive)setResult({key,status:'ready',data});})
      .catch(()=>{if(alive)setResult({key,status:'error'});});
    return ()=>{alive=false;};
  },[key,state.currentRole]);

  if(state.currentRole!=='MASTER'){
    return <section role="alert">Acesso exclusivo de governança da plataforma.</section>;
  }
  const current=result.key===key?result:{key,status:'loading' as const};
  const data=current.status==='ready'?current.data:undefined;
  return <section className="space-y-4" aria-label="Responsáveis cadastrais da plataforma">
    <header className="fr-green-card rounded-[24px] p-5 text-white">
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <h2 className="text-2xl font-extrabold text-[#f7d988]">Administradores da plataforma</h2>
          <p className="mt-2 text-sm text-emerald-50/85">
            Responsáveis principais registrados nas caixinhas.
          </p>
        </div>
        <ShieldCheck className="h-6 w-6 shrink-0 text-[#f1d485]" aria-hidden="true"/>
      </div>
      <p className="mt-4 text-xs text-emerald-100/85">
        O identificador técnico não comprova vínculo ativo ou identidade verificada.
        Não consultamos nomes, e-mails, CPF, saldos ou informações de membros.
      </p>
      <p className="mt-2 text-xs text-[#f1d485]">
        Convites, aprovações e suspensões indisponíveis até validação de segurança.
      </p>
    </header>

    <form className="fr-light-card space-y-3 rounded-2xl p-4"
      onSubmit={event=>{event.preventDefault();setSearch(input.trim());setPage(1);}}>
      <label htmlFor="admin-search" className="block text-sm font-semibold text-[#153e2a]">
        Localizar responsável
      </label>
      <div className="flex gap-2">
        <input id="admin-search" maxLength={36} value={input}
          onChange={event=>setInput(event.target.value)}
          placeholder="Buscar pelo identificador UUID"
          className="min-h-11 min-w-0 flex-1 rounded-lg border border-[#a6c3a8] bg-white px-3 text-base text-[#173e2c]"/>
        <button type="submit"
          className="fr-gold-button min-h-11 rounded-lg px-4 text-sm font-semibold">
          <Search className="mr-1 inline h-4 w-4" aria-hidden="true"/>Buscar
        </button>
      </div>
    </form>

    {current.status==='loading'&&<p role="status" className="text-sm text-[#4e6859]">
      Consultando responsáveis cadastrais autorizados...
    </p>}
    {current.status==='error'&&<div role="alert" className="fr-light-card rounded-xl p-4">
      <p className="text-sm text-[#713626]">Não foi possível consultar os responsáveis cadastrais.</p>
      <button type="button" onClick={()=>setRevision(i=>i+1)}
        className="mt-3 flex min-h-10 items-center gap-2 text-sm font-semibold text-[#075337]">
        <RefreshCw className="h-4 w-4"/>Tentar novamente
      </button>
    </div>}

    {data&&<div className="fr-light-card rounded-2xl p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-bold text-[#153e2a]">Responsáveis cadastrais</h3>
        <span className="text-sm text-[#547260]">{data.total} resultado(s)</span>
      </div>
      {data.administrators.length===0
        ? <p className="py-5 text-sm text-[#52665b]">Nenhum responsável encontrado.</p>
        : <ul className="divide-y divide-[#dceadd]">
            {data.administrators.map(admin=><li key={admin.admin_user_id}
              className="space-y-2 py-3">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 shrink-0 text-[#986d1f]" aria-hidden="true"/>
                <strong className="text-sm text-[#153e2a]">Responsável cadastral</strong>
              </div>
              <p className="break-all text-xs text-[#52685a]">{admin.admin_user_id}</p>
              <div className="grid grid-cols-2 gap-2 text-xs text-[#4c6655]">
                <p>Caixinhas: <strong>{admin.tenant_count}</strong></p>
                <p>Ativas: <strong>{admin.active_count}</strong></p>
                <p>Suspensas: <strong>{admin.suspended_count}</strong></p>
                <p>Outros estados: <strong>{admin.draft_count+admin.closed_count}</strong></p>
              </div>
            </li>)}
          </ul>}
      <div className="mt-2 flex items-center justify-between border-t border-[#dceadd] pt-3">
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
    </div>}
  </section>;
};
