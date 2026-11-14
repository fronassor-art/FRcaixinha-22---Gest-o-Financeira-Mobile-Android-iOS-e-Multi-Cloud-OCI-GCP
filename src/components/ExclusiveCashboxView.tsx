/** FR Finance M39090 — two exclusive READ-ONLY financial areas.
 * The UI must never convert SaaS intent counts or 15% simulation into a
 * bank balance, a withdrawable amount, a receipt, or an approved transfer.
 */
import React,{useEffect,useState} from 'react';
import {ShieldCheck,Wallet,RefreshCcw} from 'lucide-react';
import type {AppState} from '../services/store';
import {authService} from '../services/authService';
import {financialApi} from '../services/financialApiService';
import type {
  MasterExclusiveCashbox,TenantAdminExclusiveCashbox,
} from '../services/exclusiveCashboxBoundary';

type State={
  key:string;phase:'loading'|'ready'|'error';
  master?:MasterExclusiveCashbox;
  admin?:TenantAdminExclusiveCashbox;
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
    setResult({key,phase:'loading'});
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
        setResult({key,phase:'ready',...data});
    }).catch(()=>{
      if(active&&authService.isSessionSnapshotCurrent(snapshot))
        setResult({key,phase:'error'});
    });
    return ()=>{active=false;};
  },[key,refresh,state.currentUserId,role,tenant]);
  if(role!=='MASTER'&&role!=='TENANT_ADMIN')return null;
  const current=result.key===key?result:{key,phase:'loading' as const};
  const master=role==='MASTER';
  const caption=master?'Caixa exclusivo do Administrador Master':'Caixa exclusivo do Administrador da Caixinha';
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
        <ShieldCheck className="h-5 w-5 text-emerald-800"/>
        <h3 className="font-bold text-emerald-950">Conferência de registros</h3>
      </div>
      {current.phase==='loading'&&<p role="status">Consultando dados segregados do servidor...</p>}
      {current.phase==='error'&&<p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
        Caixa exclusivo não pôde ser confirmado no backend desta instalação.
        Verifique se a API FR Finance está atualizada. Nenhum saldo foi presumido.
      </p>}
      {current.phase==='ready'&&master&&current.master&&<div className="space-y-2 text-sm">
        <p>Intenções de cobrança SaaS registradas: <strong>{current.master.payment_intents_count}</strong></p>
        <p>Preparações de assinatura registradas: <strong>{current.master.subscription_preparations_count}</strong></p>
        <p className="text-amber-800">Cobranças preparadas não equivalem a receita recebida.</p>
      </div>}
      {current.phase==='ready'&&!master&&current.admin&&<div className="space-y-2 text-sm">
        <p>Registros contábeis da sua caixinha: <strong>{current.admin.ledger_transactions_count}</strong></p>
        <p>Participação contratual prevista do administrador: <strong>15% do lucro líquido elegível</strong></p>
        <p>Participação prevista dos membros elegíveis: <strong>85%</strong></p>
        <p className="text-amber-800">O rateio depende do fechamento anual, auditoria e conciliação.
          Não há remuneração liberada nem transferência autorizada.</p>
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
