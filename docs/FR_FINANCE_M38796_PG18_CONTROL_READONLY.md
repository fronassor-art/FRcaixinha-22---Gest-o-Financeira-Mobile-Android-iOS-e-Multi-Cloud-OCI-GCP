# FR Finance — M38796: diagnóstico de pg_control sem recuperação automática

## Evidência concreta no Termux

M38795 sincronizado e homologado: 12.665 PASS, 130 SKIP, um aviso e zero falhas.

- `M38795_PROJECT_ISOLATION=PASS_STATIC`
- `M38795_PIDFILE=EXPECTED_PATH_PORT_5433`
- `M38795_PID_REACHABLE=NOT_RUNNING`
- `M38795_PG_CTL=NOT_RUNNING_REPORTED`
- `M38795_PG_ISREADY_5433=NO_RESPONSE`
- `M38795_DIAGNOSIS=POSSIBLY_STALE_PIDFILE_DO_NOT_DELETE`

Isso sugere um arquivo postmaster.pid residual, mas não comprova a integridade da base e não autoriza apagar arquivos, reiniciar o cluster, fazer recuperação, executar migrações ou consultar membros.

## Implementação

O `backend/scripts/frfinance_m38796_pg18_control_preflight.py` verifica o manifesto de isolamento, a branch, o remote, a versão PG18 e a identidade do diretório de dados por meio do diagnóstico M38795. Em seguida, **somente se** a porta 5433 não responder, o PID não existir e `pg_ctl status` informar parado, consulta o estado do cluster com:

```sh
pg_controldata -D /data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18
```

O programa oculta a saída bruta e publica apenas uma classificação segura do campo `Database cluster state`. Não publica o identificador interno da base, LSN do WAL, checkpoint, dados de usuários ou mensagens de erro. Repete o diagnóstico de processo após a leitura para bloquear mudanças durante a verificação.

Na documentação oficial do PostgreSQL 18, `pg_controldata` mostra metadados do cluster e informações de WAL/checkpoint. Esse comando *não inicia o servidor*. O `postmaster.pid` serve para proteger contra múltiplas instâncias usando o mesmo diretório. A remoção manual de arquivos de lock exige investigação separada e confirmação da ausência de processos concorrentes.

## Resultado esperado e interpretação

- `CLEAN_SHUTDOWN_REPORTED`: o pg_control relata desligamento limpo; a presença do PID residual ainda exige revisão manual.
- `UNCLEAN_OR_RUNNING_STATE_REPORTED`: o pg_control relata estado de produção; com processo aparentemente parado, pode haver interrupção abrupta e necessidade de recuperação WAL — **não iniciar às cegas**.
- `RECOVERY_SHUTDOWN_REPORTED`, `ARCHIVE_RECOVERY_STATE_REPORTED` ou `STARTUP_STATE_REPORTED`: revisão de estado de recuperação necessária.
- `UNKNOWN_STATE` ou `BLOCKED_INCOMPLETE_EVIDENCE`: nenhuma operação de recuperação autorizada.

Em todos os resultados: `M38796_OPERATION_ALLOWED=NONE`, `M38796_PG_START_STOP=NONE`, `M38796_POSTMASTER_PID_DELETE=NONE`, `M38796_MIGRATIONS=NONE` e `M38796_PRODUCTION=BLOCKED`.

## Comandos no FR Finance

Após sincronizar a branch do repositório atual:

```sh
cd "$HOME/fr-finance"
python backend/scripts/frfinance_m38796_pg18_control_preflight.py offline
python backend/scripts/frfinance_m38796_pg18_control_preflight.py local AUTHORIZE_FRFINANCE_PG18_CONTROL_READONLY
```

O segundo comando é uma autorização somente de leitura. Não requer senha e não utiliza a porta 5432 ou os dados do FR Caixinha 2.2. A inspeção invoca `pg_ctl status` e `pg_isready` conforme o protocolo M38795, e `pg_controldata` quando o estado do processo está inequivocamente compatível com o preflight de servidor parado. O GitHub CI só executa mocks; não acessa o telefone.

## Segurança para a recuperação futura

Não executar `rm postmaster.pid`, `pg_resetwal`, `initdb`, `pg_ctl start` ou limpeza do diretório com base apenas neste pré-diagnóstico. Antes de um procedimento separado de recuperação, exigir confirmação do cluster exato, ausência de processos de outros namespaces, existência de backups restauráveis e integridade física do diretório/WAL. Se o processo antigo foi encerrado abruptamente, o PostgreSQL poderá precisar de recovery durante a partida; executar esse procedimento demanda planejamento explícito.

## Fontes técnicas de referência

- PostgreSQL 18 — `pg_controldata`: https://www.postgresql.org/docs/18/app-pgcontroldata.html
- PostgreSQL 18 — inicialização, lock e PID: https://www.postgresql.org/docs/18/server-start.html
- PostgreSQL 18 — comando postgres e verificação de conflito: https://www.postgresql.org/docs/18/app-postgres.html
