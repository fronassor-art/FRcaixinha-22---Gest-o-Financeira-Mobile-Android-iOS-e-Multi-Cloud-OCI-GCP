# FR Finance M41130 — invalidação por ciclo cadastral (NO-GO)

Base 12d2f18d59eaee1921bdab49ce4a0afe9be6e446. CP26-0061 / CTM-07 e CP26-0062 / CTM-08, matriz 330 IDs / 2.310 etapas preservada.

No fixture PostgreSQL 18 existente, mudança efetiva de estado da conta gira a geração das sessões do usuário. Inserção, alteração ou exclusão de vínculo gira somente as sessões do usuário/tenant/papel correspondente. A mudança de geração revoga as capabilities existentes na mesma transação. Não se reativam provas, tickets ou capabilities antigos ao restaurar o cadastro. Alteração sem mudança efetiva não gira geração. ACL mantém execução dos triggers e mutação cadastral fora dos papéis app/auth. Não há nova role, banco permanente ou migration.

Ensaios: rollback da suspensão; suspensão e reativação de vínculo com outro tenant preservado; exclusão/recriação do vínculo; suspensão e reativação da conta em dois tenants; escrita de admin suspenso e antigo após reativação negada e escrita fictícia com capability nova legítima. Regressões anteriores mantidas.

Limites: sem prova de serialização de escrita já iniciada contra revogação, isolamento REPEATABLE READ, custódia de chaves ou integração FastAPI real. Não altera normas de suspensão e reativação do produto. O fixture demonstra nova autorização no contexto reativado, não aprova política real de renovação de sessões. M40840/M40930 e Issue #5 NO-GO. CP26-0061/0062 PENDING_INDEPENDENT_EVIDENCE. Meta OCI 30/11 permanece condicionada.

ORIGINAL_DATABASE=NOT_ACCESSED; MIGRATIONS=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
