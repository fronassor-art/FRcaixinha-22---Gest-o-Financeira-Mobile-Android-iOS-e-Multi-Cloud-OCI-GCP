/** Rotulos de seguranca - nenhum nome, e-mail ou dado financeiro do tenant. */
import type {AuthenticatedUser} from './authService';
export function sessionRoleLabel(role:AuthenticatedUser['role']):string {
  switch(role){
    case 'MASTER': return 'Administrador Master';
    case 'TENANT_ADMIN': return 'Administrador da caixinha';
    case 'TENANT_MEMBER': return 'Membro';
  }
}
export function sessionTenantLabel(tenantId:string|null):string {
  if(tenantId===null)return 'Plataforma';
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(tenantId))
    return 'Caixinha não identificada';
  // Identificador curto apenas para diferenciar sessões próprias;
  // jamais assume que este nome prove acesso ou habilite operações.
  return 'Caixinha ' + tenantId.slice(0,8).toUpperCase();
}
