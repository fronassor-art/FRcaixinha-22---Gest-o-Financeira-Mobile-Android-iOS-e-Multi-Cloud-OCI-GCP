/** Contratos estritos para pré-análise de governança Master (sem gravação). */
export type GateName =
  'MASTER_MFA'|'DUAL_CONTROL'|'EMAIL_OWNERSHIP'|'INVITE_SINGLE_USE'|
  'EXPIRATION_AND_REVOCATION'|'TRANSACTIONAL_AUDIT'|
  'IDENTITY_MEMBERSHIP_RECHECK'|'DELIVERY_PROVIDER_VERIFIED'|'LEGAL_APPROVAL';
export const REQUIRED_GATES: readonly GateName[]=[
  'MASTER_MFA','DUAL_CONTROL','EMAIL_OWNERSHIP','INVITE_SINGLE_USE',
  'EXPIRATION_AND_REVOCATION','TRANSACTIONAL_AUDIT',
  'IDENTITY_MEMBERSHIP_RECHECK','DELIVERY_PROVIDER_VERIFIED','LEGAL_APPROVAL',
];
export const ONBOARDING_FLOW_STATES=[
  'REQUESTED','EMAIL_VERIFIED','MASTER_REVIEW','APPROVED',
  'INVITE_PREPARED','DELIVERED','ACCEPTED','ACTIVE',
  'REJECTED','REVOKED','EXPIRED',
] as const;
export type MasterOnboardingCapabilities={
  scope:'MASTER_ADMIN_ONBOARDING_PREPARATION';
  mode:'READ_ONLY_PREFLIGHT';
  operations_enabled:false;
  real_invites_enabled:false;
  real_account_changes_enabled:false;
  workflow_states:string[];
  gates:Record<GateName,'BLOCKED'>;
  next_action:'REQUIRES_SEPARATE_SCHEMA_RLS_AND_SECURITY_APPROVAL';
};
export type MasterOnboardingPreflight={
  source:'POSTGRESQL_RLS';
  scope:'MASTER_ADMIN_ONBOARDING_PREFLIGHT';
  result:'BLOCKED_PREPARATION_ONLY';
  tenant:{
    id:string;
    display_name:string;
    status:'RASCUNHO_INATIVO'|'ATIVO'|'SUSPENSO'|'ENCERRADO';
    is_owner_box:boolean;
  };
  target_role:'TENANT_ADMIN';
  candidate_reference_present:boolean;
  candidate_identity_verified:false;
  tenant_active:boolean;
  self_approval_blocked:boolean;
  blocking_reasons:string[];
  writes_performed:false;
  invitation_created:false;
  approval_granted:false;
  real_account_changed:false;
};
const obj=(value:unknown):value is Record<string,unknown>=>
  typeof value==='object'&&value!==null&&!Array.isArray(value);
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const states=['RASCUNHO_INATIVO','ATIVO','SUSPENSO','ENCERRADO'];
export function parseOnboardingCapabilities(raw:unknown):MasterOnboardingCapabilities{
  if(!obj(raw)||raw.scope!=='MASTER_ADMIN_ONBOARDING_PREPARATION'||
     raw.mode!=='READ_ONLY_PREFLIGHT'||raw.operations_enabled!==false||
     raw.real_invites_enabled!==false||raw.real_account_changes_enabled!==false||
     raw.next_action!=='REQUIRES_SEPARATE_SCHEMA_RLS_AND_SECURITY_APPROVAL'||
     !obj(raw.gates)||!REQUIRED_GATES.every(k=>raw.gates && (raw.gates as Record<string,unknown>)[k]==='BLOCKED')||
     !Array.isArray(raw.workflow_states)||
     raw.workflow_states.join('|')!==ONBOARDING_FLOW_STATES.join('|')){
    throw Error('Resposta de prontidão administrativa inválida');
  }
  return raw as MasterOnboardingCapabilities;
}
export function parseOnboardingPreflight(raw:unknown):MasterOnboardingPreflight{
  if(!obj(raw)||raw.source!=='POSTGRESQL_RLS'||
     raw.scope!=='MASTER_ADMIN_ONBOARDING_PREFLIGHT'||
     raw.result!=='BLOCKED_PREPARATION_ONLY'||raw.target_role!=='TENANT_ADMIN'||
     raw.candidate_identity_verified!==false||
     raw.writes_performed!==false||raw.invitation_created!==false||
     raw.approval_granted!==false||raw.real_account_changed!==false||
     typeof raw.candidate_reference_present!=='boolean'||
     typeof raw.tenant_active!=='boolean'||
     typeof raw.self_approval_blocked!=='boolean'||
     !Array.isArray(raw.blocking_reasons)||
     !raw.blocking_reasons.every((reason:unknown)=>typeof reason==='string'&&reason.length<100)||
     !REQUIRED_GATES.every(k=>raw.blocking_reasons.includes('GATE_'+k+'_BLOCKED'))||
     !obj(raw.tenant)||typeof raw.tenant.id!=='string'||!uuid.test(raw.tenant.id)||
     typeof raw.tenant.display_name!=='string'||!raw.tenant.display_name.trim()||
     !states.includes(String(raw.tenant.status))||
     typeof raw.tenant.is_owner_box!=='boolean'||
     raw.tenant_active!==(raw.tenant.status==='ATIVO')){
    throw Error('Pré-análise administrativa inválida');
  }
  return raw as MasterOnboardingPreflight;
}
export function validatePreflightInput(args:{
  tenantId:string;candidateUserId?:string;purpose:string;
}):void{
  if(!uuid.test(args.tenantId)||
     (args.candidateUserId!==undefined&&!uuid.test(args.candidateUserId))||
     args.purpose.trim().length<15||args.purpose.length>240){
    throw Error('Informe UUID válido e justificativa técnica de 15 a 240 caracteres');
  }
}
