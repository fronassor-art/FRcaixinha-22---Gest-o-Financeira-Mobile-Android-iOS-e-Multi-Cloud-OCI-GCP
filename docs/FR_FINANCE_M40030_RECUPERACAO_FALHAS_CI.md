# FR Finance — M40030: falha antes do COMMIT e recuperação sem duplicações

**Data:** 15/11/2026. **PR #2:** Draft. **Branch:** `atualizacao-ai-studio-9b46a63187`. **Último checkpoint local recebido:** M40020 `ffd8643` sincronizado no Termux, com `MIGRATIONS=NONE`, `LOCAL_DB_WRITES=NONE`, `FASTAPI_RESTART=NONE` e produção bloqueada.

## Finalidade

Os experimentos M40010–M40020 confirmaram, exclusivamente em PostgreSQL 18 descartável, leitura segregada e rejeição de colisões em duas conexões simultâneas. O M40030 acrescenta **falhas de processo antes de COMMIT e recuperação em conexões independentes**, sem acesso ao PostgreSQL original.

Os papéis de banco `NOLOGIN` são sintéticos, assumidos em CI por `SET ROLE`, e não autenticam pessoas, documentos ou consentimentos. **Nenhuma designação ou revogação ganha efeito jurídico ou financeiro.** O módulo não é migração da aplicação e não integra a API existente.

## Ensaio 1: recibo não confirmado após falha de processo

1. O job cria `frcaixinha_ci` em container PostgreSQL 18, com guardas de base, porta, flags CI e executor GitHub.
2. Inicializa os papéis sintéticos e as restrições M40010/M40020; adiciona um segundo documento à caixinha A para testar repetição entre documentos.
3. Um processo `psql` abre transação e grava um recibo sintético, mantendo o lock e **sem confirmar a transação**.
4. O workflow comprova o marcador emitido pelo processo ainda ativo, envia `SIGKILL` somente a esse processo **do runner descartável**, verifica código de saída 137 e proíbe que o `COMMIT` tenha sido atingido.
5. Outra conexão exige que o recibo não confirmado esteja ausente e repete **exatamente os mesmos identificadores** de registro, sessão, nonce e idempotência. O retry é confirmado uma única vez.

A prova valida rollback de transação não confirmada e capacidade de retentar em CI. Não simula crash físico do host, perda de volume, failover, replicação, corrupção de WAL ou exatamente uma entrega de mensagens externas.

## Ensaio 2: repetição depois de COMMIT

Usando o segundo documento da mesma caixinha A, o ensaio tenta repetir o **nonce já confirmado** e depois a **chave de idempotência já confirmada**. Cada tentativa exige falha de `UNIQUE` com o nome específico esperado, `m40010_unique_nonce` ou `m40010_unique_idem`. Uma falha por outro motivo não vale como aprovação do teste.

Assim se distingue retentativa **antes da confirmação** (permitida se o banco efetuou rollback) de repetição **depois da confirmação** (rejeitada). Isso é restrição de dados sintéticos, não prova de liquidação financeira ou entrega única de operação real.

## Ensaio 3: proposta de revogação interrompida

Outro `psql` marca o revisor B como `stopped_for_ci=true` e insere `REVOCATION_PROPOSED` na mesma transação. O processo sofre `SIGKILL` **antes do COMMIT**. Uma nova conexão comprova que nenhum dos dois registros foi parcialmente efetivado, recupera a mesma proposta sintética e a confirma no banco descartável. Uma tentativa subsequente de recibo do revisor B deve ser rejeitada pela checagem transacional M40020.

O estado `stopped_for_ci` significa **apenas bloqueio técnico de teste**. `authentic_revocation=false`, `mandate_ratified=false`, `human_identity_verified=false`, `approved=false`, `journal_posted=false`, `payout_enabled=false` e saldo disponível nulo continuam permanentes. Revogação, assinatura humana e pagamento reais não foram executados.

## Auditoria final

Uma conexão separada confirma exatamente um recibo da caixinha de ensaio, zero registros indevidos no segundo documento, um evento de proposta de revogação e RLS distinguindo os papéis A e B. Nega qualquer marcador de identidade humana real, política ratificada, assinatura, conciliação com provedor, lançamento contábil, saldo disponível ou pagamento habilitado.

## Segurança operacional

- Identidade descartável: `frcaixinha_ci`, porta `5432`, PostgreSQL 18, `session_user=postgres` e flags `CI_M40010_DISPOSABLE`, `CI_M40020_DISPOSABLE`, `CI_M40030_DISPOSABLE` com configurações `DISPOSABLE_ONLY`.
- O `SIGKILL` atinge apenas o `psql` iniciado pela **própria CI no runner efêmero**, nunca PID do Android, Termux, Debian ou FastAPI local.
- Não há conexões com o PostgreSQL FR Finance original (porta 5433), nem com o banco FR Caixinha 2.2. Não rodar scripts de ensaio nos ambientes originais.
- Não criar migração local, endpoint, rota de aprovação, aplicação Android ou integração com Mercado Pago/OCI.
- O Caderno Mestre e o Contrato Técnico SHA-locked M39100 permanecem intactos (330 requisitos e 2.310 etapas historicamente catalogadas).

## Entregáveis

- `backend/tests/sql/m40030_disposable_guard.psql`
- `backend/tests/sql/m40030_disposable_prepare_pg18_ci.sql`
- `backend/tests/sql/m40030_disposable_receipt_crash_pg18_ci.sql`
- `backend/tests/sql/m40030_disposable_receipt_recover_pg18_ci.sql`
- `backend/tests/sql/m40030_disposable_replay_after_commit_pg18_ci.sql`
- `backend/tests/sql/m40030_disposable_stop_crash_pg18_ci.sql`
- `backend/tests/sql/m40030_disposable_stop_recover_pg18_ci.sql`
- `backend/tests/sql/m40030_disposable_final_audit_pg18_ci.sql`
- `backend/tests/test_m40030_recovery_source_ci.py`
- `.github/workflows/frfinance-m40030-crash-recovery-ci.yml`

`M40030_TERMUX_ACCESS=NONE`; `M40030_LOCAL_MIGRATIONS=NONE`; `M40030_ORIGINAL_DB_WRITES=NONE`; `M40030_FASTAPI_RESTART=NONE`; `M40030_REAL_REVOCATION=NOT_ATTESTED`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
