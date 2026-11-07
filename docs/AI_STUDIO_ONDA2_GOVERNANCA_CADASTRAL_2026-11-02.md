# Onda 2 — Cadastro de governança da plataforma (somente leitura)

## Entregue
- Nova aba Master "Caixinhas", integrada à navegação móvel e desktop.
- Endpoint GET /api/v1/master/tenant-registry com validação require_master
  e contexto RLS PostgreSQL; pesquisa literal por nome, filtro por estado,
  paginação limitada e totais cadastrais por estado.
- Exibição de nome da caixinha, estado, marca de caixinha inaugural,
  identificador técnico UUID do responsável principal e data de cadastro.
- O backend consulta exclusivamente public.tenants; não lê users,
  memberships, e-mails, CPF, telefone, saldos, transações ou contribuições.
- Interface sem seed financeiro, com busca, filtro, paginação, recarga,
  estados vazios e falha de rede; não afirma cadastro real quando DB falha.
- Testes Python e TypeScript no fluxo de GitHub Actions.

## Bloqueios deliberados
- Convidar, aprovar, ativar ou suspender administrador: NÃO habilitado.
- Envio de e-mail de convites e aceite: NÃO implementado.
- Lista nominal de múltiplos administradores por tenant: RLS de users
  e memberships não autoriza ao Master. Usa-se apenas o UUID do
  responsável principal registrado na tabela tenants.
- Não incluir novas políticas RLS, migrations reais, dados do projeto
  independente, operações financeiras ou novas credenciais neste pacote.
- O cliente só apresenta dados; não concede autorização.
- MFA do proprietário permanece requisito para produção.

## Próximo pacote
Desenhar workflow administrativo transacional com autorização explícita,
convite de uso único, registro de aceite, auditoria, idempotência,
revogação e privilégios mínimos, mantendo o Master fora das finanças.
Antes de mudar RLS ou schema do banco local, obter aprovação específica.
