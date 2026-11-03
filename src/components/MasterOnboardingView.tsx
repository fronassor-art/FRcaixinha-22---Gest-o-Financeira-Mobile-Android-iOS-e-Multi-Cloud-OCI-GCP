import React,{useEffect,useState} from 'react';
import {CheckCircle2,ShieldAlert,ShieldCheck,RefreshCw} from 'lucide-react';
import {financialApi} from '../services/financialApiService';
import {
  MasterOnboardingCapabilities,MasterOnboardingPreflight,REQUIRED_GATES,
  validatePreflightInput,
} from '../services/masterOnboarding';
import {AppState} from '../services/store';

const LABELS:Record<string,string>={
  MASTER_MFA:'Segundo fator do proprietário',
  DUAL_CONTROL:'Aprovação independente e prevenção de autoaprovação',
  EMAIL_OWNERSHIP:'Confirmação de titularidade do e-mail',
  INVITE_SINGLE_USE:'Token de convite de uso único',
  EXPIRATION_AND_REVOCATION:'Validade e revogação de convite',
  TRANSACTIONAL_AUDIT:'Registro auditável na mesma transação',
  IDENTITY_MEMBERSHIP_RECHECK:'Verificação de identidade e vínculo',
  DELIVERY_PROVIDER_VERIFIED:'Provedor de envio validado',
  LEGAL_APPROVAL:'Aprovação jurídica para ativação',
};

