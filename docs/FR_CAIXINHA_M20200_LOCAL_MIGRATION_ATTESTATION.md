# FR Caixinha AI Studio — M20200: reconciliação das migrações locais

## Evidência do Termux enviada pelo proprietário em 05/11/2026
- HEAD `ab3d44e5513397645dd43b5463389edef4ea187b` (M20100), branch `atualizacao-ai-studio-9b46a63187`.
- PostgreSQL exclusivo 18.6, porta `5433`, banco `frcaixinha_aistudio_dev`, PGDATA dedicado; **44 tabelas públicas**.
- O banco apresenta `member_lifecycle_requests` (028), `member_lifecycle_review_events` (029), índice de rodadas (030), `notification_inbox` (031) e oito tabelas sintéticas locais M034–M041.
- Antes, o proprietário apresentou backup age recuperável, aplicação transacional M028–M030, pós-verificação `M19300_LIFECYCLE_RLS=PASS: 36 tables` e `M19300_POST_VERIFY=PASS`.
- Depois, backup age recuperável, aplicação M034–M041 e pós-verificação `M20100_LOCAL_034_041_RLS_PASS: 44 tables`, `M20100_LOCAL_034_041_POST_VERIFY=PASS`, `M20100_REAL_PAYMENTS=BLOCKED`, `M20100_EXTERNAL_NOTIFICATIONS=BLOCKED`.
- Auditoria consolidada: `M19200_REGISTRY_HASHES=PASS`, `M19200_MIGRATION_SQL_COUNT=57`, `M19200_LOCAL_DB_IDENTITY=PASS`, `M19200_LOCAL_PUBLIC_TABLES=44`, `M19200_031_INBOX=RLS_PRESENT`, 028/029 objetos presentes, 030 índice presente, M20100 RLS PASS, API notificações local PASS e 401 sem login PASS.

## Reconciliar relatório de código e estado local
O `repo-check` somente atesta que o **fonte** possui os SQL e hashes esperados; não tem acesso ao banco Termux. Por isso as antigas mensagens `PREPARED_NOT_APPLIED` eram enganosas após a instalação local.
Agora o `repo-check` usa `VERSIONED_DB_VERIFICATION_REQUIRED`, e o modo `local-readonly` comprova o estado real da base: 44 tabelas, migração 031, 028–030, todas as oito 034–041 com RLS FORCE e ausência de privilégios em app/auth, além dos triggers de auditoria imutável.

## Fronteiras e próximo desenvolvimento
- Este checkpoint comprova **estruturas locais sintéticas**, não a execução dos SQL `staging_migrations/034–041` (proibidos em Termux) nem homologação de Mercado Pago/Pix real, banco, ledger, conciliação financeira ou notificações externas.
- As migrações 001–027 possuem estruturas-base no banco, mas não há prova individual do histórico de execução de cada arquivo. Não inventar atestado retroativo nem reaplicar DDL.
- Para novas alterações persistentes: migração local versionada + catálogo/hash + CI PG16/18 + backup age testado + execução no Termux + verificação local read-only + homologação no APK. Sem migração local, a feature fica pendente.
- Nenhum SQL nem banco foram modificados por este pacote M20200; altera apenas documentação, verificador e testes de auditoria.

## Protocolo local
`AI_STUDIO_APPROVED_SHA=<SHA_COMPLETO> python3 backend/scripts/aistudio_migration_inventory.py local-readonly`
Solicita senha em modo oculto e executa transação READ ONLY, sem recriar tabelas ou reiniciar a API.
