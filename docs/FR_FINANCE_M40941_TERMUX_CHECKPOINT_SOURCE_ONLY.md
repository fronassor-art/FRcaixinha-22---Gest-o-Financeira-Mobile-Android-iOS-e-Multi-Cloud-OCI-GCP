# FR Finance M40941 — diagnóstico pós-sync no Termux, somente leitura

O pacote M40941 prepara um **único checkpoint seguro para o celular**. Ele será usado somente **depois** que uma revisão específica concluir todas as CIs relevantes no mesmo SHA e for sincronizada com o sincronizador source-only M40600. Nunca executa `git fetch`, `git merge`, `git checkout`, PostgreSQL, migration, signal, start/restart ou ativação real.

Quando o pacote for aprovado, o operador deve usar **Termux nativo, fora do Debian**, no único diretório `$HOME/fr-finance`. O comando modelo pós-sync é:

```bash
cd "$HOME/fr-finance" &&
python -B backend/scripts/frfinance_m40941_termux_post_sync_checkpoint_readonly.py --expected-head SHA_COMPLETO_APROVADO_PELA_CI
```

**Não substitua `SHA_COMPLETO_APROVADO_PELA_CI` antes da conclusão de todas as CIs do SHA exato**. O script bloqueia valores sem 40 caracteres hexadecimais, HEAD diferente, checkout inesperado, branch errada, origin fora da lista do projeto e arquivos rastreados modificados. Não mostra URLs com credenciais nem nomes de arquivos modificados. Os testes simulam as condições negativas, sem fingir que o GitHub Actions está rodando no Android.

O retorno `M40941_STATUS=PASS_SOURCE_ONLY_NO_GO` significa apenas que o Git local foi sincronizado no commit esperado, com manifesto M40939 válido e ainda **NO-GO**. **Não significa** que a FastAPI tenha carregado o novo código, que o APK foi instalado, que a segurança SQL foi corrigida ou que exista autorização para migration.

A etapa anterior será feita apenas com M40600 `--expected-old <sha_original>` `--target <sha_ci_aprovado>` depois da conferência das CIs. Nenhum comando de sync ou migration é autorizado apenas com este documento.

`M40840=NO-GO`; `M40930_MASTER_WRITES=503`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `MIGRATIONS=NONE`; `PRODUCTION=BLOCKED`; `TERMUX_SYNC=NONE` na fase GitHub.
