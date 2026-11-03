import React,{useEffect,useState} from 'react';
import {financialApi} from '../services/financialApiService';
import {
  MasterSaasPortfolio,SaasStatusFilter,SAAS_STATUS_LABELS,SAAS_TENANT_STATES
} from '../services/masterSaasPortfolio';

type State={key:string;phase:'loading'|'ready'|'error';data?:MasterSaasPortfolio};
const dateBR=(s:string|null)=>{
  if(!s)return 'Não registrada';
  const d=new Date(s);
  return Number.isFinite(d.getTime())?d.toLocaleDateString('pt-BR',{timeZone:'America/Belem'}):'Data indisponível';
};
const licenseLabels:Record<string,string>={
  ACTIVE:'Ativa',SUSPENDED:'Suspensa',EXPIRED:'Expirada',
  REVOKED:'Revogada',NOT_STARTED:'Ainda não iniciada'
};
/** Sem dados financeiros, apenas inventário de contratos SaaS no mesmo banco. */
export function MasterSaasPortfolioView({userId}:{userId:string|null}){
  const [search,setSearch]=useState('');
  const [filter,setFilter]=useState('');
  const [tenantStatus,setTenantStatus]=useState<SaasStatusFilter>('TODOS');
  const [page,setPage]=useState(1);
  const [revision,setRevision]=useState(0);
  const key=[userId,filter,tenantStatus,page,revision].join('|');
  const [result,setResult]=useState<State>({key:'',phase:'loading'});
  useEffect(()=>{
    let alive=true;
    setResult({key,phase:'loading'});
    financialApi.fetchMasterSaasPortfolio(filter,page,tenantStatus)
      .then(data=>{if(alive)setResult({key,phase:'ready',data});})
      .catch(()=>{if(alive)setResult({key,phase:'error'});});
    return ()=>{alive=false;};
  },[key]);
  const current=result.key===key?result:{key,phase:'loading' as const};
  const data=current.phase==='ready'?current.data:undefined;
  return <section aria-label="Inventário comercial de caixinhas" className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 space-y-4">
    <div>
      <h3 className="text-lg font-bold text-slate-900">Caixinhas e licenças por responsável</h3>
      <p className="mt-1 text-sm text-slate-600">
        Consulta comercial autorizada no PostgreSQL. O Master não acessa saldos,
        contribuições ou empréstimos dos participantes.
      </p>
    </div>
    <form className="grid grid-cols-1 sm:grid-cols-[1fr_auto_auto] gap-2"
      onSubmit={e=>{e.preventDefault();setPage(1);setFilter(search.trim());}}>
      <input aria-label="Buscar caixinha ou identificador do responsável" value={search}
        onChange={e=>setSearch(e.target.value)} maxLength={80}
        placeholder="Caixinha ou identificador do responsável"
        className="w-full min-w-0 min-h-11 rounded-lg border border-slate-300 px-3 py-2 text-sm"/>
      <button type="submit" className="min-h-11 rounded-lg bg-[#0b5138] px-4 py-2 font-semibold text-white">Buscar</button>
      <button type="button" className="min-h-11 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        onClick={()=>setRevision(x=>x+1)}>Atualizar</button>
    </form>
    <div>
      <label htmlFor="saas-tenant-status" className="mb-1 block text-sm font-medium text-slate-800">Situação cadastral</label>
      <select id="saas-tenant-status" value={tenantStatus}
        onChange={e=>{setTenantStatus(e.target.value as SaasStatusFilter);setPage(1);}}
        className="min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900">
        {(['TODOS',...SAAS_TENANT_STATES] as SaasStatusFilter[]).map(v=>
          <option value={v} key={v}>{SAAS_STATUS_LABELS[v]}</option>)}
      </select>
    </div>
    {current.phase==='loading'&&<p role="status" className="text-sm text-slate-700">Consultando registros comerciais...</p>}
    {current.phase==='error'&&<p role="alert" className="text-sm text-red-800">O inventário não pôde ser confirmado no servidor. Nenhum plano ou licença será presumido ativo.</p>}
    {data&&<>
      <p className="text-sm font-semibold text-slate-700">{data.total} caixinha(s) no filtro · Página {data.page}</p>
      {data.tenants.length===0&&<p className="text-sm text-slate-600">Nenhuma caixinha nesse filtro.</p>}
      <ul className="space-y-3">
        {data.tenants.map(t=><li key={t.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2 text-sm text-slate-700">
          <strong className="block break-words text-base text-[#17452f]">{t.display_name}</strong>
          <p>Cadastro: <strong>{SAAS_STATUS_LABELS[t.tenant_status]}</strong> · Data: {dateBR(t.registered_at)}</p>
          <p className="break-all text-xs">Responsável (UUID técnico): {t.admin_user_id}</p>
          <div className="grid grid-cols-2 gap-2" aria-label="Caixinhas do responsável">
            <p>Registradas: <strong>{t.admin_total}</strong></p>
            <p>Ativas: <strong>{t.admin_active}</strong></p>
            <p>Suspensas: <strong>{t.admin_suspended}</strong></p>
            <p>Rascunhos: <strong>{t.admin_draft}</strong></p>
            <p>Encerradas: <strong>{t.admin_closed}</strong></p>
            <p>Outros estados: <strong>{t.admin_total-t.admin_active}</strong></p>
          </div>
          {t.licensed_plan?<div className="rounded-lg border border-slate-200 bg-white p-3 space-y-1">
            <p>Licença registrada: <strong>{t.licensed_plan}</strong></p>
            <p>Situação: <strong>{licenseLabels[t.effective_status||'']||'Não confirmada'}</strong></p>
            <p>Início: {dateBR(t.valid_from)} · Vencimento: {dateBR(t.valid_until)}</p>
            <p>Capacidade do plano: {t.members_limit??'Não definida'} membros;
              {' '}{t.quotas_limit??'Não definida'} cotas.</p>
          </div>:<p className="font-semibold text-amber-900">Sem licença confirmada no PostgreSQL.</p>}
          {t.prepared_plan&&<p className="rounded-lg bg-amber-50 p-3 text-amber-950">
            Preparação documental: {t.prepared_plan} · {t.prepared_period} · {t.preparation_status}.
            {' '}Registro em {dateBR(t.prepared_at)}. Não confirma contratação, pagamento ou ativação.
          </p>}
          <p className="text-xs text-slate-500">
            Quantidade de novas caixinhas permitidas por contrato: não definida.
            Esse limite não corresponde à capacidade de membros ou cotas.
          </p>
        </li>)}
      </ul>
      <nav aria-label="Páginas do inventário SaaS" className="flex items-center justify-between gap-3">
        <button type="button" disabled={page<=1}
          onClick={()=>setPage(x=>Math.max(1,x-1))}
          className="min-h-11 rounded-lg border px-3 py-2 text-sm disabled:opacity-40">Anterior</button>
        <span className="text-sm">Página {page}</span>
        <button type="button" disabled={!data.has_more}
          onClick={()=>setPage(x=>x+1)}
          className="min-h-11 rounded-lg border px-3 py-2 text-sm disabled:opacity-40">Próxima</button>
      </nav>
    </>}
  </section>;
}
