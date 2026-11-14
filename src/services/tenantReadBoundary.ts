/** Fronteira adicional do cliente, NÃO substitui RBAC e RLS do servidor. */
export type TenantRole = 'TENANT_ADMIN' | 'TENANT_MEMBER';
export type TenantDashboard = {
  source:'POSTGRESQL_RLS';tenant_id:string;role:TenantRole;
  quota_count_visible:number;contribution_count_visible:number;
  loan_count_visible:number;member_count_visible?:number;
  financial_operations:'PENDING_BANK_RECONCILIATION';
};
export type TenantMember = {
  id:string;name:string;role:string;status:string;joined_at:string;
};
export type TenantMembersPage = {
  source:'POSTGRESQL_RLS';tenant_id:string;members:TenantMember[];
};
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const record=(value:unknown):value is Record<string,unknown> =>
  value!==null&&typeof value==='object'&&!Array.isArray(value);
const safeCount=(n:unknown):n is number =>
  typeof n==='number'&&Number.isSafeInteger(n)&&n>=0;
const safeText=(value:unknown,max=200):value is string =>
  typeof value==='string'&&value.trim().length>0&&value.length<=max;

export function assertTenantReadScope(
  user:{role:string;tenantId?:string|null}|null,
  tenantId:string,resource:'DASHBOARD'|'MEMBERS',
):TenantRole{
  if(!UUID.test(tenantId)||!user||user.tenantId!==tenantId||
     (user.role!=='TENANT_ADMIN'&&user.role!=='TENANT_MEMBER')||
     (resource==='MEMBERS'&&user.role!=='TENANT_ADMIN')){
    throw Error('Consulta fora do perfil ou da caixinha ativa');
  }
  return user.role as TenantRole;
}

export function parseTenantDashboard(
  raw:unknown,tenantId:string,expectedRole:TenantRole,
):TenantDashboard{
  if(!UUID.test(tenantId)||!record(raw)||
     raw.source!=='POSTGRESQL_RLS'||raw.tenant_id!==tenantId||
     raw.role!==expectedRole||
     !safeCount(raw.quota_count_visible)||
     !safeCount(raw.contribution_count_visible)||
     !safeCount(raw.loan_count_visible)||
     raw.financial_operations!=='PENDING_BANK_RECONCILIATION'){
    throw Error('Resumo de tenant inválido; dados descartados');
  }
  if(expectedRole==='TENANT_ADMIN'){
    if(!safeCount(raw.member_count_visible)){
      throw Error('Contagem administrativa indisponível');
    }
  }else if(Object.prototype.hasOwnProperty.call(raw,'member_count_visible')){
    throw Error('Resposta de membro contém dados administrativos');
  }
  // Reconstrói somente campos autorizados, sem repassar campos adicionais.
  const dashboard:TenantDashboard={
    source:'POSTGRESQL_RLS',tenant_id:tenantId,role:expectedRole,
    quota_count_visible:raw.quota_count_visible,
    contribution_count_visible:raw.contribution_count_visible,
    loan_count_visible:raw.loan_count_visible,
    financial_operations:'PENDING_BANK_RECONCILIATION',
  };
  if(expectedRole==='TENANT_ADMIN'){
    dashboard.member_count_visible=raw.member_count_visible as number;
  }
  return dashboard;
}

export function parseTenantMembers(raw:unknown,tenantId:string):TenantMembersPage{
  if(!UUID.test(tenantId)||!record(raw)||raw.source!=='POSTGRESQL_RLS'||
     raw.tenant_id!==tenantId||!Array.isArray(raw.members)||
     raw.members.length>200){
    throw Error('Lista de membros fora do contexto autorizado');
  }
  const seen=new Set<string>();
  const members:TenantMember[]=[];
  for(const item of raw.members){
    if(!record(item)||!safeText(item.id,36)||!UUID.test(item.id)||
       seen.has(item.id.toLowerCase())||!safeText(item.name)||
       !['TENANT_ADMIN','TENANT_MEMBER'].includes(String(item.role))||
       !safeText(item.status,32)||!safeText(item.joined_at,48)||
       !Number.isFinite(Date.parse(String(item.joined_at)))||
       ['cpf','email','phone','password_hash','balance','amount_paid']
         .some(field=>Object.prototype.hasOwnProperty.call(item,field))){
      throw Error('Registro de membro inválido ou contendo informações privadas');
    }
    seen.add(item.id.toLowerCase());
    members.push({
      id:item.id,name:item.name,role:item.role as string,
      status:item.status,joined_at:item.joined_at,
    });
  }
  return {source:'POSTGRESQL_RLS',tenant_id:tenantId,members};
}
