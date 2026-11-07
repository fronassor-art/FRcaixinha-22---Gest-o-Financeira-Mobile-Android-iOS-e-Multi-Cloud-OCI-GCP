/** Declarativo: a API/RLS decide permissões reais, NUNCA esta matriz do cliente. */
export const ROLES=['MASTER','TENANT_ADMIN','TENANT_MEMBER','ANONYMOUS'] as const;
export type MatrixRole=typeof ROLES[number];
export const RESOURCES=[
  'PLATFORM_TENANT_REGISTRY','PLATFORM_ADMIN_REFERENCES',
  'ADMIN_ONBOARDING_PREFLIGHT','ADMIN_WORKFLOW_SIMULATOR',
  'TENANT_FINANCIAL_DATA','MEMBER_PRIVATE_DATA',
  'INVITATION_TOKEN_STORAGE','INVITATION_ISSUANCE',
  'MEMBERSHIP_ROLE_CHANGE','DIRECT_AUDIT_MUTATION',
] as const;
export type MatrixResource=typeof RESOURCES[number];
export type MatrixAccess='DENIED'|'METADATA_ONLY'|'SIMULATION_ONLY'|'OWN_TENANT_ONLY'|'OWN_RECORD_ONLY';
export type MasterPermissionMatrix={
  scope:'MASTER_ONBOARDING_PERMISSION_MATRIX';
  source:'DECLARED_POLICY_NOT_RUNTIME_AUTHORITY';
  mode:'DOCUMENTATION_AND_CI_ONLY';
  grants_changed:false;operations_enabled:false;database_migration_required:false;
  roles:MatrixRole[];resources:MatrixResource[];
  permissions:Record<MatrixResource,Record<MatrixRole,MatrixAccess>>;
  enforcement:'FASTAPI_RBAC_PLUS_POSTGRESQL_RLS';
  sensitive_actions:'BLOCKED_PENDING_APPROVAL';
};
const isObject=(value:unknown):value is Record<string,unknown>=>
  typeof value==='object'&&value!==null&&!Array.isArray(value);
const valid=new Set<MatrixAccess>([
  'DENIED','METADATA_ONLY','SIMULATION_ONLY','OWN_TENANT_ONLY','OWN_RECORD_ONLY',
]);
const sensitive=new Set<string>([
  'INVITATION_TOKEN_STORAGE','INVITATION_ISSUANCE',
  'MEMBERSHIP_ROLE_CHANGE','DIRECT_AUDIT_MUTATION',
]);
export function parseMasterPermissionMatrix(raw:unknown):MasterPermissionMatrix{
  if(!isObject(raw)||raw.scope!=='MASTER_ONBOARDING_PERMISSION_MATRIX'||
     raw.source!=='DECLARED_POLICY_NOT_RUNTIME_AUTHORITY'||
     raw.mode!=='DOCUMENTATION_AND_CI_ONLY'||raw.grants_changed!==false||
     raw.operations_enabled!==false||raw.database_migration_required!==false||
     raw.enforcement!=='FASTAPI_RBAC_PLUS_POSTGRESQL_RLS'||
     raw.sensitive_actions!=='BLOCKED_PENDING_APPROVAL'||
     !Array.isArray(raw.roles)||raw.roles.join('|')!==ROLES.join('|')||
     !Array.isArray(raw.resources)||raw.resources.join('|')!==RESOURCES.join('|')||
     !isObject(raw.permissions)){
    throw Error('Matriz de permissões inválida');
  }
  for(const resource of RESOURCES){
    const record=raw.permissions[resource];
    if(!isObject(record))throw Error('Recurso desconhecido');
    for(const role of ROLES){
      if(typeof record[role]!=='string'||!valid.has(record[role] as MatrixAccess)){
        throw Error('Permissão não reconhecida');
      }
      if(role==='ANONYMOUS'&&record[role]!=='DENIED')throw Error('Acesso anônimo proibido');
      if(sensitive.has(resource)&&record[role]!=='DENIED'){
        throw Error('Ação administrativa sensível não liberada');
      }
      if(role==='MASTER'&&(resource==='TENANT_FINANCIAL_DATA'||
         resource==='MEMBER_PRIVATE_DATA')&&record[role]!=='DENIED'){
        throw Error('Dados financeiros do tenant proibidos ao Master');
      }
      if(role!=='MASTER'&&resource.startsWith('PLATFORM_')&&record[role]!=='DENIED'){
        throw Error('Escopo da plataforma não autorizado');
      }
    }
  }
  return raw as MasterPermissionMatrix;
}
