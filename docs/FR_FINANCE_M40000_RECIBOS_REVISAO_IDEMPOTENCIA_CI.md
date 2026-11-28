# FR Finance — M40000: recibos sintéticos de revisão e idempotência transacional

**Data:** 15/11/2026. **Branch:** `atualizacao-ai-studio-9b46a63187`, PR #2 Draft. **Checkpoint local recebido:** M39990 `579099f` sincronizado por fast-forward no Termux; sem migrações, escritas ou reinícios.

## Objetivo e escopo comprovável

M39950–M39990 estabeleceram pré-validações de forma de comprovantes, identidades declaradas, políticas ainda não ratificadas e eventos de mandato propostos. M40000 demonstra **exclusivamente no PostgreSQL 18 descartável do GitHub Actions** como um sistema futuro pode restringir duplicações e segregar a leitura de recibos documentais.

**Não registra, autentica ou assina revisões de pessoas reais.** Não há persistência no PostgreSQL original, autorização financeira, consulta a Mercado Pago, posting, saque, notificação ou endpoint FastAPI. O ensaio cria tabelas e papéis dentro de uma transação de teste e termina em `ROLLBACK`.

## Evidência técnica entregue

`backend/tests/sql/m40000_disposable_review_receipts_pg18_ci.sql`

O script somente prossegue se receber simultaneamente:
- variável psql explícita `CI_M40000_DISPOSABLE`;
- banco `frcaixinha_ci`, porta 5432, `session_user=postgres`;
- parâmetro de CI `frfinance.m40000_ci=DISPOSABLE_ONLY`.

A validação ocorre **antes** do `BEGIN`. Nenhuma dessas variáveis deve ser configurada ou utilizada no Termux/Debian original.

Duas tabelas na schema `m40000_ci`:
1. `review_packets` relaciona caixa, referência de lançamento, hash documental, rascunho da política e identificador alegado do preparador. Não aceita caixa coletivo ou misturas entre Master e tenant.
2. `review_receipts` relaciona exatamente o mesmo pacote por chave estrangeira composta e identificadores alegados de revisor, sessão, nonce e idempotência. Aceita exclusivamente `DOCUMENTARY_CHECK_PROPOSED` e `REQUEST_MORE_EVIDENCE`.

Controles reais do **banco de ensaio**, mas sem valor de autorização real:
- `UNIQUE(packet_id,reviewer_id)` — uma alegação por pessoa no mesmo pacote;
- `UNIQUE(packet_id,session_id)` — não reutilizar sessão dentro do pacote;
- `UNIQUE(scope,cashbox_key,nonce)` e `UNIQUE(scope,cashbox_key,idempotency_key)` — não reutilizar nonce ou chave de idempotência na mesma caixinha;
- trigger `guard_two_claims()` obtém `FOR UPDATE` no pacote pai e verifica limite de dois registros, rejeitando autodeclaração do preparador;
- triggers imutáveis bloqueiam `UPDATE` e `DELETE` ordinários;
- `ENABLE` e `FORCE ROW LEVEL SECURITY` protegem ambas as tabelas no papel sintético `m40000_ci_reader`, que possui somente `SELECT`;
- três caixas de amostra (Master SaaS, administrador A, administrador B), leitores isolados e membro sem acesso;
- testes de conflito exercitam limite de duas declarações, autorrevisão, sessão duplicada, revisor duplicado, nonce, idempotência, referência de outro tenant, aprovação falsa, alteração e exclusão.

Nenhum usuário da aplicação recebe direito de escrever nessas tabelas, e elas **não existirão** no FR Finance original depois do ensaio. O comando `ROLLBACK` desfaz tabelas, triggers, papel e registros no PostgreSQL de CI. As evidências de sucesso serão os logs de teste do workflow, não um histórico persistente implantado.

## Estado de segurança inalterável

Os campos do pacote contábil sempre permanecem com `policy_approved=false`, `provider_reconciled=false`, `journal_posted=false`, `payout_authorized=false` e `available_balance_cents=NULL`.

Os recibos sempre mantêm `session_authenticated=false`, `reviewer_mandate_verified=false`, `document_authenticated=false`, `approval_verified=false`, `journal_posted=false`, `payout_enabled=false` e `available_balance_cents=NULL`.

Mesmo que duas linhas existam, **não** provam duas pessoas, sessões realmente autenticadas, poderes ratificados, assinaturas independentes, liquidação, saldo, despesa válida, rateio anual 15%/85% nem autorização para movimentar patrimônio.

## Limitações de produção explicitamente pendentes

O teste `m40000_ci_reader` usa variáveis de sessão sintéticas de papel/tenant; em produção essas informações teriam que vir do servidor, usando token hash autenticado e vínculo atualizado com o tenant, não de parâmetros controlados pelo cliente.

A serialização com `FOR UPDATE` e os índices `UNIQUE` demonstram restrições de dados e protocolo transacional numa instância de CI, **não** um teste de dois servidores concorrentes, alta disponibilidade, comportamento de rede, repetição de mensagens, fraude em assinatura ou durabilidade após reboot.

Para aplicação real será necessário: política de designação/revogação ratificada, consentimentos assinados individualmente, fonte documental autenticada, política de permissões Master/administrador/coletivo, idempotência durável em migração formalmente aprovada, RLS server-side, captura independente de sessões em requisições distintas, backup do FR Finance 5433, auditoria de concorrência e verificação de provedores. Não transportar as tabelas de ensaio ao banco original por mera sincronização de código.

## Arquivos entregues

- Banco descartável: `backend/tests/sql/m40000_disposable_review_receipts_pg18_ci.sql`
- Validação estática: `backend/tests/test_m40000_review_receipts_source_ci.py`
- Workflow: `.github/workflows/frfinance-m40000-review-receipts-disposable-ci.yml`

O Caderno Mestre e o Contrato Técnico M39100 continuam com hashes imutáveis e catálogo de 330 requisitos / 2310 etapas. Este arquivo é um aditivo.

`M40000_TERMUX_ACCESS=NONE`  
`M40000_ORIGINAL_DB_ACCESS=NONE`  
`M40000_MIGRATIONS_LOCAL=NONE`  
`M40000_FASTAPI_RESTART=NONE`  
`PIX_REAL=OFF`  
`PAGAMENTOS_REAIS=OFF`  
`ATIVACAO_REAL=OFF`  
`PRODUCAO=BLOCKED`
