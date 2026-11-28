# FR Finance M41110 — capability vinculada a identidade e papel (NO-GO)

Base M41100: 3128ccebfdcc8a44b5a9f5c2a8fb6620747d4654. CP26-0061 / CTM-07 e CP26-0062 / CTM-08. Matriz 330 IDs / 2.310 etapas preservada.

## Correção no fixture existente

A capability M41050 armazenava sessão, tenant e escopo, mas recuperava o papel ativo dinamicamente. Uma identidade legitimamente vinculada como membro e administrador da mesma caixinha poderia mudar de contexto sem invalidar uma capability anterior. M41110 fixa usuário e papel na emissão da capability e exige correspondência na leitura das claims. O bind mantém FOR SHARE na linha da sessão até o fim da transação. Um trigger restrito ao fixture invalida permanentemente capabilities existentes quando usuário, papel, tenant ou estado de revogação da sessão muda. A função de trigger não tem EXECUTE para o papel app; o app não tem UPDATE no armazenamento de capabilities.

## Testes

No PostgreSQL 18 descartável existente, sem novas roles ou bancos: identidade com ambos os vínculos, leitura legítima inicial, troca para admin durante transação asyncpg READ COMMITTED, negação de claims e linhas na instrução seguinte e no reuso do mesmo backend. Capability de escrita emitida para membro não adquire direito após promoção. Novas capabilities de admin leem e escrevem no escopo correto. Retorno ao papel anterior não restaura capabilities revogadas; nova capability de membro lê somente as próprias linhas. Retorno a admin também não restaura autorização antiga. Verifica revogação persistida além da ausência de linhas e mantém regressões M41050–M41100.

## Limites de evidência

Não prova cancelamento de uma instrução já iniciada, isolamento REPEATABLE READ, invalidação por mudança de vínculo fora da linha de sessão, nem vínculo de papel no ticket anterior ao bind; estes continuam pendentes de avaliação. Nenhuma integração em rotas reais, custódia de chave, migração candidata ou liberação de runtime. M40840 e M40930 permanecem. CP26-0061 e CP26-0062: PENDING_INDEPENDENT_EVIDENCE. Issue #5 NO-GO.

ORIGINAL_DATABASE=NOT_ACCESSED; MIGRATIONS=NONE; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.

CI necessária no SHA exato antes da sincronização source-only. Não alegar PASS antes do resultado.
