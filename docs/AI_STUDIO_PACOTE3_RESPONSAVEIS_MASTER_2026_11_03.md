# Pacote 3 — Responsáveis cadastrais da plataforma AI Studio

Checkpoint: branch atualizacao-ai-studio-9b46a63187, PR #2 Draft,
baseline 7ab450cf63e12fcdc9e28f6178942eb57e3b8896.

## Funcionalidades
- Aba Master "Administradores", localizada em Mais no Android; CTA no
  dashboard "Responsáveis cadastrais".
- GET /api/v1/master/admin-registry autorizado por require_master e RLS.
- Agrupamento de UUID do responsável principal de cada caixinha, total de
  caixinhas e contagem por estado, pesquisa por UUID e paginação.
- Os dados vêm apenas de public.tenants. Não consulta tabelas users,
  credentials, memberships, financeiro, saldos ou membros de caixinhas.
- Testes de interface, escopo Master, validação de resposta e autorização
  da API no workflow GitHub Actions.

## Limites obrigatórios
- tenants.admin_user_id é referência técnica, NÃO comprovação de conta
  ativa, identidade verificada ou membership administrador operacional.
- Convites, suspensões, aprovações e revogações continuam bloqueados.
- Sem alterar políticas RLS, sem migration real, sem dinheiro real, sem
  compartilhar o banco com qualquer outro projeto FRcaixinha.
- MFA Master segue obrigatório para produção e ainda não implementado.

## Continuidade
O próximo pacote precisará especificar onboarding transacional, aceite
de convite de uso único, auditoria, revogação, prevenção de autoaprovação e
proteções RLS específicas. Requer autorização própria para mudanças de
schema/grants no banco real.
