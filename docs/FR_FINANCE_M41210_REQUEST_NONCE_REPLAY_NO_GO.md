# FR Finance M41210 — nonce de requisição e rejeição de replay (NO-GO)

Base M41200: 5ae9d3cebe2b381913e872f569e58c45e46f4d40. CP26-0061 / CTM-07, CP26-0062 / CTM-08, CP26-0257 / TENANT_RLS, TEC-09 e TEC-12. Preservados 330 IDs, 2.310 etapas, Issue #5 e PENDING_INDEPENDENT_EVIDENCE.

O gateway gera um UUIDv4 novo internamente por requisição, passa ao emissor como request_nonce e compara o nonce retornado por m41050.current_claims_v3() junto às cinco claims anteriores. O fixture registra o nonce que já integra o HMAC do ticket M41120 no contexto protegido, com unicidade, e o copia ao consumir o ticket e emitir a capability. Não aceita nonce vindo de cabeçalho, corpo ou query. Não há fallback para v1/v2, e a transação financeira segue READ ONLY. Funções anteriores preservadas para regressões históricas. O contrato do provider mudou; um provider antigo é incompatível e falha fechado.

Ensaios: nonce ausente/nulo/divergente offline; sessão errada com nonce correto; replay sequencial e concorrente de capability válida da mesma sessão nas seis rotas; expiração com nonce correto; recuperação por nova requisição. As regressões de revogação e isolamento continuam. Resultados dependem da CI no SHA exato.

Limite importante: esta é uma proteção na fronteira HTTP/SQL, não consumo atômico de capability em cada transação SQL. A instalação direta do token por papel financeiro ainda é possível no fixture até expirar ou revogar; a proteção contra replay fora do gateway, emissão independente e políticas do catálogo autoritativo continuam pendentes. Não se deve usar este pacote como autorização de produção. M40570, M40730, M40840, M40930, M41180 e provider padrão ausente/HTTP 503 permanecem. Nenhuma migração do catálogo alterada; alterações SQL somente no fixture isolado da CI.

ORIGINAL_DATABASE=NOT_ACCESSED; DB_WRITES=NONE; MIGRATIONS=NONE; SERVICE_RESTARTS=NONE; RUNTIME_RELOAD=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
