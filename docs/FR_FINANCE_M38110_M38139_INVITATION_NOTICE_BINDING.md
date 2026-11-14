# FR Finance AI Studio — M38110–M38139 | Convite, identidade e versão contratual vinculados ao aviso

Origem: M38109, commit 92772d3, 1.286 testes Python PASS no Termux. Projeto AI Studio somente, sem misturar com FR 2.2.

## O que foi desenvolvido
Um novo contrato imutável `PendingMemberInvitationEvidence` correlaciona (1) UUID de convite, (2) caixinha, (3) UUID da identidade já conhecida, (4) perfil TENANT_MEMBER, (5) UUID da versão de adesão publicada, (6) SHA-256 exato do documento, (7) ciclo e revisão do convite e (8) validade.

A função `invitation_notice_digest` calcula um SHA-256 com separação de domínio e parâmetros canônicos. Nenhum nome, CPF, telefone, endereço de e-mail, token ou texto contratual é incorporado ao resumo. O digest **não é assinatura** e só representa correlação hipotética de dados que um worker futuro obteria por leitura confiável.

A função `inspect_pending_member_invitation_notice` reutiliza a política de notificações M15000, confrontando o aviso com convite, destinatário, tenant, papel, ciclo, instante, revisão e resumo contratual. Expiração, revogação, aceite já ocorrido, versão/documento divergente, ausência de publicação ou alegações de autenticação são recusados.

O retorno é um `PendingInvitationNoticePreview` com permissões explicitamente falsas para envio, inclusão na inbox, prova de titularidade, aceite, criação/ativação de usuário ou produção. Essa função não publica notificações nem reabre convites.

## Limites e próximos gates
- O recorte é **aviso pendente de convite para membro já identificado**, pois o tipo histórico `INVITATION_ACCEPTANCE_PENDING` existe com escopo TENANT_MEMBER. Não inventa identidade de convidado desconhecido, nem estabelece fluxo de convite de administrador.
- Nenhum objeto Python vindo de HTTP constitui evidência autenticada. Integração real exige SELECT autorizado por tenant, locks adequados, transação auditada, idempotência persistente, RLS, prova real de e-mail/consentimento e aprovação jurídica.
- 109 arquivos SQL permanecem intactos. Não consultar ou alterar o PostgreSQL original 5433, nem ativar OCI, SMTP, e-mail, conta real ou Pix.
- `EMAIL_REAL=OFF`, `INVITATIONS_REAL=OFF`, `PIX_REAL=OFF`, `ACTIVATION_REAL=OFF`, `PRODUCTION=BLOCKED`.

## Homologação
```sh
PYTHONPATH=backend python -m pytest -q -p no:cacheprovider backend/tests/test_m38110_invitation_notice_binding_ci.py backend/tests/test_m15000_notifications_ci.py backend/tests/test_m29100_m29400_onboarding_chain_ci.py
```
