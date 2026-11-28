# FR Finance M40800 — Supermacropacote de gates de autenticação, migração e deploy seguro

**Base auditada:** M40770 `a60577b` com CI geral 7/7 PASS e M40760 8/8 PASS. **PR #2 permanece Draft.**

## 1. Borda de credencial financeira antes de abrir a pool

`backend/app/database.py` passa a chamar `require_financial_dsn_shape` **antes de abrir qualquer conexão** asyncpg. No ambiente Termux AI Studio identificado por `FRCAIXINHA_TERMUX_LOCAL_API=1`, recusa papéis de proprietário, superusuário, banco errado, host remoto, porta divergente e parâmetros de DSN inesperados; perfis opcionais Auth e Verifier, quando fornecidos, devem permanecer segregados. Em produção, a configuração do pool também deve passar pelo gate `require_production_auth` já existente.

**Limite:** sintaxe DSN é apenas declaração, não atesta a identidade de servidor nem confere ACL, RLS, dados, processo ou segredos reais. A flag local ausente mantém o estado `NONPRODUCTION_UNATTESTED`; um atacante com código arbitrário pode subverter controle em Python. **M40570 — GUC spoofing — segue NO-GO**.

## 2. Classificador de migração sem acesso PostgreSQL

`backend/scripts/frfinance_m40800_migration_delta_readonly.py` lê SOMENTE metadados Git em Termux nativo; verifica HEAD fixado, branch, origin, limpeza, ancestralidade e caminhos de SQL/migrações. Se houve qualquer alteração no catálogo SQL, arquivos `*.sql` ou instaladores, sai **bloqueado** para revisão independente. Se nenhuma, retorna `M40800_MIGRATION_REVIEW=NO_SCHEMA_DELTA_IN_SYNC_RANGE`, isto é, **não é necessária migração para a sincronização daquele intervalo**.

Nenhum script ou autorização para aplicar DDL/DML foi criado. Não executar `aistudio_local_migration.sh`: é instalador inicial de banco vazio, não serve para o PostgreSQL original com dados. É proibido aplicar migrations anteriores/duplicadas reflexivamente. Antes de QUALQUER migração real futura: pré-voo de identidade na porta 5433, backup consistente criptografado e restore verificado, hash e diff do SQL, aprovação expressa do plano reversível, rollback e evidências pós-migração. O pedido genérico de continuidade não substitui esses gates.

## 3. Regressão e escopo

A CI M40800 roda pytest **offline**, sem banco, provedor, serviços, credenciais ou aparelho. A CI geral AI Studio também passa a ser acionada por `push` sobre os novos arquivos deste pacote, garantindo validação frontend/API/RLS descartável/APK após commit.

## 4. Pendências que continuam NÃO resolvidas

- **M40730 SQL signer:** login SQL emissor vazado permite tickets sem Ed25519, apesar da separação por ACL. **NO-GO** até isolamento de assinatura real, privilégios efetivos, custódia e teste adversarial independente.
- **M40570 / GUC:** papel SQL app com execução arbitrária falsifica `app.current_*`. **NO-GO** até redesenho da fronteira de sessão SQL e migração controlada.
- **Runtime Android:** HEAD Git do Termux não prova código FastAPI carregado; reinício depende de autorização/owner atestado.
- **APK físico M40510:** correção de topo após teclado/logout aguarda reteste no dispositivo.
- **OCI/Vault/TLS/MP/jurídico:** falta evidência real homologada, revisão regulatória e aceite antes de dinheiro.
- **M40740–M40760:** tráfego real negado nos três adaptadores revisados; isso não é firewall global.

`MIGRATIONS=NONE`; `DB_CONNECTIONS=NONE` nos testes e classificador; `SERVICE_RESTARTS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`. **Não aplicar nenhuma migração SQL no banco local nem reiniciar serviços por causa deste pacote.**
