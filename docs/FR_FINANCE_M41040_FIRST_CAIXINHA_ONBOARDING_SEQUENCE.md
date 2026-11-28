# FR Finance M41040 — sequência da primeira caixinha em modo somente leitura

## Escopo

Detalha no painel Master a ordem de trabalho desejada para a caixinha específica do proprietário: convite do administrador, cadastro, Contrato A, licença SaaS, configuração e Contrato B, convites dos membros, cadastro/aceite dos membros, contribuições e encerramento planejado em 20/12/2027.

As nove etapas são um roteiro visual bloqueado. Nenhum convite é emitido; nenhum cadastro, aceite, cobrança, contribuição, ciclo ou pagamento é criado. A licença da plataforma permanece separada do dinheiro de cada caixinha. Os valores e a quantidade de cotas continuam definidos pelo administrador no momento cabível; esta prévia não os fixa.

## Rastreabilidade mantida

A implementação referencia requisitos existentes da matriz CP20261114, sem criar, renumerar ou promover IDs:

- CP26-0018 e CP26-0019: convite individual, identidade/sessão, e-mail verificado, contrato canônico e aceite.
- CP26-0020 e CP26-0024: gates de produção e operações reais desativados até homologação independente.
- CP26-0006 e CP26-0007: separação do caixa Master e do caixa de cada caixinha.
- CP26-0023: autorização e testes independentes do provedor/Pix.
- CP26-0017: evidências necessárias ao fechamento.

Cada requisito continua sujeito às sete etapas M39100: 01_SCOPE, 02_CODE, 03_UNIT, 04_SECURITY, 05_E2E, 06_EXTERNAL e 07_SIGNOFF. A matriz permanece com 330 itens e estados de evidência pendentes. Nenhum gate M40939 é alterado. Contratos A e B seguem minutas; o corte do Capital-Dias e as regras de fechamento não são decididos nesta mudança.

## Código e provas

- `src/services/firstCaixinhaOnboardingSequenceV1.ts`: nove passos imutáveis associados a IDs CP26 e aos gates/tarefas de liberação atuais; cada passo permanece `BLOCKED_SOURCE_ONLY`.
- `src/components/FirstCaixinhaCalendarDraftPanel.tsx`: exibe ator, ordem e motivo de bloqueio no painel de calendário da primeira caixinha.
- `src/tests/m41040_first_caixinha_onboarding_sequence_ci.test.ts`: valida ordem, IDs existentes, sete etapas, status pendente da matriz, texto renderizado e ausência de formulário, API, persistência ou ações financeiras.
- `.github/workflows/frfinance-m41030-first-caixinha-closing-interval-ci.yml` e `.github/workflows/validacao-atualizacao.yml`: executam essa prova na CI dedicada e na validação geral.

## Limites

É uma alteração de fonte/UX para planejamento. Não modifica contratos, regras de rateio, calendário das demais caixinhas, manifestos de produção, matriz de evidências, API, SQL, banco, migrações, processos, provedor, convites reais ou flags de operação.

`PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`; `MIGRATIONS=NONE`.
