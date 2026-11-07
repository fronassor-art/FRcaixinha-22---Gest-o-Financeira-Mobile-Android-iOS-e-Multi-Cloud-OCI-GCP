# FR Finance AI Studio — M24900: convite e cadastro, pré-diagnóstico seguro

## Objetivo

Preparar o onboarding de administradores e membros sem abrir um caminho
incompleto para criação de conta, concessão de privilégios ou envio de
convites. Somente esta frente AI Studio, sem reutilizar o outro projeto.

### Entrega versionada

- `POST /api/v1/invitations/preflight` exige sessão autenticada válida
  (mesma dependência PostgreSQL que protege outras rotas).
- Hierarquia: Master pode **avaliar** pedido de administrador; Admin pode
  **avaliar** pedido de membro do próprio tenant; Membro recebe 403.
- A requisição passa a aceitar o campo opcional `requiredDocumentId`
  (ou `required_document_id`), UUID da versão contratual proposta.
- A presença do UUID **não prova** publicação nem aceite. O relatório
  sempre retorna `status=BLOCKED`, `activation_authorized=false`,
  `writes_performed=false`, `email_sent=false`.
- A resposta nunca ecoa o e-mail da pessoa, UUID do contrato ou do tenant.
- Para convites administrativos há bloqueios adicionais de MFA Master,
  aprovação independente e identificação do tenant.
- O antigo `POST /api/v1/invitations` continua devolvendo 503 em pedidos
  autorizados, sem criar tokens ou e-mails.
- Recuperação de senha e auto-cadastro públicos permanecem desativados.

## Contrato da API (exemplo sem credenciais)

```json
{
  "target_email": "pessoa@example.invalid",
  "target_role": "TENANT_MEMBER",
  "tenant_id": "00000000-0000-4000-8000-000000000001",
  "requiredDocumentId": "00000000-0000-4000-8000-000000000002"
}
```

Esse JSON é **apenas ilustrativo**. A rota não valida se o destinatário
existe; também não dispara e-mail, não publica documentos e não possui
efeito no banco. A autenticação real de quem requisita o diagnóstico é
obrigatória.

## Próximos controles para efetivação

1. Revisar política comercial e jurídica para contrato Master/plataforma
   e para adesão de membros; armazenar versão e hash publicados.
2. Criar fluxo de token opaco com hash somente no banco, expiração curta,
   limite de tentativas, idempotência, revogação, auditoria e
   segregação de roles, sempre na mesma transação segura.
3. Definir provedor de e-mail com confirmação real de entrega e de posse
   do endereço; não reutilizar simulações de entrega da CI.
4. Implementar aceite por identidade verificada, documento exato, CPF
   validado e regras de unicidade, com vínculo da caixinha autorizado.
5. Para convite administrativo, aplicar MFA Master e revisão independente
   quando exigida pela política, sem autoaprovação.
6. Homologar E2E em ambiente descartável e depois em staging OCI sob
   TLS, RLS e logs seguros antes de qualquer produção.

## Verificação

- Novo `backend/tests/test_m24900_invitation_preflight_ci.py`: testes
  sem DB, sem HTTP externo e sem secrets, adequados ao Termux.
- Proteções M24400/M24600 e RLS de GitHub Actions devem continuar PASS.
- Não houve migração, provisionamento OCI, Pix, criação de contas,
  envio real, acesso SMTP nem reinício do FastAPI local.
- A compilação de APK pela CI não equivale à instalação homologada.

## Comando local

```sh
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m24900_invitation_preflight_ci.py \
  backend/tests/test_m24600_invitation_document_binding_ci.py \
  backend/tests/test_m24400_explicit_invite_acceptance_ci.py \
  backend/tests/test_aistudio_lifecycle_disabled.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
git rev-parse --short HEAD
git status --short
```
