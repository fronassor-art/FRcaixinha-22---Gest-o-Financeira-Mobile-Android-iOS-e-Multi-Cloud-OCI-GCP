# FR Finance AI Studio — M24200: prova SQL antes de descartar credencial

## Objetivo e limite

A correção **não** libera Pix real nem substitui a homologação das 147 cláusulas. A matriz de 01/11 continua como fotografia histórica de 50 bloqueios e 34 itens sem verificação; o M24000 fornece ações de auditoria, não baixa contratual.

O M24100 continha um risco de arquitetura: `StagingProtectedCredentialStore.cancel()` verificava apenas o estado em memória e confiava na afirmação do chamador de que o registro PENDING já havia sido marcado como FAILED. Um chamador incorreto poderia tentar apagar a referência de uma revisão ativa.

O M24200 exige confirmação independente de leitura no PostgreSQL **antes da exclusão**: `mp_staging_oauth_failed_ref(tenant,actor,seller,revision)` só retorna a referência opaca de uma revisão com status **FAILED**, nunca ACTIVE, PENDING ou RETIRED. A função usa `SECURITY DEFINER`, concede execução somente ao worker `frcaixinha_mp_oauth_worker`, obriga o banco descartável `frcaixinha_staging`, confere tenant/ator/seller/revisão e recusa revisões ainda apontadas como ativas. O índice único de `credential_ref` impede duas revisões de compartilharem a mesma referência.

O adaptador Python `StagingSellerCASRegistry.failed_credential_ref` valida a identidade técnica de banco/PostgreSQL 18/porta, consulta apenas a função versionada e não expõe dados ao frontend. O armazenamento protegido M24100 exige que o retorno SQL seja exatamente igual à referência esperada, usando `compare_digest`, antes de invocar `EncryptedRevisionWriter.discard_confirmed_failed`. Erros, resposta ambígua, referência diferente ou resposta ausente **não** apagam o item; deixam revisão para reconciliação.

## Fronteiras operacionais

- SQL 048 e fixture CI 044: apenas PostgreSQL 18 **descartável no GitHub Actions**, jamais local Termux 5433. O catálogo cresce de 69 para 71 fontes SQL auditadas.
- Todo o fluxo continua **disabled by default**. O `EncryptedRevisionWriter` ainda é protocolo sem implementação OCI Vault/KMS: não existem credenciais reais no banco, aplicativo ou testes.
- Não existe emissor de consentimento real, reconciliação durável de referência órfã, webhook HTTPS real, Money Out comercialmente habilitado, conciliação bancária independente, fechamento ou rateio real.
- O resultado de 6/6 CI, se alcançado, comprova apenas os cenários automáticos, não aprovação financeira, regulatória ou contratual. PR #2 permanece DRAFT.

## Homologação local sem migração

```bash
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
python3 backend/scripts/aistudio_migration_inventory.py repo-check
python3 backend/scripts/aistudio_contract_gap_audit.py --json
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m24200_oauth_failed_ref_guard_ci.py \
  backend/tests/test_m24100_oauth_protected_store_port_ci.py \
  backend/tests/test_m24000_oauth_ambiguous_ack_ci.py \
  backend/tests/test_m24000_contract_gap_147_ci.py \
  backend/tests/test_m19200_migration_inventory_ci.py
git rev-parse --short HEAD
git status --short
```

Não rodar manualmente `backend/scripts/aistudio_staging_chain_ci.sh`, `backend/staging_migrations/048...`, `backend/ci_migrations/044...` nem nenhum `psql -f` no celular. Não fornecer token, senha ou dados de clientes nos resultados enviados ao chat.
