import React,{useEffect,useState} from 'react';
import {AppState} from '../services/store';
import {financialApi} from '../services/financialApiService';
import {MemberCycleRiskPreview} from '../services/memberCycleRiskBoundary';
import {authService} from '../services/authService';
import {formatBRL} from '../services/financialEngine';
import {TenantMember} from '../services/tenantReadBoundary';

/** M531 — História registrada e cenários de datas; jamais bloqueio financeiro. */
function localToday():string{
  const parts=new Intl.DateTimeFormat('en-US',{
    timeZone:'America/Belem',year:'numeric',month:'2-digit',day:'2-digit'
  }).formatToParts(new Date());
  const v=(key:string)=>parts.find(p=>p.type===key)?.value||'';
  return v('year')+'-'+v('month')+'-'+v('day');
}

type Result={
  key:string;
  status:'loading'|'ready'|'error';
  preview?:MemberCycleRiskPreview;
};

export const MemberCycleRiskPanel:React.FC<{state:AppState}>=({state})=>{
  const tenant=state.currentTenantId;
  const role=state.currentRole;
  const [date,setDate]=useState(localToday);
  const [members,setMembers]=useState<TenantMember[]>([]);
  const [memberId,setMemberId]=useState('');
  const [membersError,setMembersError]=useState(false);
  const [revision,setRevision]=useState(0);
  const key=JSON.stringify([state.currentUserId,tenant,role,2027,date,memberId,revision]);
  const [result,setResult]=useState<Result>({key:'',status:'loading'});

  useEffect(()=>{
    let active=true;
    const session=authService.captureSession();
    setMembers([]);
    setMemberId('');
    setMembersError(false);
    setResult({key:'',status:'loading'});
    if(tenant&&role==='TENANT_ADMIN'){
      financialApi.fetchTenantMembers(tenant).then(data=>{
        if(active&&authService.isSessionSnapshotCurrent(session))
          setMembers(data.members.filter(m=>m.role==='TENANT_MEMBER'));
      }).catch(()=>{
        if(active&&authService.isSessionSnapshotCurrent(session))
          setMembersError(true);
      });
    }
    return ()=>{active=false;};
  },[tenant,role,state.currentUserId]);

  const refresh=()=>{
    if(!tenant||!state.currentUserId||
      !['TENANT_MEMBER','TENANT_ADMIN'].includes(role)||
      (role==='TENANT_ADMIN'&&!memberId))return;
    const snapshot=authService.captureSession();
    const activeKey=JSON.stringify([state.currentUserId,tenant,role,2027,date,memberId,revision+1]);
    setRevision(n=>n+1);
    setResult({key:activeKey,status:'loading'});
    financialApi.fetchMemberCycleRiskPreview(
      tenant,2027,date,role==='TENANT_ADMIN'?memberId:undefined
    ).then(preview=>{
      if(authService.isSessionSnapshotCurrent(snapshot))
        setResult({key:activeKey,status:'ready',preview});
    }).catch(()=>{
      if(authService.isSessionSnapshotCurrent(snapshot))
        setResult({key:activeKey,status:'error'});
    });
  };
  if(!tenant||!['TENANT_MEMBER','TENANT_ADMIN'].includes(role))return null;
  const current=result.key===key?result:null;
  return <section aria-labelledby="m531-risk-title"
    className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
    <h3 id="m531-risk-title" className="text-base font-bold text-slate-900">
      Histórico contratual do membro — prévia
    </h3>
    <p className="text-sm text-slate-700">
      Consulte as contribuições registradas por competência e a sequência potencial
      de atraso. A data pode ser alterada para testar um cenário temporal.
      Esta consulta não bloqueia direitos, não confirma banco e não executa Pix.
    </p>
    {role==='TENANT_ADMIN'&&
      <label className="block space-y-1 text-sm font-medium text-slate-700">
        Membro desta caixinha
        <select value={memberId} onChange={e=>{
          setMemberId(e.target.value);setResult({key:'',status:'loading'});
        }} className="block w-full rounded-lg border border-slate-300 p-2">
          <option value="">Selecione um membro</option>
          {members.map(member=><option key={member.id} value={member.id}>
            {member.name} — {member.status}
          </option>)}
        </select>
      </label>}
    {membersError&&
      <p role="alert" className="text-sm text-rose-800">
        Lista de membros indisponível. Reautentique e verifique o servidor.
      </p>}
    <label className="block space-y-1 text-sm font-medium text-slate-700">
      Data de referência da simulação
      <input type="date" min="2020-01-01" max="2100-12-31"
        value={date} onChange={e=>{
          setDate(e.target.value);setResult({key:'',status:'loading'});
        }} className="block w-full rounded-lg border border-slate-300 p-2"/>
    </label>
    <button type="button" onClick={refresh}
      disabled={role==='TENANT_ADMIN'&&!memberId}
      className="rounded-lg border border-slate-300 px-4 py-2 font-medium text-slate-800 disabled:opacity-50">
      Consultar histórico
    </button>
    {current?.status==='loading'&&
      <p role="status" className="text-sm text-slate-700">Consultando histórico...</p>}
    {current?.status==='error'&&
      <p role="alert" className="text-sm text-rose-800">
        Prévia indisponível ou contexto inválido. Nenhum direito foi alterado.
      </p>}
    {current?.status==='ready'&&current.preview&&
      <div className="space-y-2 text-sm text-slate-800">
        <dl className="grid grid-cols-2 gap-3">
          <div><dt>Obrigações registradas</dt>
            <dd className="font-bold">{current.preview.registered_contributions_count}</dd></div>
          <div><dt>Meses consecutivos sem quitação registrada</dt>
            <dd className="font-bold">{current.preview.currently_unpaid_consecutive_months}</dd></div>
          <div><dt>Total cadastrado</dt>
            <dd className="font-bold">{formatBRL(current.preview.registered_due_cents/100)}</dd></div>
          <div><dt>Pagamentos registrados</dt>
            <dd className="font-bold">{formatBRL(current.preview.registered_paid_cents/100)}</dd></div>
          <div className="col-span-2"><dt>Saldo cadastral ainda pendente</dt>
            <dd className="font-bold">{formatBRL(current.preview.registered_open_cents/100)}</dd></div>
        </dl>
        <p>Maior atraso registrado: {current.preview.longest_registered_overdue_days} dias.</p>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-1"
          aria-label="Critérios distintos de revisão cadastral">
          <p className="font-semibold">Sinais de revisão: critérios independentes</p>
          <p>
            90 dias: {current.preview.registered_ninety_day_review_candidate
              ? 'Limite atingido no cadastro; revisão necessária.'
              : 'Limite não atingido no cadastro.'}
          </p>
          <p>
            Três competências consecutivas: {current.preview.registered_three_competence_review_candidate
              ? 'Sequência potencial registrada; revisão necessária.'
              : 'Nenhuma sequência potencial registrada.'}
          </p>
          <p>
            {current.preview.requires_independent_review
              ? 'Solicitar comprovação independente, sem aplicar penalidade.'
              : 'Nenhum sinal encontrado; isso não comprova adimplência bancária.'}
          </p>
        </div>
        <p>
          {current.preview.potential_three_unpaid_trigger_date
            ?'Sequência potencial de três competências: '+
              current.preview.potential_three_unpaid_trigger_date
            :'Sem sequência potencial de três competências comprovada nesta prévia.'}
        </p>
        {current.preview.membership_profit_eligible===null&&
          !current.preview.financial_closing_authorized&&
          <p className="text-sm font-medium text-amber-900">
            Elegibilidade para rateio: não definida. Fechamento não autorizado.
          </p>}
        <p className="rounded-lg bg-amber-50 p-3 text-amber-900">
          Histórico ainda sem atestado bancário e contratual. Esta análise não
          determina exclusão de lucro, perda de capital, fechamento ou pagamento.
          Direitos e obrigações permanecem preservados para homologação.
        </p>
      </div>}
  </section>;
};
