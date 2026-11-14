# FR Finance — M39087 | recuperação da CI geral, segunda etapa

Data do checkpoint: 13/11/2026. PR #2 deve permanecer em rascunho na branch AI Studio.

## Resultados confirmados
- Termux M39086: sincronização concluída em `18df1cce1544ea1aa4a62a7f4e4f4e09ec5f06c2`; seis testes Python aprovados, mais verificações de RBAC/navegação/crédito especial, árvore Git limpa e nenhum acesso ou migração ao PostgreSQL original.
- GitHub Actions `Validação da atualização AI Studio`, run `43542284926`, falhou em **frontend** e **PostgreSQL 16 descartável**; jobs `API sem banco`, `PostgreSQL 18 preflight` e `SQL 066–068 PG18` passaram. APK dependente ficou skipped.
- Frontend: `src/tests/android_safe_area_ci.test.ts` exigia `className="fr-app-shell `, mas M39075 já usa `className={'fr-app-shell ...' + (resumeValidationPending ? ' invisible pointer-events-none select-none' : '')}` junto com `aria-hidden` e `inert` ao revalidar sessão. O teste literal estava defasado; app continua montado e bloqueado durante a revalidação.
- Backup: `E: Unable to locate package postgresql-client-16` no APT do runner. Tentativa anterior com pg_restore mais novo falhara por `transaction_timeout` em servidor PG16. Não é evidência de falha do PostgreSQL do Termux.

## M39087 publicada
1. Teste `android_safe_area_ci.test.ts` atualizado para verificar o shell montado com classes condicionais e os atributos `inert`/`aria-hidden`. **Nenhuma alteração em `src/App.tsx`**.
2. CI geral conserva serviço descartável `postgres:16` e usa `pg_dump`/`pg_restore` da imagem **oficial `postgres:16`** por um wrapper temporário gerado apenas dentro de `$RUNNER_TEMP`. O wrapper exige `GITHUB_ACTIONS=true`, host local `127.0.0.1`, porta 5432, papel `postgres`, DB `frcaixinha_ci` ou `frcaixinha_restore_ci` e ferramentas `pg_dump`/`pg_restore` somente. Usa `docker run --rm -i --network host` para preservar o fluxo binário via stdin/stdout.
3. Mantidos `age`, chaves efêmeras, `pg_restore --exit-on-error`, reconciliação da linha sintética restaurada, regras de banco descartável e job PostgreSQL18 independente.
4. Testes em `backend/tests/test_m39087_ci_backup_client_and_session_shell_ci.py` verificam a sintaxe bash do script extraído da CI, alinhamento YAML do heredoc, negativas fora do contexto descartável, rejeição do DB original e encaminhamento de argumentos por um executável Docker **falso** — não conectam banco ou rede.
5. Teste M39086 adaptado para exigir a nova operação pela imagem Docker, e workflow `frfinance-m39087-safe-area-restore-ci.yml` criado.

## Limites
Nenhum backup, restore, migração, alteração de SQL, login, API, APK, OCI, Pix, e-mail ou push real é executado no Termux por esta etapa. O `pg_restore` real será executado **somente no PostgreSQL descartável do GitHub Actions**. Testes de shell e CI isolada não substituem o backup/restauração de verdade do pipeline geral.

## Critério de aceitação
A CI geral e a CI M39087 devem terminar PASS; se o pipeline geral continuar bloqueado, os novos logs precisam ser inspecionados. No Termux, executar exclusivamente testes Python/TSX offline após sincronização protegida.
