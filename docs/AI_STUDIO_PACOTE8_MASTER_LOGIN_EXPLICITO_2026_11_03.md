# Pacote 8 — Autenticação Master explícita / FRcaixinha AI Studio Mobile

Baseline: f1c682fd6ce29c20fa45678dc475717e7def4a6d.
Branch atualizacao-ai-studio-9b46a63187, PR #2 Draft.

- Autenticação MASTER depende de escolha explícita requested_role=MASTER,
  senha validada e confirmação protegida GET /master/owner-access.
- Retirado o antigo fallback que concedia MASTER quando requested_role
  era omitido. A compatibilidade legada sem papel só funciona para
  contas NÃO Master com vínculo TENANT_ADMIN ou TENANT_MEMBER válido.
- Mesmo usuário Master pode autenticar como admin/membro de tenant
  usando papel explícito e vínculo verificado na API.
- Frontend rejeita tentativas de login simultâneas e descarta tokens de
  login recebido após logout, papel divergente ou confirmação Master falha.
  Revogação best-effort desses tokens via logout; a API PostgreSQL continua
  sendo autoridade de revogação real.
- Testes de escolha de papel backend e corridas/erros frontend integrados CI.

Sem MFA nesta entrega; isso permanece pendência para produção.
Nenhuma migration, permissão, conta, convite, saldo ou transação real.
APK será inspecionado no checkpoint 170, não neste build.
