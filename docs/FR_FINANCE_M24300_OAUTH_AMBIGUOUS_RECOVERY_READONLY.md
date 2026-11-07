# M24300 — Recuperação de revisões OAuth após resposta ambígua

**Projeto:** FR Finance AI Studio (não usar o repositório, banco ou ambiente da frente FRcaixinha 2.2).

## Problema específico

Depois de uma tentativa de registrar ou ativar conexão Mercado Pago, uma desconexão pode deixar o processo sem saber se o PostgreSQL efetivou a operação. A solução não é repetir cegamente a operação nem apagar a referência criptografada. É conferir o estado de **uma revisão exata** no banco, mantendo tokens protegidos e sem autorizar pagamentos.

## Implementação

- `backend/staging_migrations/049_mp_oauth_revision_state_staging_only.sql`: função SQL `mp_staging_oauth_revision_state`. Só o worker `frcaixinha_mp_oauth_worker` consegue consultar, exclusivamente no banco `frcaixinha_staging` do ambiente isolado. Recebe tenant/ator/seller/revisão/referência opaca, compara todos e retorna somente `PENDING`, `ACTIVE`, `FAILED`, `RETIRED` ou `NULL`. **Não expõe credenciais, hashes ou referências de terceiros.**
- `backend/ci_migrations/045_oauth_revision_state_worker_probe_ci_only.sql`: ensaios PostgreSQL 18 descartáveis com revisão ACTIVE, FAILED, PENDING, tenant/ator trocado, referência divergente e revisão inexistente. Não confere ao worker SELECT direto nas tabelas.
- `StagingSellerCASRegistry.revision_status`: adaptador Python com validação de UUID, formato da referência/revisão, banco, role, versão PG18 e **porta 5433 proibida**. Todas as exceções são tratadas como ausência de evidência.
- `StagingOAuthRecoveryInspector.inspect`: mecanismo somente leitura, desativado por padrão, que devolve uma recomendação não executável. `PENDING` exige reconciliação; `FAILED` exige a prova independente M24200 antes de qualquer limpeza; `RETIRED` exige política de retenção; `ACTIVE` **não** significa conta autorizada, pois consentimento e papel administrativo podem ter sido revogados. Casos incertos retêm a referência para revisão humana.
- Testes sintéticos verificam todas essas condições e comprovam ausência de exclusão, reativação, operação financeira ou chamadas Oracle.

## Garantias e limites

Nenhuma máquina virtual OCI foi criada; nenhum pagamento ou Pix real foi habilitado; nenhuma migração foi aplicada no Termux. A cadeia staging SQL só roda no CI descartável do GitHub Actions com guardas de ambiente. O catálogo auditado passa de **71 a 73 fontes SQL**.

**A recuperação ainda é preparatória**: não há store criptografado efetivo nem registro durável de falhas em armazenamento, fila de reconciliação, política de retenção, auditoria operacional ou infraestrutura HTTPS. Também faltam consentimento legítimo e integração Mercado Pago autorizada. O M24300 não baixa automaticamente nenhuma das 50 cláusulas historicamente bloqueadas nem as 34 não verificadas.

## Comandos seguros no Termux

```bash
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
python3 backend/scripts/aistudio_migration_inventory.py repo-check
python3 backend/scripts/aistudio_contract_gap_audit.py --json
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m24300_oauth_recovery_readonly_ci.py \
  backend/tests/test_m24200_oauth_failed_ref_guard_ci.py \
  backend/tests/test_m24100_oauth_protected_store_port_ci.py \
  backend/tests/test_m24000_contract_gap_147_ci.py \
  backend/tests/test_m19200_migration_inventory_ci.py
git rev-parse --short HEAD
git status --short
```

Os comandos só auditam arquivos e executam testes com fakes; não executam SQL no PostgreSQL local.
