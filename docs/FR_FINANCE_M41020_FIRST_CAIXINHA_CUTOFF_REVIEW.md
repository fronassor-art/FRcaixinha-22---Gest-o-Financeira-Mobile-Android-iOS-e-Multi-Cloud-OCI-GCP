# FR Finance M41020 — prévia do corte da primeira caixinha

Base: branch \`atualizacao-ai-studio-9b46a63187\`; pai M41010 \`ad7dc1683c204b0e2ab75e5f4c2d188cdcbc5ddf\`. PR #2 permanece Draft.

## Escopo

O cartão Master da primeira caixinha permite comparar, sem valor preselecionado, as duas convenções possíveis entre a data final de pagamento informada (20/12/2027) e o limite exclusivo do Capital-Dias. A seleção fica somente no estado efêmero desta tela e é descartada ao sair.

| Opção para revisão | Janela de calendário | Dias civis |
|---|---|---:|
| Excluir 20/12/2027 | [10/12/2026, 20/12/2027) | 375 |
| Incluir 20/12/2027 | [10/12/2026, 21/12/2027) | 376 |

A contagem é apenas a duração do intervalo. Sem eventos de capital e sem política confirmada, não calcula Capital-Dias, lucro ou rateio. A data de liquidação continua separada da janela de cálculo.

## Guardas preservadas

- Nenhuma opção é escolhida por padrão; o corte contratual permanece não resolvido.
- A prévia não constitui aceite, não calcula valores financeiros, não salva dados e não se vincula a tenant/convite.
- Abertura do ciclo, aceite de contrato, convites, SaaS, contribuições e execução financeira continuam \`false\`.
- Valor da cota, quantidade de cotas por membro e publicação dos Contratos A/B seguem pendentes.
- A divergência entre a matriz de requisitos legada 15%/85% e a redação V2.2 mais recente de percentual administrativo livre permanece sem decisão nesta entrega.

## Rastreabilidade

| Requisito | Arquivo | Teste | Estado |
|---|---|---|---|
| CP26-0193 — distinguir corte do Capital-Dias e data de liquidação | \`src/services/firstCaixinhaCutoffReviewV22.ts\`, \`src/components/FirstCaixinhaCalendarDraftPanel.tsx\` | M41020 | Comparação source-only; decisão de ciclo continua pendente |
| CP26-0008/0070 — cálculo e rateio | Motor Capital-Dias V2 | M40965/M41010 | Não promovido por este pacote |
| CP26-0010/0011/0099 — cotas e piso | Política de ciclo | M41000/M41020 | Sem valor inventado; prova independente pendente |
| CP26-0018/0019/0072/0074 — convites, identidade e aceite | Jornada Master/Admin/Membro | Gates de produção e E2E | Não implementado nem liberado por este pacote |

A matriz de 330 IDs e as 2.310 etapas permanecem inalteradas. CI cobre somente o código e não fecha requisitos, homologação externa ou AT real.

## Evidência e limites

M41020 adiciona apenas TypeScript/React, testes e workflow CI. Não adiciona SQL/migração/API, não acessa o PostgreSQL autoritativo, não cria ou altera ciclos, não reinicia serviço e não altera runtime. PIX_REAL, PAGAMENTOS_REAIS, ATIVACAO_REAL e comunicações reais permanecem OFF; \`PRODUCTION=BLOCKED\`.
