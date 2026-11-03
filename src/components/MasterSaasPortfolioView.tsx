import React, {useEffect, useState} from 'react';
import {financialApi} from '../services/financialApiService';

type Portfolio = Awaited<ReturnType<typeof financialApi.fetchMasterSaasPortfolio>>;
type State = {key:string;phase:'loading'|'ready'|'error';data?:Portfolio};
const dateBR = (s:string|null) => {
  if (!s) return 'Não registrada';
  const d=new Date(s);
  return Number.isFinite(d.getTime()) ? d.toLocaleDateString('pt-BR',{timeZone:'America/Belem'}) : 'Data inválida';
};

/** Consulta comercial read-only do Master; nunca oferece acesso ao patrimônio do tenant. */
export function MasterSaasPortfolioView({userId}:{userId:string|null}) {
  const [search,setSearch]=useState('');
  const [filter,setFilter]=useState('');
  const [page,setPage]=useState(1);
  const [revision,setRevision]=useState(0);
  const key=[userId,filter,page,revision].join('|');
  const [result,setResult]=useState<State>({key:'',phase:'loading'});
  useEffect(()=>{
    let alive=true;
    setResult({key,phase:'loading'});
    financialApi.fetchMasterSaasPortfolio(filter,page).then(data=>{
      if(data.source!=='POSTGRESQL_RLS' ||
         data.scope!=='MASTER_SAAS_PORTFOLIO' ||
         data.boxes_limit_policy!=='NOT_DEFINED' ||
         !Array.isArray(data.tenants) ||
         !Number.isInteger(data.total) || data.total<0 ||
         data.tenants.some(t=>!t.id||!t.admin_user_id||t.admin_active>t.admin_total))
        throw new Error('Inventário inválido');
      if(alive)setResult({key,phase:'ready',data});
    }).catch(()=>{if(alive)setResult({key,phase:'error'});});
    return ()=>{alive=false;};
  },[key]);
  const current=result.key===key?result:{key,phase:'loading' as const};
  const data=current.phase==='ready'?current.data:undefined;
  return <section aria-label="Inventário comercial de caixinhas" className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 space-y-4">
    <div>
      <h3 className="text-lg font-bold text-slate-900">Caixinhas e licenças por responsável</h3>
      <p className="mt-1 text-sm text-slate-600">
        Informações cadastrais e comerciais do PostgreSQL. O Master não consulta saldos,
        contribuições ou empréstimos dos participantes.
      </p>
    </div>
    <form className="flex flex-wrap gap-2" onSubmit={e=>{e.preventDefault();setPage(1);setFilter(search.trim());}}>
      <input aria-label="Buscar caixinha ou identificador do responsável" value={search}
        onChange={e=>setSearch(e.target.value)} maxLength={80}
        placeholder="Caixinha ou identificador do responsável"
        className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"/>
      <button type="submit" className="rounded-lg bg-[#0b5138] px-4 py-2 font-semibold text-white">Buscar</button>
      <button type="button" className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        onClick={()=>setRevision(x=>x+1)}>Atualizar</button>
    </form>
    {current.phase==='loading' && <p role="status" className="text-sm">Consultando registros comerciais...</p>}
    {current.phase==='error' && <p role="alert" className="text-sm text-red-800">Não foi possível confirmar as licenças no servidor. Nenhum plano será presumido contratado.</p>}
    {data && <>
      <p className="text-sm font-semibold text-slate-700">{data.total} caixinha(s) no filtro</p>
      {data.tenants.length===0 && <p className="text-sm text-slate-600">Nenhum registro encontrado.</p>}
      <ul className="space-y-3">
        {data.tenants.map(t=><li key={t.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2 text-sm text-slate-700">
          <strong className="block break-words text-base text-[#17452f]">{t.display_name}</strong>
          <p>Status cadastral: <strong>{t.tenant_status}</strong> · Cadastro: {dateBR(t.registered_at)}</p>
          <p className="break-all text-xs">Responsável (identificador técnico): {t.admin_user_id}</p>
          <p>Caixinhas deste responsável: <strong>{t.admin_total}</strong> cadastradas,
            {' '}<strong>{t.admin_active}</strong> ativas,
            {' '}<strong>{t.admin_total-t.admin_active}</strong> em outros estados.</p>
          {t.licensed_plan ? <>
            <p>Plano com licença registrada: <strong>{t.licensed_plan}</strong> · Situação: <strong>{t.effective_status}</strong></p>
            <p>Início: {dateBR(t.valid_from)} · Vencimento: {dateBR(t.valid_until)}</p>
            <p>Limite do plano: {t.members_limit ?? 'não definido'} membros;
              {' '}{t.quotas_limit ?? 'não definido'} cotas.</p>
          </> : <p className="font-semibold text-amber-900">Sem licença confirmada no PostgreSQL.</p>}
          {t.prepared_plan && <p>Preparação documental: {t.prepared_plan} ·
            {' '}{t.prepared_period} · {t.preparation_status} · Criada em {dateBR(t.prepared_at)}.
            {' '}Isso não confirma contratação ou pagamento.</p>}
          <p className="text-xs text-slate-500">Vagas de novas caixinhas por contrato: não definidas.
            Não confundir com limite de membros ou cotas.</p>
        </li>)}
      </ul>
      <div className="flex items-center justify-between gap-3">
        <button type="button" disabled={page<=1}
          onClick={()=>setPage(x=>Math.max(1,x-1))}
          className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">Anterior</button>
        <span className="text-sm">Página {page}</span>
        <button type="button" disabled={!data.has_more}
          onClick={()=>setPage(x=>x+1)}
          className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">Próxima</button>
      </div>
    </>}
  </section>;
}
