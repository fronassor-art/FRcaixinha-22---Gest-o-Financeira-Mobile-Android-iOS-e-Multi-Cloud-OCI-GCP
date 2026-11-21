# FR Finance — M40020: colisões concorrentes e revogação apenas proposta

**Data:** 15/11/2026. **Branch:** `atualizacao-ai-studio-9b46a63187`. **PR #2:** Draft.

**Checkpoint local recebido:** M40010 sincronizado no Termux em `454678a`, por *fast-forward*. Não houve migração, acesso de escrita ao PostgreSQL original nem reinício do FastAPI.

## Objetivo do experimento

O M40010 confirmou registros sintéticos persistidos entre conexões do **PostgreSQL 18 efêmero do GitHub Actions**. O M40020 acrescenta dois cenários de **concorrência real entre processos psql simultâneos**, dentro de uma única execução CI, para testar conflitos de duplicação e uma *proposta* de revogação.

**Este pacote não concede, revoga ou confirma direitos de revisão reais.** Todas as identidades são papéis PostgreSQL `NOLOGIN` simulados via `SET ROLE`. Os registros são dados sintéticos do banco descartável, sem assinatura de pessoa, consentimento, pagamento, provedor, aplicativo ou lançamentos de saldo.

## Cenários de concorrência

### 1 — Duas tentativas no mesmo lugar de revisão

- Um processo assume o papel sintético `m40010_a_a`, grava um recibo na posição 1 do pacote de teste e mantém a transação aberta por três segundos.
- Enquanto essa transação possui um lock de linha, um segundo processo `psql`, igualmente associado ao papel A, tenta registrar outro recibo para a **mesma posição/revisor**, reutilizando nonce e chave de idempotência.
- O trigger `m40020_ci.lock_proposed_grant()` usa `SELECT ... FOR UPDATE` no estado de designação proposto. O processo concorrente deve aguardar o lock, depois ser rejeitado por restrição única nomeada M40010.
- A auditoria final, em outra conexão, exige **exatamente um** recibo, sem alteração do original. Uma rejeição por motivo inesperado reprova a CI.

### 2 — Proposta de revogação competindo com novo recibo

- Um processo de administração sintética atualiza a linha de estado de designação para `stopped_for_ci=true` e grava `REVOCATION_PROPOSED` na tabela de eventos também sintéticos, **na mesma transação**.
- O processo mantém a trava por três segundos; um outro `psql` tenta escrever um recibo com papel `m40010_a_b`, associado à posição 2 do mesmo pacote.
- A checagem transacional do trigger deve aguardar a conclusão da primeira transação e rejeitar a segunda com a mensagem específica `M40020_PROPOSED_STOP_BLOCKS_FUTURE_CI_RECEIPT`.
- A auditoria exige um único evento proposto, um único recibo total, nenhum recibo posterior para posição 2, bloqueio de reativação e impossibilidade de excluir o evento.

A paralelização da CI só é aceita quando o processo titular da trava ainda está em execução após a emissão do marcador de lock. Uma execução puramente sequencial não passa por esse teste de sobreposição.

## Segurança dos dados de teste

A schema experimental `m40020_ci` contém `proposed_grant_state` e `proposed_stop_events`, com `ENABLE/FORCE ROW LEVEL SECURITY`, leitura por `current_user`, eventos imutáveis, transição de estado de parada estritamente unidirecional e restrição de vínculo ao papel original M40010.

O trigger utiliza `SECURITY DEFINER` **somente no banco sintético de CI**, para conferir a trava com permissões isoladas. Sua existência nesse ensaio **não** prova segurança de uma futura implementação de produção; uma função real precisaria de revisão específica de privilégios, autenticação, políticas RLS, auditoria, concorrência e autorização.

Todos os eventos continuam `PROPOSED_ONLY_NOT_EFFECTIVE`, com `signed_human_consent=false`, `authentic_revocation=false`, `approved=false` e `payments_enabled=false`. Na proposta, os campos `reviewer_identity_authenticated`, `mandate_ratified` e `effective_revocation_verified` são sempre falsos. Os recibos M40010 continuam sem autenticação humana, aprovação, reconciliação bancária, posting ou saque.

O flag `stopped_for_ci` indica somente que, **no banco de ensaio**, uma proposta bloqueia futuras inserções para exercitar a regra técnica. Ele não é uma revogação real nem substitui política jurídica formal ou o mecanismo de revogação de sessões reais.

## Alcance e pendências

São testados apenas o patrimônio próprio de administrador (`TENANT_ADMIN_OWN`) e os papéis sintéticos de sua caixinha A, vinculados ao ensaio M40010; os pacotes independentes do Master e da caixinha B permanecem na base de CI sem movimentação. Os três patrimônios seguem separados, com `TENANT_COLLECTIVE` fora de autorização por este pacote.

Continuam abertos: política de revisão e revogação juridicamente ratificada; assinatura individual e consentimento; autenticação de usuários por sessão vinculada ao servidor em requisições independentes; verificação persistente de titularidade; trilha de auditoria durável em banco original **após autorização expressa de migração**; expiração e revogação de papéis reais; conciliação e prova do provedor; licenças, controle fiscal e fechamento do rateio 15%/85%.

## Arquivos e validação

- `backend/tests/sql/m40020_disposable_guard.psql`: dupla barreira de banco/porta/flags CI;
- `backend/tests/sql/m40020_disposable_lock_init_pg18_ci.sql`: schema e trigger de lock;
- `backend/tests/sql/m40020_disposable_race_first_pg18_ci.sql` e `m40020_disposable_race_duplicate_pg18_ci.sql`: duas conexões em conflito;
- `backend/tests/sql/m40020_disposable_stop_proposal_pg18_ci.sql` e `m40020_disposable_stopped_writer_pg18_ci.sql`: proposta versus gravação em curso;
- `backend/tests/sql/m40020_disposable_final_audit_pg18_ci.sql`: contagens, RLS, immutabilidade e flags negativas;
- `backend/tests/test_m40020_concurrency_source_ci.py`: contrato estático de segurança;
- `.github/workflows/frfinance-m40020-concurrent-stop-ci.yml`: orquestração das provas no PostgreSQL 18 descartável.

O Caderno Mestre e o Contrato Técnico protegidos no M39100 não foram editados; esta documentação é um aditivo.

`M40020_ORIGINAL_DB_WRITES=NONE`  
`M40020_LOCAL_MIGRATIONS=NONE`  
`M40020_TERMUX_ACCESS=NONE`  
`M40020_FASTAPI_RESTART=NONE`  
`M40020_REAL_REVOCATION=NOT_ATTESTED`  
`M40020_INDEPENDENT_HUMAN_AUTH=NOT_ATTESTED`  
`PIX_REAL=OFF`  
`PAGAMENTOS_REAIS=OFF`  
`ATIVACAO_REAL=OFF`  
`PRODUCTION=BLOCKED`
