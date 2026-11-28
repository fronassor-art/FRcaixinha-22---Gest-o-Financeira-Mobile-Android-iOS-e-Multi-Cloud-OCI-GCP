/** FR Finance M39090 + M39900: exclusive cashboxes in READ-ONLY homologation.
 * The SaaS intent counter and collective tenant ledger are NOT bank money.
 * Never display invented receipts, payments, withdrawals, or account balances.
 */
import React,{useEffect,useState} from 'react';
import {ShieldCheck,Wallet,RefreshCcw} from 'lucide-react';
import type {AppState} from '../services/store';
import {authService} from '../services/authService';
import {financialApi} from '../services/financialApiService';
import type {
  MasterExclusiveCashbox,TenantAdminExclusiveCashbox,
} from '../services/exclusiveCashboxBoundary';
import type {ExclusiveCashboxHistory} from '../services/exclusiveCashboxHistoryBoundary';
import {
  adminCashboxEvidence,masterCashboxEvidence,
} from '../services/exclusiveCashboxEvidence';

type State={
  key:string;phase:'loading'|'ready'|'error';
  master?:MasterExclusiveCashbox;
  admin?:TenantAdminExclusiveCashbox;
  history?:ExclusiveCashboxHistory;
  historyPhase?:'loading'|'ready'|'unavailable';
};