export const MasterOnboardingView:React.FC<{state:AppState}>=({state})=>{
  const scope=[state.currentUserId,state.currentRole,state.currentTenantId].join(':');
  const [snapshot,setSnapshot]=useState<{
    scope:string;status:'loading'|'ready'|'error';data?:MasterOnboardingCapabilities
  }>({scope:'',status:'loading'});
  const [reload,setReload]=useState(0);
  const [tenantId,setTenantId]=useState('');
  const [candidateUserId,setCandidateUserId]=useState('');
  const [purpose,setPurpose]=useState('');
  const [preflight,setPreflight]=useState<MasterOnboardingPreflight|null>(null);
  const [error,setError]=useState('');
  const [pending,setPending]=useState(false);
  const [revision,setRevision]=useState(0);
  const key=scope+'|'+reload;
  useEffect(()=>{
    if(state.currentRole!=='MASTER')return;
    let alive=true;
    setSnapshot({scope:key,status:'loading'});
    financialApi.fetchMasterOnboardingCapabilities()
      .then(data=>{if(alive)setSnapshot({scope:key,status:'ready',data});})
      .catch(()=>{if(alive)setSnapshot({scope:key,status:'error'});});
    return ()=>{alive=false;};
  },[key,state.currentRole]);
  useEffect(()=>{
    setPreflight(null);
    setError('');
    setPurpose('');
    setCandidateUserId('');
    setTenantId('');
    setRevision(n=>n+1);
  },[scope]);

  if(state.currentRole!=='MASTER'){
    return <section role="alert">Acesso restrito à governança Master.</section>;
  }
  const current=snapshot.scope===key?snapshot:{scope:key,status:'loading' as const};
  const data=current.status==='ready'?current.data:undefined;
  const submit=async(e:React.FormEvent)=>{
    e.preventDefault();
    if(pending||!data)return;
    setError('');
    setPreflight(null);
    try{
      validatePreflightInput({
        tenantId:tenantId.trim(),
        candidateUserId:candidateUserId.trim()||undefined,
        purpose,
      });
      setPending(true);
      const check=await financialApi.simulateMasterOnboarding({
        tenantId:tenantId.trim(),
        candidateUserId:candidateUserId.trim()||undefined,
        purpose:purpose.trim(),
      });
      setPreflight(check);
    }catch{
      setError('Não foi possível concluir a pré-análise. Confira os identificadores, a justificativa e a conexão.');
    }finally{
      setPending(false);
    }
  };
  return <section className="space-y-4" aria-label="Preparação de acessos administrativos">
    <header className="fr-green-card rounded-[24px] p-5 text-white">
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <h2 className="text-2xl font-extrabold text-[#f7d988]">
            Preparação de administradores
          </h2>
          <p className="mt-2 text-sm text-emerald-50/90">
            Pré-análise técnica sem criação de contas, convites ou mudanças de permissões.
          </p>
        </div>
        <ShieldCheck className="h-6 w-6 shrink-0 text-[#f1d485]"/>
      </div>
      <p className="mt-3 text-sm text-[#f6dc9d]">
        Modo homologação · execução real bloqueada
      </p>
    </header>

    {current.status==='loading'&&<p role="status">Consultando requisitos do servidor...</p>}
    {current.status==='error'&&<div role="alert" className="fr-light-card rounded-xl p-4">
      <p>Não foi possível consultar os bloqueios de segurança.</p>
      <button type="button" onClick={()=>setReload(n=>n+1)}
        className="mt-2 flex min-h-11 items-center gap-2 text-[#0d5336]">
        <RefreshCw className="h-4 w-4"/>Tentar novamente
      </button>
    </div>}
    {data&&<>
      <div className="fr-light-card rounded-2xl p-4">
        <h3 className="font-bold text-[#123d2b]">Requisitos antes de habilitar convites</h3>
        <p className="mt-1 text-xs text-[#52665a]">
          Todos os controles abaixo estão bloqueados para execução real.
        </p>
        <ul className="mt-3 space-y-2">
          {REQUIRED_GATES.map(name=><li key={name}
            className="flex items-start gap-2 text-sm text-[#405d4b]">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-[#a66f19]"/>
            <span>{LABELS[name]} · Pendente</span>
          </li>)}
        </ul>
      </div>

      <form onSubmit={submit} className="fr-light-card space-y-3 rounded-2xl p-4">
        <h3 className="font-bold text-[#123d2b]">Pré-analisar uma caixinha</h3>
        <p className="text-xs text-[#53695b]">
          Os dados não serão salvos, nem haverá convite. Utilize apenas UUIDs técnicos.
        </p>
        <label htmlFor="onboarding-tenant" className="block text-sm font-semibold">
          UUID da caixinha
        </label>
        <input id="onboarding-tenant" value={tenantId} maxLength={36}
          onChange={e=>setTenantId(e.target.value)}
          placeholder="00000000-0000-0000-0000-000000000000"
          className="min-h-11 w-full rounded-lg border border-[#9cb8a8] bg-white px-3 text-base"/>
        <label htmlFor="onboarding-candidate" className="block text-sm font-semibold">
          UUID de candidato (opcional)
        </label>
        <input id="onboarding-candidate" value={candidateUserId} maxLength={36}
          onChange={e=>setCandidateUserId(e.target.value)}
          placeholder="Somente para pré-análise de conflito"
          className="min-h-11 w-full rounded-lg border border-[#9cb8a8] bg-white px-3 text-base"/>
        <label htmlFor="onboarding-purpose" className="block text-sm font-semibold">
          Justificativa técnica (não informe dados pessoais)
        </label>
        <textarea id="onboarding-purpose" value={purpose} maxLength={240}
          rows={3} onChange={e=>setPurpose(e.target.value)}
          placeholder="Ex.: Avaliar futuro responsável pela administração da caixinha"
          className="w-full rounded-lg border border-[#9cb8a8] bg-white p-3 text-base"/>
        <button type="submit" disabled={pending}
          className="fr-gold-button min-h-11 w-full rounded-lg px-4 text-sm font-bold disabled:opacity-60">
          {pending?'Consultando...':'Executar pré-análise sem emitir convite'}
        </button>
        {error&&<p role="alert" className="text-sm text-[#8c3225]">{error}</p>}
      </form>
    </>}

    {preflight&&<div role="status" className="fr-light-card rounded-2xl p-4">
      <div className="flex items-start gap-2">
        <ShieldAlert className="h-5 w-5 shrink-0 text-[#a66f19]"/>
        <div>
          <h3 className="font-bold text-[#143d29]">Pré-análise concluída · execução bloqueada</h3>
          <p className="mt-1 text-sm text-[#52685a]">
            {preflight.tenant.display_name} · {preflight.tenant.status}
          </p>
        </div>
      </div>
      <p className="mt-3 text-sm text-[#52685a]">
        Caixinha ativa: {preflight.tenant_active?'Sim':'Não'}.
        Identidade confirmada do candidato: Não.
      </p>
      {preflight.self_approval_blocked&&
        <p className="mt-2 text-sm font-semibold text-[#8a3828]">
          Conflito identificado: tentativa de autoaprovação.
        </p>}
      <p className="mt-2 text-sm font-semibold text-[#8a3828]">
        Nenhum convite, aprovação ou mudança de conta foi realizado.
      </p>
      <CheckCircle2 className="mt-3 h-4 w-4 text-[#0b5635]" aria-hidden="true"/>
    </div>}
  </section>;
};
