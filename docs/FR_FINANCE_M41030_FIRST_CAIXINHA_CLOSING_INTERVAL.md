# FR Finance M41030 — intervalo entre última contribuição e encerramento

## Escopo

Esta alteração apresenta, no rascunho exclusivo da primeira caixinha do proprietário, a diferença civil entre a última contribuição informada em 10/11/2027 e o encerramento/pagamento final informado em 20/12/2027: **40 dias civis**.

O valor descreve apenas a distância entre duas datas sem horário local. Não cria vencimento adicional, não decide a inclusão de 20/12 no corte do Capital-Dias, não fixa processamento, juros, lucro ou rateio e não altera o calendário das demais caixinhas.

## Código e provas

- src/services/firstCaixinhaCloseIntervalV22.ts: valida o rascunho canônico M41000 antes de calcular a diferença de datas UTC civis.
- src/components/FirstCaixinhaCalendarDraftPanel.tsx: apresenta o intervalo junto às datas da primeira caixinha e deixa explícito que ele não habilita cálculo.
- src/tests/m41030_first_caixinha_closing_interval_ci.test.ts: verifica os 40 dias, datas, falhas fechadas para rascunho alterado, renderização e ausência de persistência/API no painel.
- src/tests/m41000_first_caixinha_calendar_draft_ci.test.ts e src/tests/m41020_first_caixinha_cutoff_review_ci.test.ts: regressões do calendário e do corte seguem no workflow dedicado e na validação geral.

## Limites

É um resumo de calendário, não um recibo de pagamento ou confirmação de encerramento. Não altera contratos nem matriz de 330 requisitos. Sem SQL, API, conexão ou escrita em banco, migrações, convites, cobrança, operação financeira, serviço ou flags reais. PIX_REAL=OFF, PAGAMENTOS_REAIS=OFF, ATIVACAO_REAL=OFF, PRODUCTION=BLOCKED.
