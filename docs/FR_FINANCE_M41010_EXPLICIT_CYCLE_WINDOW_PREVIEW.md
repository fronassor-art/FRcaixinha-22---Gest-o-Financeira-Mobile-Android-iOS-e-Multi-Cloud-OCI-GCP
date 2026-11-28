# FR Finance M41010 — janelas explícitas de ciclo no motor Capital-Dias

Base: branch atualizacao-ai-studio-9b46a63187, HEAD anterior f7d33a2874d275f4b48c23decdc8079917b93d9b. PR #2 Draft. Pacote source-only, sem integração operacional.

## Requisito e escopo

O Caderno Mestre mantém o ciclo de 12 meses como padrão até decisão expressa sobre alternativa. A instrução do proprietário para sua primeira caixinha informa início em 10/12/2026, contribuições mensais até 10/11/2027 e encerramento/pagamento em 20/12/2027. O M41000 registra isso como rascunho sem tenant, convite ou contrato vinculados.

Este pacote habilita o preview financeiro a processar uma janela diferente do aniversário de 12 meses somente quando o chamador fornece uma política aceita, congelada, com hash e evidência referenciados, ligada ao tenant, ciclo e datas. O registro continua caller-supplied e não autenticado; não autoriza persistência, fechamento ou pagamento.

## Comportamento

- Sem autorização de janela especial, o motor continua exigindo aniversário de 12 meses, com ajuste para o último dia válido do mês.
- EXPLICIT_ACCEPTED_WINDOW valida escopo, datas inclusivas/exclusivas, versão e hash da política, aceite, congelamento e referência de evidência.
- Capital-Dias agora soma segmentos de saldo constante entre eventos e limites de elegibilidade. O peso continua equivalente à soma diária; a implementação não percorre cada dia de janelas extensas.
- A impressão digital do preview Capital-Dias inclui todo o aceite explícito, evitando que a janela aceita fique fora do conteúdo coberto pelo hash.
- Testes cobrem as duas leituras possíveis para 20/12/2027: exclusão (endExclusive=20/12) e inclusão (endExclusive=21/12). O pacote deliberadamente não escolhe uma delas para a primeira caixinha.
- Nada neste pacote vincula o rascunho M41000 à conta do administrador, habilita convite, aceite de contratos, SaaS, contribuição, liquidação ou operação real.

## Critérios e evidência de requisitos

| Requisito | Arquivo/API | Verificação | Estado após este pacote |
|---|---|---|---|
| CP26-0008 / CP26-0070 — Capital-Dias e preservação do rateio | src/services/capitalDaysV22.ts | M40965 + M41010 | Preview de janelas anual e explícita; não é fechamento real |
| CP26-0193 — separar corte Capital-Dias e data de liquidação | src/services/cycleWindowV22.ts, contrato de política em cycleDistributionPreviewV22.ts | M40971 + M41010 | Duas convenções testadas; decisão de 20/12 ainda pendente |
| CP26-0018/0019, CP26-0072/0074 — convite, identidade, contrato e aceite | Jornada Master/Admin/Membro | M41000 e gates de produção da issue #5 | Não implementado por M41010 |
| CP26-0010/0011/0099 — valor da cota, quantidade e piso de R$150 | Política do ciclo | M41000 e checklist 330 | Nenhum valor inventado; falta definição do proprietário |
| Macropacote 2310 — etapas de convite/contrato, cota/ciclo, fechamento e aceite | Este pacote fica limitado à etapa de cálculo/preview | workflows M40965, M40970, M40971 e M41010 | E2E real e aceites independentes continuam pendentes |

Matriz CP26 continua preservada com IDs e estados históricos; nenhum requisito foi marcado concluído apenas por código ou CI.

## Limites de segurança e operação

executionAuthorized=false continua inalterado. PR #2 permanece Draft; issue #5 permanece aberta. Sem alteração em SQL, migrations, APIs FastAPI, contratos comerciais publicados, dados, sessão, convite ou PSP. Nenhum banco/serviço foi acessado, reiniciado ou recarregado. PIX, pagamentos e ativação reais permanecem OFF; produção continua BLOCKED.
