# FR Finance — M38795, diagnóstico seguro do processo PostgreSQL 18

## Evidências de entrada do Termux

- M38794: 12.632 testes aprovados; 130 ignorados; 1 aviso; 0 falhas.
- Identidade Git e PGDATA: FR_FINANCE_AI_STUDIO, PG18, `frcaixinha_aistudio_pg18`.
- O cluster FR Caixinha 2.2 está em outro diretório (`frcaixinha_2_2_pg18`).
- `M38794_PG_PIDFILE=EXPECTED_PATH_AND_PORT_UNVERIFIED_PROCESS`: existe arquivo postmaster.pid indicando o caminho e a porta 5433, mas o processo ainda **não** está verificado.
- A tentativa anterior de consultar metadados devolveu `M38792_FAILURE_CLASS=CONNECTION_REFUSED`: a porta 5433 recusou conexão naquele momento. Isso não prova ausência de dados nem permissão para iniciar um cluster.

## O que este macropacote faz

Implementa `backend/scripts/frfinance_m38795_pg18_runtime_probe.py`, que só roda a inspeção local após conferir o manifesto e a separação do projeto M38794. A auditoria permite duas ações limitadas:

- `pg_ctl -D <PGDATA_EXATO_FR_FINANCE> status`: apenas verifica o estado do PostgreSQL associado ao diretório correto; sem iniciar, parar, recuperar, migrar ou alterar configuração.
- `pg_isready -q -t 3 -h 127.0.0.1 -p 5433 -U frc_ai_owner -d frcaixinha_aistudio_dev`: consulta de prontidão ao protocolo PostgreSQL, sem autenticação ou SQL. Este passo realiza uma tentativa de conexão *somente* à porta 5433 no loopback. Não solicita nem envia senha.

Além disso, verifica `postmaster.pid` somente por leitura e consulta a existência do PID com sinal zero (não envia sinais de encerramento). A inspeção não consulta o banco 2.2, não usa a porta 5432 e não exibe PID, argumentos de processo, mensagens brutas de `pg_ctl` ou conteúdo de logs.

O relatório distingue: `M38795_PG_CTL` (`RUNNING_REPORTED`, `NOT_RUNNING_REPORTED`, `UNKNOWN` ou `UNAVAILABLE`); `M38795_PG_ISREADY_5433` (`ACCEPTING`, `REJECTING`, `NO_RESPONSE`, `UNKNOWN` ou `UNAVAILABLE`); `M38795_PID_REACHABLE` e `M38795_DIAGNOSIS`. Todos os resultados são indicativos e permanecem em `M38795_CLUSTER_IDENTITY=NOT_ATTESTED`, pois a porta pode atender um processo de identidade ainda não provada.

## Execução segura no Termux

Após sincronização, executar do diretório `$HOME/fr-finance`:

```sh
python backend/scripts/frfinance_m38795_pg18_runtime_probe.py offline
python backend/scripts/frfinance_m38795_pg18_runtime_probe.py local AUTHORIZE_FRFINANCE_PG18_5433_READONLY_PROBE
```

O segundo comando é uma autorização explícita para testar apenas o processo e a prontidão TCP na porta 5433. Não altera banco, não inicia o servidor e não mexe no arquivo `postmaster.pid`.

Se aparecer `POSSIBLY_STALE_PIDFILE_DO_NOT_DELETE`, **não remover o PID file automaticamente**. Antes de permitir qualquer inicialização, examinar com cuidado estado real do processo e dados do cluster; a conclusão de `pg_ctl status` e a existência do PID não devem ser tratadas isoladamente como prova definitiva.

Se aparecer `PG_CTL_RUNNING_BUT_PORT_5433_NO_RESPONSE`, o processo pode usar outra configuração de escuta ou estar em um estado incompleto; **não alterar porta nem arquivos de configuração** com base apenas nesse indicador.

Se aparecer `PG_PROTOCOL_5433_ACCEPTED_CLUSTER_STILL_UNATTESTED`, a porta responde ao protocolo, mas ainda não comprovamos usuário, database nem cluster. A auditoria M38790 de metadados requer autorização separada e confirmação independente de identidade.

## Segurança

Os testes de CI usam substitutos para chamadas de sistema e para `pg_ctl` e `pg_isready`. **Não há acesso ao Termux nem a PostgreSQL real no GitHub Actions**.

Nenhum SQL, migrations, `initdb`, `pg_ctl start/stop`, remoção de arquivos, alteração de senha, OCI, SMTP, Pix ou ativação real fazem parte deste pacote. A produção permanece bloqueada.
