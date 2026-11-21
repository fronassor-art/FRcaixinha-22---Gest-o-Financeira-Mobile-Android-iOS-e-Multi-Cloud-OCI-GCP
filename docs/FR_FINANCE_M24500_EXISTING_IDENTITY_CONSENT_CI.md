# M24500 — Aceite versionado para identidade existente (laboratório CI)

**Frente exclusiva:** FR Finance AI Studio. **Não** usar FRcaixinha 2.2 independente. Este pacote não cria recursos OCI, não ativa webhooks/Pix e não aplica nenhuma migração no banco Termux `frcaixinha_aistudio_dev` (5433).

## Problema corrigido

O M24400 passou a exigir aceite afirmativo e hash SHA-256 exato no cadastro de **nova** identidade. A função existente `accept_existing_identity_ci`, entretanto, ainda aceitava somente `consent=True` e `document_id`; nem verificava o e-mail marcado `email_verified_at`. Isso não oferecia prova consistente de qual versão a identidade já cadastrada tinha visualizado.

## Alterações

- `accept_existing_identity_ci` agora recebe também `accepted_document_sha256` (padrão `None`) e mantém `consent=False` como padrão. Sem `consent is True` e digest hexadecimal de 64 caracteres: falha antes de abrir a transação.
- O digest apresentado precisa corresponder ao `sha256` do documento publicado `TENANT_MEMBERSHIP` e a versão `document_id` deve corresponder ao `required_document_id` do convite; nenhum documento alternativo pode servir.
- O usuário precisa estar `ACTIVE`, ter endereço de e-mail igual ao do convite e apresentar `email_verified_at IS NOT NULL`. Essa verificação é **sintética** no CI e não afirma que houve confirmação por provedor externo.
- Mantidos: token hash de uso único, expiração, convite entregue, revisão da permissão atual do convidante (Master ou Admin), tenant ativo, bloqueio de vínculo duplicado e aceites imutáveis. A criação do vínculo, eventual aceite e auditoria acontecem na mesma transação efêmera.
- O hash de evidência do novo aceite inclui a versão de documento explicitamente reconhecida e um valor aleatório; não é uma assinatura eletrônica de produção.
- Regressão no banco descartável atualiza fixtures de identidades sintéticas verificadas e testa falha por digest omitido, incorreto e `email_verified_at` ausente, antes de uma tentativa de sucesso. Os demais testes de expiração, revogação e Master continuam.
- A regressão `test_m24500_existing_identity_versioned_consent_ci.py` pode ser executada **sem PostgreSQL** no Termux.

## Limite contratual

Esta correção melhora a prova da regra de adesão nas cláusulas **6.1/6.1-A** e prepara parte de **3.1**, mas não habilita convite público, e-mail real, API autenticada de aceite, MFA/dupla aprovação, contratação SaaS e cobrança conciliada. As cláusulas continuam historicamente bloqueadas até a auditoria da implementação integrada. A matriz registra 147 cláusulas e 84 pendências prioritárias históricas; nenhum status pode ser promovido só por PASS de teste.

A execução de CI usa somente o banco `frcaixinha_ci` na porta 5432, identificado por `FRCAIXINHA_CI_ISOLATED=1`. A função permanece protegida por `_ci_only`. Nenhum CPF, senha, convite, dinheiro ou token real é usado nos testes.

## Conferência no Termux

```bash
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
python3 backend/scripts/aistudio_contract_gap_audit.py --json
python3 backend/scripts/aistudio_migration_inventory.py repo-check
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m24500_existing_identity_versioned_consent_ci.py \
  backend/tests/test_m24400_explicit_invite_acceptance_ci.py \
  backend/tests/test_m24000_contract_gap_147_ci.py
git rev-parse --short HEAD
git status --short
```

Não executar testes de integração PostgreSQL `*_lifecycle_ci.py` manualmente contra o banco local: só estão habilitados no CI descartável.
