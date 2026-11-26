# FR Finance M41200 — vínculo individual de sessão SQL (NO-GO)

Base M41190: d9a7b203902e4221426c913d673efc9bcfdb40b7. CP26-0061 / CTM-07, CP26-0062 / CTM-08, CP26-0257 / TENANT_RLS, TEC-09, TEC-12. 330 IDs, 2.310 etapas, Issue #5 e PENDING_INDEPENDENT_EVIDENCE preservados.

A autorização do ledger passa a exigir o UUID da sessão verificada pelo backend além do usuário, papel, tenant e escopo. A função versionada m41050.current_claims_v2() devolve somente claims já validadas e o UUID capturado no bind da capability, nunca o digest ou bearer. A função anterior mantém a forma de retorno para políticas e testes históricos, mas valida também a igualdade do UUID capturado com o registro de sessão atual. O identificador é único no fixture, e alterações nele também invalidam a geração. Não há fallback quando a função versionada está ausente. SQL exclusivamente no fixture CI já existente; nenhum arquivo do catálogo autoritativo alterado.

O provedor sintético seleciona o digest pelo ID de sessão juntamente com usuário, papel e tenant. Duas sessões da mesma conta recebem UUIDs reais do fixture, exercitam as seis rotas em concorrência, e tentativas cruzadas de reutilização de capability são negadas em ambas as direções. Revogar a primeira sessão não invalida a segunda e a primeira capability não retorna claims. Testes offline acrescentam UUID divergente, ausente e nulo e preservam falhas transacionais. O resultado precisa ser obtido da CI do SHA exato.

Limites: o protótipo continua sem prova do emissor independente, da custódia ou da política autoritativa. O identificador de sessão não é segredo nem substitui o ticket assinado; o gateway não torna capabilities de uso único dentro da mesma sessão. O provedor oficial permanece ausente; M40570, M40730, M40840, M40930, M41180 e o HTTP 503 padrão seguem em vigor. Nenhuma migração autorizada, nenhum acesso ao PG original, nenhuma ativação de runtime. Aceite externo continua pendente.

ORIGINAL_DATABASE=NOT_ACCESSED; DB_WRITES=NONE; MIGRATIONS=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
