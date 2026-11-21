# FR Finance AI Studio — Macropacote M26200–M26300

## Baseline homologada

Checkpoint M26100 `dfc5f26` confirmado no Termux: **45 testes PASS**,
`M19200_MIGRATION_SQL_COUNT=82`, registro Git íntegro,
`PIX_REAL=DESATIVADO`. GitHub Actions run `42384793848`:
6/6 jobs, incluindo PostgreSQL descartável e APK debug.

O banco AI Studio de desenvolvimento permanece exclusivo em
PostgreSQL 18/Termux porta `5433`. Os objetos locais M028–M044 foram
atestados por consultas sem escrita. SQL de staging/CI **não** pode ser
aplicado ali.

## M26200 — Recebimento sintético assinado, sem webhook público

`backend/app/synthetic_mail_receipt.py` implementa somente o
**protocolo de laboratório CI_HMAC_V1**:
- assinatura HMAC-SHA256 em contexto distinto, timestamp e bytes JSON exatos;
- janela de até 300 s e assinatura comparada em tempo constante;
- limite de 2 KiB, UTF-8 estrito, JSON sem chaves duplicadas, UUIDs
  canônicos e eventos permitidos `CI_SMTP_ACCEPTED` / `CI_BOUNCE`;
- erros neutros sem logar o corpo, assinatura, token ou dados pessoais;
- resultado imutável sempre com
  `provider_delivery_confirmed=false`,
  `recipient_verified=false`, `consent_recorded=false`,
  `user_activated=false`.

**Não é um protocolo de assinatura oficial de qualquer provedor.**
No ambiente real será indispensável adaptar e validar a especificação
oficial do provedor contratado, o segredo recebido em vault, TLS,
replay ledger durável e revalidação de vínculo/escopo.

## M26300 — Audit trail no staging PostgreSQL descartável

A migration `staging_migrations/053_mail_receipt_audit_staging_only.sql`
cria uma tabela com RLS forçado e sem políticas públicas, mais uma função
de escrita estritamente restrita a `frcaixinha_mail_receipt_ci`.
Ela liga cada evento sintético ao evento da fila de convites e a um
`lease_id` previamente auditado pela M26100.

- `receipt_event_id` único e advisory lock impedem o reprocessamento
  conflitante; repetição exata resulta em `REPLAY`.
- Eventos `CI_SMTP_ACCEPTED` e `CI_BOUNCE` são registrados **somente
  como trilha CI**. Não há transição do convite para DELIVERED ou
  alteração do outbox.
- Constraints impedem registrar entrega, comprovação da titularidade,
  aceite, assinatura, conta ativa ou movimentação financeira.
- Dados persistidos: UUIDs, tipo restrito, SHA-256 do corpo sintético e
  metadados de auditoria. O corpo, endereço, token e segredo não são
  armazenados nessa nova tabela.
- Role CI não pode fazer SELECT, INSERT, UPDATE nem DELETE diretos.
- `ci_migrations/052_mail_receipt_idempotency_probe_ci_only.sql` executa
  os ensaios de replay, conflito, evento inexistente e falsa entrega.
- `test_m26300_signed_receipt_pg_ci.py` verifica um HMAC em Python e
  registra o evento correspondente no PostgreSQL com role segregada.

O catálogo agora tem **84 arquivos SQL**. Ambos os novos arquivos SQL
estão classificados como CI/staging com `do_not_apply_source_to_termux`.
Este pacote não prevê migrações na porta `5433`.

## Controles que ainda não estão concluídos em produção

1. Provedor real de e-mail e callbacks oficiais assinados.
2. Cofre/KMS, envelope criptografado, identidade e autorização do worker
   e armazenamento dos tokens de uso único.
3. Confirmar autenticamente a entrega e a posse do e-mail (não
   equivalentes ao ACK de SMTP) com verificação do destinatário.
4. Convite real e aceite transacional do contrato com a identidade
   verificada, MFA e aprovação dupla para administração.
5. Staging OCI com TLS, DNS, backup restaurável, auditar permissões RLS,
   e homologação com contas fictícias.
6. Pix real e empréstimos continuam desativados até habilitação do PSP,
   conciliação e teste integral do ciclo financeiro.

**Não há rota pública para recebimento de callback neste pacote.**
O estado do sistema não é alterado de modo a autorizar contas reais.

## Testes locais seguros

Após CI PASS, sincronizar a branch e executar:

```bash
(
set -e
cd "$HOME/frcaixinha-aistudio-mobile" || exit 1
test "$(git branch --show-current)" = "atualizacao-ai-studio-9b46a63187"
test -z "$(git status --porcelain --untracked-files=no)"
git pull --ff-only origin atualizacao-ai-studio-9b46a63187
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_m26200_signed_receipt_ci.py \
  backend/tests/test_m26300_mail_receipt_audit_policy_ci.py \
  backend/tests/test_m26100_dispatch_lease_policy_ci.py \
  backend/tests/test_m26000_recovery_staging_policy_ci.py \
  backend/tests/test_m25900_staging_outbox_contract_ci.py \
  backend/tests/test_security_guards.py
python3 backend/scripts/aistudio_migration_inventory.py repo-check
bash -n backend/scripts/aistudio_staging_chain_ci.sh
git rev-parse --short HEAD
git status --short
echo "FR_FINANCE_M26300_TERMUX=PASS"
echo "PIX_REAL=DESATIVADO"
)
```

O teste `test_m26300_signed_receipt_pg_ci.py` é executado **somente na CI**
contra PostgreSQL descartável; não é destinado ao Termux.
