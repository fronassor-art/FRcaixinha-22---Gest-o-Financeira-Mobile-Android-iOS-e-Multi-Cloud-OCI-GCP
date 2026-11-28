# M40970 — cálculo source-only da base de lucro líquido elegível

## Escopo

Adiciona `calculateEligibleProfitBasisV22` e `calculateCapitalDaysFromProfitBasisV22`. A primeira função soma apenas receitas recebidas/conciliadas no ciclo, despesas e perdas reconhecidas com prova e aceite de política e ajustes com referência explícita de autorização. Ela mantém competência, reconhecimento e data financeira em campos separados.

Capital principal, principal de empréstimo, recebíveis não pagos, juros futuros e prêmios lotéricos externos são classificados como não elegíveis. Resultado líquido negativo ou zero gera base distribuível zero. A função integrada entrega essa base ao cálculo Capital-Dias; valores acima do limite seguro da interface existente são rejeitados, sem arredondar ou truncar.

## Rastreabilidade

- Caderno/Contrato V2.2, seção 10.1: corte de realização, competência, despesas/perdas/ajustes e exclusões.
- CP26-0008: lucro líquido elegível e cálculo de distribuição.
- CP26-0009: principal, principal de crédito e Pix apenas aprovado não são lucro realizado.
- CP26-0017: fechamento exige evidências de resultado e pendências; o pacote não fecha nem liquida.
- Teste M40970 cobre elegíveis, excluídos, estado pendente, falta de conciliação/prova/autorizações, escopo, moeda, duplicidade, perda líquida, overflow e integração à prévia Capital-Dias.

## Limites

Os campos `CONFIRMED`, `reconciled`, `policyAccepted`, `evidenceRef` e `authorizationRef` são entrada não confiável nesta função pura; ela não atesta ledger, PSP, documento ou aprovação humana. A fonte autoritativa e a revisão de fechamento seguem pendentes no issue #5. Nenhum item dos 330 IDs / 2.310 passos é marcado como concluído por este pacote.

Sem API, UI, persistência, SQL, migração, acesso ao PostgreSQL original, reinício/reload ou sync Termux. Flags reais OFF; produção bloqueada.
