# M40966 — vínculo de tenant/ciclo/membro no cálculo Capital-Dias

## Incremento

O cálculo M40965 agora exige um escopo explícito `tenantId + cycleId`. Antes de calcular pesos, exige que cada membro pertença ao mesmo par e que cada evento confirme tenant, ciclo e `membershipId` iguais aos do membro que o contém. O resultado devolve o par de escopo usado.

Entrada ausente, vazia, com espaços externos, cruzada entre tenants/ciclos ou ligada a outro membro é recusada antes de produzir o resultado. Os identificadores são tratados como strings opacas com até 128 caracteres.

## Rastreabilidade

- Caderno Técnico V2.2: cláusulas 2.3 e 2.9 (ações financeiras vinculadas a `tenant_id` e `cycle_id`); 10.3/10.4 e TEC-04 (cálculo por ciclo).
- Testes M40966 negativos: tenant divergente do membro; ciclo divergente; evento de outro tenant/ciclo; evento de outro membro; escopo ausente ou malformado.
- Teste M40965 integral continua validando janela anual, restituições, elegibilidade, perdas, centavos e conservação.

## Limites

Este é um bloqueio de inconsistência de dados na fronteira do cálculo. Comparar IDs não autentica quem os informou, não prova titularidade e não autoriza acesso. Não substitui identidade de sessão, RLS, autorização de tenant nem revisão adversarial do SQL. O resultado segue `SOURCE_ONLY`: nenhum ledger, snapshot, API, persistência, fechamento ou liquidação foi adicionado.

Sem alteração de SQL/migration, DB original, Termux, serviços ou flags reais. `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
