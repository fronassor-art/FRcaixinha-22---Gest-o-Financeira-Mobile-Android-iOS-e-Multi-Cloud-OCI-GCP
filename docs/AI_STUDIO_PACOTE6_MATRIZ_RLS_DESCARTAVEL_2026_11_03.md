# FRcaixinha AI Studio Mobile — Pacote 6: matriz e RLS

Baseline: 27bb9324dd6c8a653712f32186d1379bb8926dd4.
Branch atualizacao-ai-studio-9b46a63187; PR #2 Draft.

## Escopo implementado
- GET /api/v1/master/admin-onboarding/permission-matrix:
  contrato documental do RBAC, exigindo sessão MASTER real no FastAPI.
- Nova seção móvel de comparação de quatro papéis (MASTER,
  TENANT_ADMIN, TENANT_MEMBER e ANONYMOUS) sem troca de sessão.
- Nenhuma permissão é criada pela matriz; a autorização de verdade
  permanece no require_master/require_tenant_access e PostgreSQL RLS.
- Matriz explicitamente bloqueia tokens, emissão de convites reais,
  mudanças de memberships e mutação direta de auditoria.
- Testes CI de registros sintéticos com duas caixinhas:
  Master vê nomes cadastrais, não vê quotas ou memberships;
  Admin de uma caixinha vê apenas a sua.
- Testes CI com papéis app/auth/verifier reais em PostgreSQL 16
  descartável: verificam RLS ENABLE + FORCE e ausência de SELECT,
  INSERT, UPDATE e DELETE sobre invitations,
  invite_email_verification e password_reset_tokens.
  Tentativas reais de SELECT e INSERT devem falhar por SQLSTATE 42501
  e contextos SET LOCAL não podem vazar entre transações.
- Testes sem banco garantem endpoint protegido e contrato de bloqueios.
- Integração no GitHub Actions: testes frontend, backend e PostgreSQL CI.

## Restrições e limites
- Testes de banco exigem flag FRCAIXINHA_CI_ISOLATED=1 e três DSNs
  exclusivos para 127.0.0.1:5432/frcaixinha_ci. Não rodar no banco
  local do celular. NÃO são migrations ou scripts de implantação.
- As verificações de grants e RLS só provam o estado do PostgreSQL
  descartável utilizado no CI, não o banco de produção.
- O catálogo de acesso é declarativo, não um mecanismo de autorização.
- Convites, aprovação, suspensão, alteração de papel e pagamentos
  continuam desativados. MFA e aprovação jurídica ainda não concluídos.
- Não alterar schema, role GRANT/RLS, PKCS12, app ID ou fazer merge.
- Manter o APK atual no aparelho; próxima inspeção planejada na versão 170.

## Próximo pacote sugerido
Teste de recuperação de sessão e resiliência operacional do fluxo Master
em ambientes isolados; sem envio real de e-mail, tokens ou alteração DB.
