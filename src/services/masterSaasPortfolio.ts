/** Contrato de integridade do inventário comercial Master — sem dados patrimoniais. */
export type SaasTenantStatus = 'RASCUNHO_INATIVO'|'ATIVO'|'SUSPENSO'|'ENCERRADO';
export type SaasStatusFilter = SaasTenantStatus|'TODOS';
export const SAAS_TENANT_STATES: readonly SaasTenantStatus[] =
  ['RASCUNHO_INATIVO','ATIVO','SUSPENSO','ENCERRADO'];
export const SAAS_STATUS_LABELS: Record<SaasStatusFilter,string> = {
  TODOS:'Todos os estados',RASCUNHO_INATIVO:'Rascunho inativo',
  ATIVO:'Ativa',SUSPENSO:'Suspensa',ENCERRADO:'Encerrada'
};
export type MasterSaasTenant = {
  id:string;display_name:string;admin_user_id:string;
  tenant_status:SaasTenantStatus;registered_at:string;
  admin_total:number;admin_active:number;admin_suspended:number;
  admin_draft:number;admin_closed:number;
  licensed_plan:string|null;license_status:string|null;effective_status:string|null;
  valid_from:string|null;valid_until:string|null;
  prepared_plan:string|null;prepared_period:string|null;preparation_status:string|null;
  prepared_at:string|null;members_limit:number|null;quotas_limit:number|null;
};
export type MasterSaasPortfolio = {
  source:'POSTGRESQL_RLS';scope:'MASTER_SAAS_PORTFOLIO';boxes_limit_policy:'NOT_DEFINED';
  total:number;page:number;page_size:number;tenant_status_filter:SaasStatusFilter;
  has_more:boolean;tenants:MasterSaasTenant[];
};
const record=(x:unknown):x is Record<string,unknown> =>
  x!==null && typeof x==='object' && !Array.isArray(x);
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const validInt=(x:unknown) => Number.isSafeInteger(x)&&Number(x)>=0;
const date=(x:unknown) => typeof x==='string'&&x.length<=48&&
  /\d{4}-\d{2}-\d{2}T/.test(x)&&Number.isFinite(Date.parse(x));
const nilOr=(x:unknown,check:(value:unknown)=>boolean)=>x===null||check(x);
const short=(x:unknown)=>typeof x==='string'&&x.length>0&&x.length<=70;
const plan=(x:unknown)=>typeof x==='string'&&
  ['ESSENCIAL','INTERMEDIARIO','AMPLIADO'].includes(x);
const license=(x:unknown)=>typeof x==='string'&&
  ['ACTIVE','SUSPENDED','EXPIRED','REVOKED'].includes(x);
const effective=(x:unknown)=>typeof x==='string'&&
  ['ACTIVE','SUSPENDED','EXPIRED','REVOKED','NOT_STARTED'].includes(x);
const keys = new Set(['id','display_name','admin_user_id','tenant_status',
  'registered_at','admin_total','admin_active','admin_suspended','admin_draft',
  'admin_closed','licensed_plan','license_status','effective_status','valid_from',
  'valid_until','prepared_plan','prepared_period','preparation_status','prepared_at',
  'members_limit','quotas_limit']);
export function parseMasterSaasPortfolio(raw:unknown,filter:SaasStatusFilter,page:number):MasterSaasPortfolio {
  if(!record(raw)||raw.source!=='POSTGRESQL_RLS'||raw.scope!=='MASTER_SAAS_PORTFOLIO'||
     raw.boxes_limit_policy!=='NOT_DEFINED'||raw.tenant_status_filter!==filter||
     !validInt(raw.total)||!validInt(raw.page)||raw.page!==page||
     raw.page_size!==20||typeof raw.has_more!=='boolean'||!Array.isArray(raw.tenants)||
     raw.tenants.length>20||raw.has_more!==(page*20<Number(raw.total)))
    throw Error('Inventário comercial Master inválido');
  const seen=new Set<string>();
  for(const tenant of raw.tenants){
    if(!record(tenant)||Object.keys(tenant).some(k=>!keys.has(k))||
       typeof tenant.id!=='string'||!uuid.test(tenant.id)||seen.has(tenant.id)||
       typeof tenant.admin_user_id!=='string'||!uuid.test(tenant.admin_user_id)||
       typeof tenant.display_name!=='string'||tenant.display_name.trim().length===0||
       tenant.display_name.length>255||!SAAS_TENANT_STATES.includes(tenant.tenant_status as SaasTenantStatus)||
       (filter!=='TODOS'&&tenant.tenant_status!==filter)||!date(tenant.registered_at)||
       !validInt(tenant.admin_total)||!validInt(tenant.admin_active)||
       !validInt(tenant.admin_suspended)||!validInt(tenant.admin_draft)||
       !validInt(tenant.admin_closed)||Number(tenant.admin_total)<1||
       Number(tenant.admin_total)!==Number(tenant.admin_active)+Number(tenant.admin_suspended)+
       Number(tenant.admin_draft)+Number(tenant.admin_closed)||
       !nilOr(tenant.licensed_plan,plan)||!nilOr(tenant.license_status,license)||
       !nilOr(tenant.effective_status,effective)||
       !nilOr(tenant.valid_from,date)||!nilOr(tenant.valid_until,date)||
       !nilOr(tenant.prepared_plan,plan)||!nilOr(tenant.prepared_period,short)||
       !nilOr(tenant.preparation_status,short)||!nilOr(tenant.prepared_at,date)||
       !nilOr(tenant.members_limit,validInt)||!nilOr(tenant.quotas_limit,validInt))
      throw Error('Registro comercial Master inválido');
    if(tenant.licensed_plan===null &&
       [tenant.license_status,tenant.effective_status,tenant.valid_from,
        tenant.valid_until,tenant.members_limit,tenant.quotas_limit].some(v=>v!==null))
      throw Error('Licença sem vínculo no PostgreSQL');
    if(tenant.licensed_plan!==null &&
       [tenant.license_status,tenant.effective_status,tenant.valid_from,
        tenant.valid_until].some(v=>v===null))
      throw Error('Licença incompleta');
    if(tenant.prepared_plan===null &&
       [tenant.prepared_period,tenant.preparation_status,tenant.prepared_at].some(v=>v!==null))
      throw Error('Preparação incompleta');
    if(typeof tenant.valid_from==='string'&&typeof tenant.valid_until==='string'&&
       Date.parse(tenant.valid_until)<=Date.parse(tenant.valid_from))
      throw Error('Vigência da licença inválida');
    seen.add(tenant.id);
  }
  return raw as MasterSaasPortfolio;
}
