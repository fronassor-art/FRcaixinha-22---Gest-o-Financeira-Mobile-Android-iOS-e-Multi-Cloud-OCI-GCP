# M24600 — Convite com documento contratual obrigatório (CI isolado)

**Escopo:** exclusivamente FR Finance AI Studio, branch `atualizacao-ai-studio-9b46a63187`. Não envolve FRcaixinha 2.2, OCI, Pix, fornecedor de e-mail, credencial real nem migração no Termux.

## Lacuna corrigida

O M24400/M24500 passou a exigir que o aceite reconhecesse o `required_document_id` do convite. Porém, `prepare_invitation_ci` não vinculava esse documento ao gerar o convite; os próprios testes corrigiam a lacuna com `UPDATE public.invitations SET required_document_id` depois da criação. Um convite sintético, portanto, nascia sem versão exigida.

## Implementação M24600

- `prepare_invitation_ci` exige `required_document_id` como argumento obrigatório, com tipo UUID.
- Antes do INSERT, em **transação única no banco descartável**, confere que o documento existe, é `TENANT_MEMBERSHIP` e foi publicado. `PLATFORM_LICENSE`, UUID inexistente e documento não publicado são rejeitados.
- O `required_document_id` é gravado **no INSERT original**, junto do hash de token, identidade do convite e expiração. Nenhuma etapa posterior precisa corrigir o vínculo.
- Testes de integração com PostgreSQL CI passam a testar a gravação originária e a rejeição de documentos não elegíveis, sem criar convite ou evento de aceite em caso de falha.
- Testes locais sem PostgreSQL verificam contrato de assinatura, código, isolamento CI e inexistência do remendo SQL na fixture.
- Continua obrigatório consentimento afirmativo e digest exato do documento para aceitar o convite. Entrega e verificação de e-mail continuam somente sintéticas, sem prova externa.

## Limites

Não existe convite público, cadastro de usuário liberado, confirmação real de e-mail, assinatura eletrônica de produção ou provisionamento remoto. O módulo permanece sob `_ci_only` e o endpoint público continua HTTP 503. Nenhum status das 147 cláusulas é promovido; `production_release_authorized` continua falso.

## Validação no Termux (sem aplicar migrações)

```bash
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m24400_explicit_invite_acceptance_ci.py \
  backend/tests/test_m24500_existing_identity_versioned_consent_ci.py \
  backend/tests/test_m24600_invitation_document_binding_ci.py \
  backend/tests/test_m24000_contract_gap_147_ci.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
git rev-parse --short HEAD
git status --short
```

Os testes que usam PostgreSQL só devem rodar no GitHub Actions, em `frcaixinha_ci` (porta 5432). Não executar contra a base local `frcaixinha_aistudio_dev` (porta 5433).
