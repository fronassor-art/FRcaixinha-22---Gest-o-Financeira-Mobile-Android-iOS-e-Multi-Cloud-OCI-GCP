# FR Finance — M39086: correção das três falhas remanescentes da CI geral

Data: 13/11/2026. Branch de trabalho `atualizacao-ai-studio-9b46a63187`; PR #2 permanece draft.

## Checkpoint anterior
- No Termux nativo, M39085 foi sincronizada até `85895f7f7b6ba82738ec332d7a2f1b34aca0110d`: **38 testes PASS**, 1 DeprecationWarning, sem migrações e sem gravações.
- Workflow Crédito Especial M39010, execução `43538006338`: **SUCCESS** (corrigida a falha anterior da contagem SQL M39046).
- Workflow de validação geral `43538006669`: falhou em frontend, backend-sem-banco e postgres-isolado; outros jobs foram aprovados; APK dependente ficou SKIPPED.

## Falhas e resoluções
1. `src/tests/role_scope_ui.test.ts` esperava o menu do membro sem `MINHAS_OPORTUNIDADES`. A M39076 incluiu essa aba. Atualizado o teste, reforçando as negativas (Master e Admin não acessam a aba do membro; Master e Membro não acessam `CAMPANHAS_MEMBROS`). Código de permissões não modificado.
2. `backend/tests/test_m19200_migration_inventory_ci.py` exigia 20 `LOCAL_CANDIDATE_REQUIRES_PROOF`, mas o catálogo agora tem 22, incluindo migrações 112 e 113. Ajustado para 22 e acrescentada exigência de ausência de evidência de aplicação local; **não é autorização para executar ou reaplicar SQL**.
3. `pg_restore` da CI estava usando cliente PostgreSQL mais recente contra serviço descartável PostgreSQL 16. Falha objetiva: `unrecognized configuration parameter "transaction_timeout"`. Atualizado exclusivamente o passo `Backup cifrado age e restauração descartável` de `.github/workflows/validacao-atualizacao.yml` para instalar e usar `postgresql-client-16` explicitamente em `PATH`, validando `pg_dump`, `pg_restore` e servidor de major 16 antes da operação. Criptografia age, `pg_restore --exit-on-error` e comparação de linhas restauradas permanecem obrigatórios. O job separado PostgreSQL 18 não foi alterado.

## Cobertura
- `backend/tests/test_m39086_general_ci_drift_ci.py` fiscaliza todas as correções sem acesso a banco.
- `frfinance-m39086-general-ci-drift.yml` testa o inventário e o menu com Node e compilador TypeScript 7 oficial no Linux.
- A restauração cifrada **real em banco descartável** continua sendo prova exigida no workflow geral; a validação estática não a substitui.
- M39086 não adiciona migrations, não toca `/root/fr-finance` nem PostgreSQL do Termux (5433), não configura OCI, não gera APK, não ativa Pix nem envia notificações.

## Homologação pendente
Aguardar a conclusão da CI geral na nova revisão da PR e executar os testes estáticos no Termux nativo. Até lá, não anunciar M39086 como integralmente homologada.
