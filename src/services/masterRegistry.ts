/** Inventario de plataforma — somente metadados cadastrais autorizados. */
export type RegistryStatus = 'TODOS' | 'RASCUNHO_INATIVO' | 'ATIVO' | 'SUSPENSO' | 'ENCERRADO';
export type TenantStatus = Exclude<RegistryStatus,'TODOS'>;
export type MasterRegistryTenant = {
  id: string;
  display_name: string;
  status: TenantStatus;
  is_owner_box: boolean;
  admin_user_id: string;
  created_at: string;
};
export type MasterRegistryPage = {
  source: 'POSTGRESQL_RLS';
  scope: 'MASTER_TENANT_REGISTRY';
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  status_counts: Record<TenantStatus,number>;
  tenants: MasterRegistryTenant[];
  admin_invitation_status: 'NOT_IMPLEMENTED';
  admin_access_changes: 'BLOCKED_PENDING_APPROVAL';
};
export const REGISTRY_STATES: readonly TenantStatus[] = [
  'RASCUNHO_INATIVO','ATIVO','SUSPENSO','ENCERRADO'
];
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const integer = (v:unknown):v is number => Number.isSafeInteger(v) && Number(v) >= 0;
const record = (v:unknown):v is Record<string,unknown> =>
  typeof v==='object' && v!==null && !Array.isArray(v);

export function registryQuery(params:{
  search:string;status:RegistryStatus;page:number;pageSize?:number;
}):string {
  if(!Number.isSafeInteger(params.page) || params.page<1 || params.page>1000) {
    throw Error('Página inválida');
  }
  if(!['TODOS',...REGISTRY_STATES].includes(params.status)) {
    throw Error('Filtro inválido');
  }
  const search=params.search.trim();
  if(search.length>80) throw Error('Busca excede 80 caracteres');
  const pageSize=params.pageSize??20;
  if(!Number.isSafeInteger(pageSize)||pageSize<5||pageSize>50) {
    throw Error('Tamanho de página inválido');
  }
  return new URLSearchParams({
    search,tenant_status:params.status,
    page:String(params.page),page_size:String(pageSize),
  }).toString();
}

export function parseMasterTenantRegistry(raw:unknown):MasterRegistryPage {
  if(!record(raw)||raw.source!=='POSTGRESQL_RLS'||
     raw.scope!=='MASTER_TENANT_REGISTRY'||
     !integer(raw.total)||!integer(raw.page)||raw.page<1||
     !integer(raw.page_size)||raw.page_size<5||raw.page_size>50||
     typeof raw.has_more!=='boolean'||!Array.isArray(raw.tenants)||
     raw.tenants.length>raw.page_size||
     raw.admin_invitation_status!=='NOT_IMPLEMENTED'||
     raw.admin_access_changes!=='BLOCKED_PENDING_APPROVAL'||
     !record(raw.status_counts))throw Error('Inventário Master inválido');
  const counts=raw.status_counts;
  if(!REGISTRY_STATES.every(status=>integer(counts[status]))) {
    throw Error('Totais cadastrais inválidos');
  }
  const seen=new Set<string>();
  for(const item of raw.tenants){
    if(!record(item)||typeof item.id!=='string'||!uuid.test(item.id)||
       seen.has(item.id)||typeof item.admin_user_id!=='string'||
       !uuid.test(item.admin_user_id)||
       typeof item.display_name!=='string'||!item.display_name.trim()||
       item.display_name.length>255||
       !REGISTRY_STATES.includes(item.status as TenantStatus)||
       typeof item.is_owner_box!=='boolean'||
       typeof item.created_at!=='string'||
       !Number.isFinite(Date.parse(item.created_at))){
      throw Error('Registro cadastral inválido');
    }
    seen.add(item.id);
  }
  if(raw.has_more!==(raw.page*raw.page_size<raw.total)){
    throw Error('Paginação inconsistente');
  }
  return raw as MasterRegistryPage;
}
