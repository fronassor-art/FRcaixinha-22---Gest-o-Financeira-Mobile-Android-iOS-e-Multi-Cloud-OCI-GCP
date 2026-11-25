# M40969 — reversão compensatória vinculada no Capital-Dias

## Alteração

O evento `REVERSAL` exige `reversesEventId` e referência a outro evento confirmado da mesma participação, no mesmo tenant e ciclo. A reversão precisa ocorrer na mesma data ou depois, ter o mesmo valor absoluto e só pode ser aplicada uma vez por evento-alvo. O sentido é derivado do alvo e invertido, incluindo uma cadeia confirmada de reversão de reversão. Ciclos de referência são rejeitados.

A reversão altera o capital no fechamento diário da sua própria data efetiva. Eventos de reversão pendentes ou marcados como anulados não alteram capital. Uma restituição comum continua distinta de reversão: a primeira representa retirada de capital; a segunda compensa um evento referenciado. O hash M40967/M40968 agora inclui o campo de referência reversa.

## Testes e rastreabilidade

- Contrato Técnico V2.2, cláusulas 10.3, 10.8 e TEC-06: capital líquido de restituições/reversões e eventos compensatórios com referência.
- CP26-0008 e CP26-0017: capital-dias e evidências para fechamento; requisitos continuam pendentes de aceite independente.
- Teste M40969 cobre contribuição/reversão, restituição/reversão, reversão de reversão, ordem de entrada, alvo inexistente, alvo pendente, associação a outro membro, data anterior, valor divergente, repetição do alvo e ciclo.
- Regressões M40965–M40968 executadas pelo workflow dedicado.

## Limites

O cálculo continua source-only. A referência é uma consistência declarada pela entrada, não autenticação nem prova de origem. O pacote não persiste eventos, não confirma reversão financeira, não altera ledger/API/DB/schema, não trata correção tardia pós-fechamento e não cria obrigação de pagamento. Nenhum item da matriz de 330 IDs / 2.310 etapas é marcado como concluído; os gates P0 do issue #5 permanecem abertos.

Sem migrações, acesso ao PostgreSQL original, reinício/reload ou sincronização nesta etapa. Flags reais OFF; produção bloqueada.
