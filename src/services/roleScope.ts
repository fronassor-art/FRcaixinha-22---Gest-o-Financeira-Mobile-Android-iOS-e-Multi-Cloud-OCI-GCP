import type { UserRole } from '../types';

// Fonte unica de autorizacao para renderizar abas apos troca de contexto.
const TABS: Record<UserRole, readonly string[]> = {
  MASTER: ['DASHBOARD','CAIXINHAS','LICENCAS','ADMINISTRADORES','ONBOARDING','SUPORTE','NUVEM','AUDITORIA','NOTIFICACOES'],
  TENANT_ADMIN: ['DASHBOARD','MEMBROS','CONTRIBUICOES','EMPRESTIMOS','CAMPANHAS_MEMBROS','LEDGER','FECHAMENTO','NOTIFICACOES'],
  TENANT_MEMBER: ['MEU_PAINEL','MINHAS_CONTRIBUICOES','MEU_EMPRESTIMO','MINHAS_OPORTUNIDADES','MEU_RESULTADO','NOTIFICACOES'],
};
export const tabsAllowedToRole = (role: UserRole): readonly string[] => TABS[role];
export const isRoleTabAllowed = (role: UserRole, tab: string): boolean =>
  TABS[role].includes(tab);
export const initialRoleTab = (role: UserRole): string =>
  role === 'TENANT_MEMBER' ? 'MEU_PAINEL' : 'DASHBOARD';
