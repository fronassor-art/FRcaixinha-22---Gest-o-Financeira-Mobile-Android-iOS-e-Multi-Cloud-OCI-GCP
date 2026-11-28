# M40965 — Capital-Dias V2 por ciclo, cálculo puro source-only

## Escopo entregue

Adiciona `src/services/capitalDaysV22.ts`, um cálculo puro de preview do Capital-Dias e do rateio do lucro líquido em um ciclo de 12 meses `[cycleStart, cycleEndExclusive)`, com E no aniversário de S e ajuste ao último dia válido (como 29/02 para 28/02 no ano seguinte). Usa datas civis ISO sem depender do fuso configurado no telefone, valores monetários em centavos inteiros e `BigInt` para peso e rateio exatos.

Cada membro fornece capital de abertura conciliado, eventos identificados (aporte ou restituição, status confirmado/pendente/revertido) e períodos de elegibilidade derivados da política aceita. Aportes/restituições confirmados passam a afetar o fechamento do próprio dia; pendentes e revertidos não entram no cálculo. A elegibilidade é recebida como intervalo, sem inferir regra de inadimplência. A restituição não pode exceder o capital confirmado no fechamento diário.

O percentual administrativo é entrada obrigatória em pontos-base, sem valor padrão. A divisão usa arredondamento HALF_UP no pool administrativo, complemento exato para o pool dos membros, quota inteira truncada e maiores restos com desempate lexical por `membership_id`. Se não houver peso elegível, o pool dos membros fica pendente e segregado. Perda líquida não cria distribuição.

## Rastreabilidade e limites

- Caderno V2.2: cláusulas 10.3, 10.4, 10.6, 10.7 e RET-15; TEC-04; cenários RET-T01, RET-T05, RET-T16.
- Testes: corte entre anos, fechamento diário, restituição, status não confirmado, janelas de elegibilidade, centavos residuais, desempate, ausência de peso, perda e entradas inválidas.
- Módulo é somente cálculo de preview; não consulta identidade, valida evidência externa, decide elegibilidade, grava snapshot/ledger, autoriza fechamento nem liquida dinheiro.
- Nenhuma API, interface, SQL, migration, PostgreSQL original, arquivo Termux ou operação financeira real foi alterada.

`PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
