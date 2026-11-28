# FR Finance M39800 — Origem do FastAPI já em execução

**Data:** 14/11/2026 · **PR:** #2 Draft, branch AI Studio.

## Evidência recebida no Termux

O operador concluiu o fast-forward `20c5d85 → 52454c9`. A verificação M39700 mostrou:

| Campo | Resultado no aparelho |
|---|---|
| Sincronização Termux | `M39700_TERMUX=SYNCED`, HEAD `52454c9` |
| Fonte da aplicação | `M39700_GIT_SOURCE=M39700_CODE_PRESENT` |
| Servidor escutando | `M39700_HEALTH=FR_FINANCE_ONLINE` |
| Versão efetivamente carregada | `M39700_LOADED_CODE=STALE_OR_NOT_LOADED` |
| Rotas GET | `GET_ROUTES_PRESENT` e 0 ausentes |
| Readiness do banco | `SKIPPED_UNVERIFIED_RUNNING_APP` por segurança |
| Status do processo | `BLOCKED_RUNNING_API_OR_VERSION` |
| Migrações, escrita e Pix | **Nenhuma execução** |

A interpretação é **servidor anterior ao marcador M39700**, apesar do checkout já estar sincronizado. Não é evidência de falta de tabelas PostgreSQL e não exige migrar o banco. Os arquivos Python importados no processo antigo não são recarregados por `git merge --ff-only`.

## Desenvolvimento M39800

- `backend/scripts/frfinance_m39800_running_process_origin_readonly.py`: lê apenas o health local e, após confirmar FR Finance, pesquisa exclusivamente o socket `127.0.0.1:8000` em `/proc/net/tcp`, relaciona o inode a descritores de processos do **mesmo UID**, confere a pasta `$HOME/fr-finance` e classifica a linha de execução sem mostrá-la.
- Reconhece como origem esperada somente o Uvicorn executado como `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` no checkout original, sem `--reload` nem processos workers múltiplos. Se o processo for diferente, proprietário ambíguo ou os diretórios `/proc` estiverem inacessíveis por política do Android, retorna **BLOCKED** e não inventa identidade.
- `backend/tests/test_m39800_original_fastapi_process_origin_ci.py`: testes sintéticos para socket/porta/UID/pasta e casos de falha sem acesso ao dispositivo.
- `.github/workflows/frfinance-m39800-process-provenance-ci.yml` e `validacao-atualizacao.yml`: executar provas de não acionamento de sinais/processos antes da CI ampla.

Nenhum programa desta entrega imprime PID, comando completo, ambiente, credenciais, URL de banco ou conteúdo de negócio. **Não existe função de parada/reinício automático.** A confirmação da origem dá informação para um reinício manual e controlado **apenas se autorizado pelo operador e na sessão correta**, e não equivale à autorização para matar processos.

## Handoff posterior à CI

A próxima execução no Termux deve apenas sincronizar a revisão M39800 e executar **uma vez** o novo verificador de origem do processo. Não repetir sincronizações M39600/M39700 já concluídas e não reaplicar SQL110–113. Se o Android negar leitura de `/proc`, registrar `BLOCKED_NO_PROCESS_PROOF`; o operador ainda pode identificar a sessão original do Uvicorn manualmente sem interferir no banco. Se o listener for classificado como original, negociar um encerramento pela própria sessão e uma inicialização segura, sem `pkill`, `kill -9` ou encerramento de PostgreSQL.

**Restrições inalteradas:** `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCTION_RELEASE=BLOCKED`. O banco FR Finance `5433` permanece distinto do FR Caixinha 2.2 `5432`. Nenhuma migração nova adicionada nesta entrega. Os gates de produção e aceites E2E do Caderno Mestre e Contrato Técnico permanecem independentes.
