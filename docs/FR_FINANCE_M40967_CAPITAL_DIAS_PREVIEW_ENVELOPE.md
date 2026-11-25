# M40967 — envelope determinístico da prévia Capital-Dias

## Escopo implementado

A função `createCapitalDaysPreviewEnvelopeV22` calcula a prévia usando a entrada validada do M40965/M40966 e produz um envelope não persistido com:
- versão explícita da política aceita;
- resultado calculado;
- SHA-256 de uma serialização canônica que inclui algoritmo, política, entrada e resultado.

Membros, períodos e eventos são ordenados por identificadores/datas antes da serialização. Reordenar arrays sem mudar os fatos preserva o digest; mudar entrada ou versão da política muda o digest. A função não altera a entrada original.

## Rastreabilidade e validação

- CP26-0008 / requisito de lucro líquido elegível e rateio parametrizado: vincula política explícita e cálculo Capital-Dias.
- CP26-0017 / evidências de fechamento: melhora a identificação determinística da prévia; não declara fechamento nem liquidação.
- Fonte: `src/services/capitalDaysV22.ts`.
- Teste: `src/tests/m40967_capital_days_envelope_v22.test.ts`; também reexecuta as suítes M40965 e M40966.
- Cobertura: hash de 64 caracteres, invariância à ordem, alteração por mudança de dados ou política, input imutável, versão ausente rejeitada e conservação dos centavos.
- A matriz de 330 IDs e 2.310 etapas permanece intacta; nenhum item recebe aceite por esta CI.

## Limites e estado

O SHA-256 é uma impressão de integridade determinística, não assinatura, autenticação, prova de origem, consentimento, autorização ou evidência independente. O chamador ainda precisa obter a política e os eventos por fonte autenticada e autorizada. Não há persistência, API, ledger, fechamento, pagamento, SQL ou migração neste pacote.

Sem acesso ao PostgreSQL original, sem escrita de banco, sem restart/reload de serviços, sem sync Termux nesta etapa e sem ativação financeira. `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