export function ExclusiveCashboxView({state}:{state:AppState}){
  const role=state.currentRole;
  const tenant=state.currentTenantId;
  const key=[state.currentUserId,role,tenant].join(':');
  const [refresh,setRefresh]=useState(0);
  const [result,setResult]=useState<State>({key:'',phase:'loading'});
  useEffect(()=>{
    let active=true;
    const snapshot=authService.captureSession();
    setResult({key,phase:'loading',historyPhase:'loading'});
    const user=authService.getUser();
    if(!user||user.id!==state.currentUserId||user.role!==role||
       (role==='TENANT_ADMIN'&&(!tenant||user.tenantId!==tenant))||
       (role!=='MASTER'&&role!=='TENANT_ADMIN')){
      setResult({key,phase:'error'});
      return ()=>{active=false;};
    }
    const load=role==='MASTER'
      ?financialApi.fetchMasterExclusiveCashbox().then(master=>({master}))
      :financialApi.fetchTenantAdminExclusiveCashbox(tenant!).then(admin=>({admin}));
    void load.then(data=>{
      if(active&&authService.isSessionSnapshotCurrent(snapshot))
        setResult(prev=>({
          ...(prev.key===key?prev:{key,phase:'loading' as const}),
          key,phase:'ready',...data,
        }));
    }).catch(()=>{
      if(active&&authService.isSessionSnapshotCurrent(snapshot))
        setResult(prev=>({...prev,key,phase:'error'}));
    });
    // Independent request: a 404 on a stale FastAPI never hides the base cashbox.
    const loadHistory=role==='MASTER'
      ?financialApi.fetchMasterExclusiveCashboxHistory()
      :financialApi.fetchTenantAdminExclusiveCashboxHistory(tenant!);
    void loadHistory.then(history=>{
      if(active&&authService.isSessionSnapshotCurrent(snapshot))
        setResult(prev=>prev.key===key
          ?{...prev,history,historyPhase:'ready'}:prev);
    }).catch(()=>{
      if(active&&authService.isSessionSnapshotCurrent(snapshot))
        setResult(prev=>prev.key===key
          ?{...prev,historyPhase:'unavailable'}:prev);
    });
    return ()=>{active=false;};
  },[key,refresh,state.currentUserId,role,tenant]);
  if(role!=='MASTER'&&role!=='TENANT_ADMIN')return null;
  const current=result.key===key?result:{key,phase:'loading' as const};
  const master=role==='MASTER';
  const caption=master?'Caixa exclusivo do Administrador Master':'Caixa exclusivo do Administrador da Caixinha';
  const items=current.phase==='ready'
    ?(master&&current.master?masterCashboxEvidence(current.master)
      :!master&&current.admin?adminCashboxEvidence(current.admin):[])
    :[];
  return <section aria-label={caption} className="space-y-4">
    <div className="fr-green-card rounded-3xl p-5 text-white">
      <div className="flex items-center gap-2">
        <Wallet className="h-6 w-6 text-[#f6dc98]" aria-hidden="true"/>
        <h2 className="text-xl font-bold text-[#f6dc98]">{caption}</h2>
      </div>
      <p className="mt-3 text-sm text-emerald-50">
        {master
          ?'Receitas e assinaturas SaaS da plataforma, isoladas do patrimônio das caixinhas.'
          :'Controle da remuneração própria do administrador, separado do capital dos membros e da tesouraria coletiva.'}
      </p>
      <div className="mt-4 rounded-xl border border-[#bfa66c]/40 bg-black/15 p-4">
        <p className="text-xs text-emerald-100">Saldo conciliado e disponível</p>
        <p className="mt-1 text-xl font-semibold text-white">Não disponível</p>
        <p className="mt-2 text-xs text-emerald-50">
          Nenhum saldo bancário pode ser apresentado antes de conciliação e prova do provedor.
        </p>
      </div>
    </div>
    <div className="fr-light-card space-y-3 rounded-2xl p-5">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-emerald-800" aria-hidden="true"/>
        <h3 className="font-bold text-emerald-950">Conferência de registros e pendências</h3>
      </div>
      {current.phase==='loading'&&<p role="status">Consultando dados segregados do servidor...</p>}
      {current.phase==='error'&&<p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
        Caixa exclusivo não pôde ser confirmado no backend desta instalação.
        Verifique se a API FR Finance está atualizada. Nenhum saldo foi presumido.
      </p>}
      {current.phase==='ready'&&items.length>0&&<div className="space-y-3" aria-label="Categorias do caixa exclusivo">
        {items.map(item=><article key={item.id}
          className="rounded-xl border border-slate-200 bg-white/80 p-4">
          <h4 className="text-sm font-bold text-emerald-950">{item.label}</h4>
          <p className="mt-1 text-base font-semibold text-slate-800">
            {item.kind==='COUNT_ONLY'
              ?`${item.count} registros (somente quantidade)`
              :'Aguardando comprovação'}
          </p>
          <p className="mt-1 text-xs text-slate-600">{item.detail}</p>
        </article>)}
      </div>}
      {current.phase==='ready'&&!master&&current.admin&&<p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
        Regra contratual prevista: 15% do lucro líquido elegível para
        o administrador e 85% para os membros. O cálculo de cada ciclo exige
        política versionada comprovada e fechamento auditado. Esta consulta
        não confirma remuneração, transferência ou disponibilidade.
      </p>}
      {current.phase==='ready'&&master&&current.master&&<p className="text-xs text-amber-800">
        Cobranças preparadas não equivalem a receita recebida. O Caixa Master
        não agrega dinheiro ou despesas das caixinhas de terceiros.
      </p>}
      {current.phase==='ready'&&<div className="space-y-3" aria-label="Histórico documental do caixa">
        <h3 className="text-sm font-bold text-emerald-950">
          Histórico documental (não é extrato bancário)
        </h3>
        {current.historyPhase==='loading'&&<p role="status" className="text-sm text-slate-600">
          Consultando os eventos registrados...
        </p>}
        {current.historyPhase==='unavailable'&&<p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
          Histórico não disponível nesta versão da API. Nenhum lançamento ou saldo foi presumido.
        </p>}
        {current.historyPhase==='ready'&&current.history&&
          (current.history.entries.length===0
            ?<p className="text-sm text-slate-600">Nenhum registro documental encontrado.</p>
            :<ul className="space-y-2">
              {current.history.entries.map(item=><li key={item.category+':'+item.id}
                className="rounded-xl border border-slate-200 p-3">
                <p className="text-sm font-semibold text-slate-800">
                  {item.category==='SAAS_INTENT'
                    ?'Intenção SaaS (não é recebimento)'
                    :item.category==='SAAS_PREPARATION'
                      ?'Preparação de assinatura (não é receita)'
                      :'Registro do livro-razão COLETIVO (não é remuneração)'}
                </p>
                <p className="text-xs text-slate-600">
                  {new Date(item.occurred_at).toLocaleString('pt-BR')} ·
                  {' '}Estado técnico: {item.state}
                </p>
                <p className="mt-1 text-xs text-amber-900">
                  Valor liquidado ou disponível: não comprovado.
                </p>
              </li>)}
            </ul>)}
      </div>}
      <button type="button" onClick={()=>setRefresh(n=>n+1)}
        className="flex min-h-11 items-center gap-2 rounded-xl border border-emerald-800 px-4 text-sm font-semibold text-emerald-900">
        <RefreshCcw className="h-4 w-4" aria-hidden="true"/> Atualizar consulta
      </button>
    </div>
    <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-950">
      Homologação somente leitura: pagamentos, Pix, saques, transferências,
      fechamento e movimentações reais permanecem desativados.
    </p>
  </section>;
}
