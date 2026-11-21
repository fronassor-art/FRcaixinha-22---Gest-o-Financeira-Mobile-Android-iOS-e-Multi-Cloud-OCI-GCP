# FR Finance M40010 — Auditoria sintética entre sessões PostgreSQL descartáveis

**Data:** 15/11/2026. **Branch:** `atualizacao-ai-studio-9b46a63187`, PR #2 Draft.

Checkpoint anterior recebido: **M40000** sincronizado no Termux no commit `d5eb5af`, sem migração, escrita em banco, reinício de API ou ativação real.

## Evidência desenvolvida

O M40000 testou unicidade, append-only e RLS em uma transação encerrada com `ROLLBACK`. O M40010 expande os ensaios para mostrar **persistência apenas entre processos de CI**, dentro de um serviço **PostgreSQL 18 efêmero do GitHub Actions**. A persistência do ensaio termina quando o container é destruído. Não existe implantação ou migração nos bancos originais.

A sequência é executada com processos `psql` separados:

1. Em `frcaixinha_ci`/5432, a configuração de teste cria a schema isolada `m40010_ci`, quatro pacotes sintéticos, seis papéis revisores `NOLOGIN` e oito vínculos de revisão por pacotes. Executa `COMMIT` **somente no banco descartável**.
2. Uma nova conexão grava uma declaração por caixa (Master, administrador A e administrador B) assumindo papéis simulados `m40010_m_a`, `m40010_a_a` e `m40010_b_a`.
3. Outra nova conexão, separada da anterior, grava a segunda declaração por caixa usando papéis simulados distintos.
4. Uma quarta conexão observa os **seis registros sintéticos persistidos** e tenta fraudar papel, atravessar tenant, reutilizar nonce/chave de idempotência e elevar permissão.

## Restrições demonstradas

- Registro do autor associado à identidade **do papel PostgreSQL `current_user`**, não a uma variável de papel vinda da tela.
- Vínculo referencial composto do documento, domínio financeiro, política proposta, papel atribuído, identificador do revisor e posição 1 ou 2.
- Somente dois lugares possíveis por pacote, impostos por `slot IN (1,2)` e `UNIQUE(packet_id,slot)`.
- Índices únicos de revisor, sessão declarada, nonce e idempotência.
- Separação por RLS com `ENABLE/FORCE ROW LEVEL SECURITY` nas três tabelas.
- Papel revisor com `SELECT` restrito e `INSERT` somente em colunas de recibos propostas, sem autorização de alterar registros anteriores ou aprovar pagamentos.
- `BEFORE UPDATE OR DELETE` bloqueia alteração/exclusão em tabelas do ensaio.
- Campo de horário de inclusão gerado pelo servidor PostgreSQL do teste.
- Testes negativos verificam de forma específica os nomes das restrições de nonce e idempotência; as falhas são capturadas sem corromper os dados anteriores.

O caixa da empresa (`PLATFORM_MASTER`) é separado do patrimônio próprio do administrador (`TENANT_ADMIN_OWN`). São usados dois administradores de caixinhas distintas, A e B; o patrimônio coletivo (`TENANT_COLLECTIVE`) continua **fora da política de aprovação**. Nenhuma regra de rateio 15%/85% é executada.

## Advertências de segurança

Os papéis `NOLOGIN` são **representações simuladas** assumidas por um superusuário dentro do serviço CI. Não correspondem a pessoas reais, sessões de aplicativo, assinaturas criptográficas ou consentimento jurídico. Nem a persistência entre conexões nem o banco de teste autenticam um ato humano.

O campo `claimed_session_id` é um identificador sintético e não um token validado pelo servidor. A designação de revisores do Master e dos administradores continua **não ratificada**. Os requisitos de verificação de token-hash por requisição, segregação de deveres, autorização de titularidade, política contratual, revogação persistente e aprovação em duas requisições reais continuam em aberto.

Todas as tabelas obrigam `policy_ratified=false`, `human_identity_verified=false`, `reviewer_mandate_ratified=false`, `document_authenticated=false`, `approved=false`, `provider_reconciled=false`, `journal_posted=false`, `payout_enabled=false` e saldo disponível nulo quando o campo existe. Nada é conciliado, lançado, transferido ou liberado.

O guard compartilhado só permite prosseguir com variável psql `CI_M40010_DISPOSABLE`, database `frcaixinha_ci`, porta 5432, `session_user=postgres`, flag de sessão `frfinance.m40010_ci=DISPOSABLE_ONLY`, e o workflow exige `GITHUB_ACTIONS=true`. Esses guardas são de prevenção de erro operacional, **não** substituem controle real de identidade. Os scripts de teste não devem ser executados no Termux nem Debian.

## Entregáveis

- `backend/tests/sql/m40010_disposable_guard.psql`
- `backend/tests/sql/m40010_disposable_init_pg18_ci.sql`
- `backend/tests/sql/m40010_disposable_writer_first_pg18_ci.sql`
- `backend/tests/sql/m40010_disposable_writer_second_pg18_ci.sql`
- `backend/tests/sql/m40010_disposable_audit_pg18_ci.sql`
- `backend/tests/test_m40010_disposable_audit_source_ci.py`
- `.github/workflows/frfinance-m40010-ephemeral-audit-ci.yml`

O Caderno Mestre e o Contrato Técnico M39100 permanecem SHA-locked; este registro é **aditivo**.

`M40010_ORIGINAL_DB_ACCESS=NONE`  
`M40010_MIGRATIONS_LOCAL=NONE`  
`M40010_FASTAPI_RESTART=NONE`  
`M40010_REAL_HUMAN_SIGNATURES=NONE`  
`PIX_REAL=OFF`  
`PAGAMENTOS_REAIS=OFF`  
`ATIVACAO_REAL=OFF`  
`PRODUCTION=BLOCKED`
