/** Referências técnicas de administradores primários cadastrados em tenants. */
export type PrimaryAdminSummary={
  admin_user_id:string;
  tenant_count:number;
  active_count:number;
  suspended_count:number;
  draft_count:number;
  closed_count:number;
};
export type MasterAdminRegistryPage={
  source:'POSTGRESQL_RLS';
  scope:'MASTER_PRIMARY_ADMIN_REGISTRY';
  total:number;
  page:number;
  page_size:number;
  has_more:boolean;
  identity_status:'UNVERIFIED_REFERENCE_ONLY';
  invitation_status:'NOT_IMPLEMENTED';
  access_changes:'BLOCKED_PENDING_APPROVAL';
  administrators:PrimaryAdminSummary[];
};
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const obj=(value:unknown):value is Record<string,unknown>=>
  typeof value==='object'&&value!==null&&!Array.isArray(value);
const nonnegativeInt=(value:unknown):value is number=>
  typeof value==='number'&&Number.isSafeInteger(value)&&value>=0;

export function adminRegistryQuery(args:{search:string;page:number;pageSize?:number}):string{
  const search=args.search.trim();
  const pageSize=args.pageSize??20;
  if(search.length>36||!nonnegativeInt(args.page)||args.page<1||args.page>1000||
     !nonnegativeInt(pageSize)||pageSize<5||pageSize>50){
    throw Error('Parâmetros da consulta de administradores inválidos');
  }
  return new URLSearchParams({
    search,page:String(args.page),page_size:String(pageSize),
  }).toString();
}

export function parseMasterAdminRegistry(raw:unknown):MasterAdminRegistryPage{
  if(!obj(raw)||raw.source!=='POSTGRESQL_RLS'||
     raw.scope!=='MASTER_PRIMARY_ADMIN_REGISTRY'||
     !nonnegativeInt(raw.total)||!nonnegativeInt(raw.page)||raw.page<1||
     !nonnegativeInt(raw.page_size)||raw.page_size<5||raw.page_size>50||
     typeof raw.has_more!=='boolean'||
     raw.has_more!==(raw.page*raw.page_size<raw.total)||
     raw.identity_status!=='UNVERIFIED_REFERENCE_ONLY'||
     raw.invitation_status!=='NOT_IMPLEMENTED'||
     raw.access_changes!=='BLOCKED_PENDING_APPROVAL'||
     !Array.isArray(raw.administrators)||
     raw.administrators.length>raw.page_size){
    throw Error('Resposta do cadastro de administradores inválida');
  }
  const numericKeys=[
    'tenant_count','active_count','suspended_count','draft_count','closed_count'
  ] as const;
  const seen=new Set<string>();
  const admins:PrimaryAdminSummary[]=[];
  for(const entry of raw.administrators){
    if(!obj(entry)||typeof entry.admin_user_id!=='string'||
       !UUID.test(entry.admin_user_id)||seen.has(entry.admin_user_id.toLowerCase())||
       !numericKeys.every(key=>nonnegativeInt(entry[key]))){
      throw Error('Cadastro administrativo inconsistente');
    }
    const tenantCount=Number(entry.tenant_count);
    const activeCount=Number(entry.active_count);
    const suspendedCount=Number(entry.suspended_count);
    const draftCount=Number(entry.draft_count);
    const closedCount=Number(entry.closed_count);
    if(tenantCount!==activeCount+suspendedCount+draftCount+closedCount){
      throw Error('Contagens administrativas divergentes');
    }
    seen.add(entry.admin_user_id.toLowerCase());
    admins.push({
      admin_user_id:entry.admin_user_id,
      tenant_count:tenantCount,
      active_count:activeCount,
      suspended_count:suspendedCount,
      draft_count:draftCount,
      closed_count:closedCount,
    });
  }
  return {
    source:'POSTGRESQL_RLS',scope:'MASTER_PRIMARY_ADMIN_REGISTRY',
    total:raw.total,page:raw.page,page_size:raw.page_size,
    has_more:raw.has_more,
    identity_status:'UNVERIFIED_REFERENCE_ONLY',
    invitation_status:'NOT_IMPLEMENTED',
    access_changes:'BLOCKED_PENDING_APPROVAL',
    administrators:admins,
  };
}
