# FR Finance M40770 — gatilho seguro da CI geral para alterações dos adaptadores financeiros

**Data:** 19/11/2026. **Base:** M40760 `6672098`. **Produção: NO-GO.**

## Falha de observabilidade

Após a publicação do M40760, a branch `atualizacao-ai-studio-9b46a63187` apontava para `6672098` e os oito testes específicos passaram, mas a PR #2 continuava exibindo `4301420` e o workflow principal `validacao-atualizacao.yml` não havia executado no HEAD atual. A configuração anterior do workflow possuía apenas `pull_request` (base `main`) e `workflow_dispatch`. Por isso um avanço da branch sem atualização da PR não necessariamente promovia a CI geral.

## Correção limitada

O workflow principal recebe um novo gatilho `push`, somente para a branch de desenvolvimento FR Finance AI Studio, e com filtro de caminhos: o próprio workflow, os três adaptadores Mercado Pago M40740/M40750/M40760, seus testes específicos e os respectivos workflows. Os gatilhos existentes de PR e acionamento manual são preservados. Isto permite executar a CI geral contra o SHA real da branch quando se altera uma dessas superfícies, mesmo que o snapshot da PR ainda esteja atrasado.

O workflow preserva `permissions: contents: read`, execução em runners GitHub descartáveis, testes RLS em PostgreSQL efêmero, frontend e APK debug. Nenhum deploy, pull no Termux, conexão com PostgreSQL local, migration, restart ou ação de provedor é adicionada. A existência do gatilho não é um resultado PASS: verificar os **sete jobs** no commit publicado antes de qualquer source-only sync do Termux.

## Bloqueios ainda existentes

- M40730: comprometimento do login SQL emissor contorna a verificação Ed25519 (**NO-GO**).
- M40570: GUC `app.current_*` falsificável sob execução SQL arbitrária na role app (**NO-GO**).
- M40740/M40750/M40760: transporte com mock apenas nos três adaptadores alterados; outros caminhos de rede não são certificados.
- Runtime owner FastAPI não atestado, não existe aprovação de pagamentos reais, OCI e gerenciamento de segredos seguem sem comprovação operacional.

**Operação autorizada exclusivamente no GitHub:** manter PR #2 Draft, main preservada, sem migrações, DB writes locais ou reinícios. `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
