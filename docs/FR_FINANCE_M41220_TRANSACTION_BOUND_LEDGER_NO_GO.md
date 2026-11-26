# FR Finance M41220 — vínculo à transação PostgreSQL (NO-GO)

Base M41210: bec354c805441ead4386320d5efe72e2048f0a43. CP26-0061 / CTM-07, CP26-0062 / CTM-08, CP26-0257 / TENANT_RLS, TEC-09 e TEC-12. 330 IDs e 2.310 etapas preservados, Issue #5 aberta e PENDING_INDEPENDENT_EVIDENCE.

O gateway abre READ ONLY, obtém PID, virtualxid do lock exclusivo da transação e timestamp do início diretamente de PostgreSQL. O binder externo consome o ticket em transação separada e grava a identidade do destino em catálogo protegido, sem modificar a transação de leitura. current_claims_v4 exige identidade atual, escopo READ_ENTRIES, sessão, nonce e claims anteriores; as três tabelas do ledger no fixture usam somente v4. As claims históricas rejeitam replay de tokens vinculados; tokens antigos não vinculados permanecem para regressões isoladas e não autorizam o ledger. O provider padrão permanece ausente; API sem fallback.

Ensaios: leitura positiva repetida dentro da mesma transação, tentativa concorrente em outro backend, nova transação no mesmo backend, rollback e tentativa de reconsumo do ticket, token antigo não vinculado nas três tabelas, identidade ausente/malformada, regressões HTTP M41210 e anteriores. O teste real do SHA deve confirmar resultados. Não altera catálogo autoritativo.

Limites: a identidade da transação não é segredo nem prova de processo. O binder sintético verifica lock ativo e janela de tempo, mas não comprova a identidade independente do processo destinatário; titular de ticket válido ainda pode escolher uma transação ativa. Repetir leituras dentro da transação autorizada é intencional. Tokens históricos sem vínculo permanecem utilizáveis no fixture histórico, não nas três tabelas de ledger. A solução não atesta escrita financeira, SQL autoritativo, recuperação de cluster ou custódia independente. Não ativar provider. M40570, M40730, M40840, M40930 e M41180 continuam.

ORIGINAL_DATABASE=NOT_ACCESSED; DB_WRITES=NONE; MIGRATIONS=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
