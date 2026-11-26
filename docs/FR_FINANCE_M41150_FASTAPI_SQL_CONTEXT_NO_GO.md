# FR Finance M41150 — FastAPI e capability SQL em rota somente leitura (NO-GO)

## Escopo e rastreabilidade

Rastreia CP26-0061 / CTM-07 e CP26-0062 / CTM-08. A matriz conserva os 330 IDs e as 2.310 etapas; nenhum item, gate ou aceite é promovido.

O endpoint existente GET /api/v1/tenants/{tenant_id}/ledger/accounts/directory agora aceita uma dependência de capability opcional. Com provedor ausente, conserva a dependência anterior, ainda submetida ao M40840. Com provedor presente, a dependência valida a sessão verificada e o papel Admin, exige o tenant da rota igual ao tenant da sessão, solicita ticket de uso único e o vincula a uma capability opaca. A capability é instalada somente dentro de transação PostgreSQL READ ONLY. A RLS da tabela decide as linhas; os GUCs legados de usuário, papel e tenant não são usados nesse caminho.

## Evidência executável

Workflow dedicado FR Finance M41150 executa o roteador real de ledger em uma aplicação ASGI de teste, contra PostgreSQL 18 descartável. A fixture cria public.ledger_accounts e sua política RLS somente no banco efêmero, aproveitando o schema sintético M41050–M41140. A prova verifica isolamento de tenant, negação de GUCs legados forjados, papel e tenant adulterados via HTTP, sessão não verificada, ticket reutilizado e capability revogada. A resposta é somente metadado da conta, sem saldo ou autorização de fechamento.

O teste substitui get_current_session por identidades sintéticas e injeta no app.state um provedor local, com chave e funções da fixture. Portanto ele atesta a rota FastAPI e o caminho SQL/RLS em CI, mas **não** autenticação do bearer no runtime oficial, custódia independente, schema PostgreSQL autoritativo, origem do processo, runtime Termux/OCI ou homologação em staging.

## Limites e próximos bloqueios

O provedor não é configurado pelo app oficial. A função pública de emissão/ligação e seu privilégio mínimo ainda dependem de desenho, revisão de ACL, custódia externa de chaves e teste adversarial independente. O caminho legado continua em desenvolvimento quando o provedor não existe. M40840 NO-GO, M40930 HTTP 503 para mutações Master e Issue #5 permanecem. Este pacote não remove gates, não declara a autorização SQL efetiva concluída e não habilita escrita financeira.

CP26-0061=PENDING_INDEPENDENT_EVIDENCE
CP26-0062=PENDING_INDEPENDENT_EVIDENCE
M41150_AUTHENTICATION=OVERRIDDEN_SYNTHETIC
M41150_PROVIDER=CUSTODY_NOT_CONFIGURED
M41150_ROUTE=LEDGER_DIRECTORY_READ_ONLY
M41150_SQL=POSTGRES18_DISPOSABLE_RLS_FIXTURE
ORIGINAL_DATABASE=NOT_ACCESSED
MIGRATIONS=NONE
DB_WRITES=DISPOSABLE_FIXTURE_ONLY
SERVICE_RESTARTS=NONE
RUNTIME_RELOAD=NONE
PIX_REAL=OFF
PAGAMENTOS_REAIS=OFF
ATIVACAO_REAL=OFF
PRODUCTION=BLOCKED
