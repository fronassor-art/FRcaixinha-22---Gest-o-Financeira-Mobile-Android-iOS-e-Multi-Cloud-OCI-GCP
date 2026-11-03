import React,{useEffect,useState} from 'react';
import {RefreshCw,ShieldCheck} from 'lucide-react';
import {financialApi} from '../services/financialApiService';
import {
  MatrixRole,MatrixResource,MasterPermissionMatrix,ROLES,RESOURCES,
} from '../services/masterPermissionMatrix';
import {AppState} from '../services/store';

const titles:Record<MatrixResource,string>={
  PLATFORM_TENANT_REGISTRY:'Cadastro de caixinhas da plataforma',
  PLATFORM_ADMIN_REFERENCES:'Responsáveis cadastrais da plataforma',
  ADMIN_ONBOARDING_PREFLIGHT:'Pré-análise de novos administradores',
  ADMIN_WORKFLOW_SIMULATOR:'Simulador de convite e auditoria',
  TENANT_FINANCIAL_DATA:'Dados financeiros da própria caixinha',
  MEMBER_PRIVATE_DATA:'Dados financeiros individuais',
  INVITATION_TOKEN_STORAGE:'Armazenamento de tokens de convite',
  INVITATION_ISSUANCE:'Emissão de convites reais',
  MEMBERSHIP_ROLE_CHANGE:'Alteração de papéis e vínculos',
  DIRECT_AUDIT_MUTATION:'Alteração direta do histórico de auditoria',
};
const roleLabels:Record<MatrixRole,string>={
  MASTER:'Administrador Master',
  TENANT_ADMIN:'Administrador da caixinha',
  TENANT_MEMBER:'Membro',
  ANONYMOUS:'Sem autenticação',
};
const accessLabels:Record<string,string>={
  DENIED:'Bloqueado',
  METADATA_ONLY:'Somente metadados',
  SIMULATION_ONLY:'Somente simulação',
  OWN_TENANT_ONLY:'Limitado à própria caixinha',
  OWN_RECORD_ONLY:'Somente registros próprios',
};

export const MasterPermissionMatrixView:React.FC<{state:AppState}>=({state})=>{
  const scope=[state.currentUserId,state.currentRole,state.currentTenantId].join('|');
  const [role,setRole]=useState<MatrixRole>('MASTER');
  const [revision,setRevision]=useState(0);
  const key=scope+'|'+revision;
  const [result,setResult]=useState<{
    key:string;status:'loading'|'ready'|'error';data?:MasterPermissionMatrix
  }>({key:'',status:'loading'});
  useEffect(()=>{
    if(state.currentRole!=='MASTER')return;
    let active=true;
    setResult({key,status:'loading'});
    financialApi.fetchMasterPermissionMatrix()
      .then(data=>{if(active)setResult({key,status:'ready',data});})
      .catch(()=>{if(active)setResult({key,status:'error'});});
    return ()=>{active=false;};
  },[key,state.currentRole]);
  if(state.currentRole!=='MASTER')return (
    <section role="alert">Acesso à matriz restrito ao Master.</section>
  );
  const current=result.key===key?result:{key,status:'loading' as const};
  const data=current.status==='ready'?current.data:undefined;
  return <section className="fr-light-card space-y-3 rounded-2xl p-4"
    aria-label="Matriz de permissões por perfil">
    <div className="flex items-start gap-2">
      <div className="flex-1">
        <h3 className="text-lg font-bold text-[#153e2a]">Matriz de permissões</h3>
        <p className="mt-1 text-xs text-[#546b5c]">
          Referência declarativa. A autorização real depende de sessão validada,
          FastAPI e RLS do PostgreSQL.
        </p>
      </div>
      <ShieldCheck className="h-5 w-5 shrink-0 text-[#a77a2b]"/>
    </div>
    {current.status==='loading'&&<p role="status">Consultando política documentada...</p>}
    {current.status==='error'&&<div role="alert">
      <p className="text-sm text-[#833f2e]">Matriz indisponível.</p>
      <button type="button" onClick={()=>setRevision(n=>n+1)}
        className="mt-2 flex min-h-11 items-center gap-2 text-[#0d5336]">
        <RefreshCw className="h-4 w-4"/>Tentar novamente
      </button>
    </div>}
    {data&&<>
      <label htmlFor="matrix-role" className="block text-sm font-semibold text-[#153e2a]">
        Perfil para comparação (não altera sua sessão)
      </label>
      <select id="matrix-role" value={role}
        onChange={ev=>setRole(ev.target.value as MatrixRole)}
        className="min-h-11 w-full rounded-lg border border-[#a6c3a8] bg-white px-3 text-base">
        {ROLES.map(x=><option key={x} value={x}>{roleLabels[x]}</option>)}
      </select>
      <ul className="divide-y divide-[#dceadd]">
        {RESOURCES.map(resource=><li key={resource}
          className="flex items-start justify-between gap-2 py-3">
          <span className="max-w-[62%] text-sm text-[#254a35]">{titles[resource]}</span>
          <span className="text-right text-xs font-semibold text-[#8a5d25]">
            {accessLabels[data.permissions[resource][role]]}
          </span>
        </li>)}
      </ul>
      <p className="text-xs text-[#8b3828]">
        Tokens, convites reais e mudanças de papéis estão bloqueados
        para todos os perfis. Nenhuma permissão foi concedida.
      </p>
    </>}
  </section>;
};
