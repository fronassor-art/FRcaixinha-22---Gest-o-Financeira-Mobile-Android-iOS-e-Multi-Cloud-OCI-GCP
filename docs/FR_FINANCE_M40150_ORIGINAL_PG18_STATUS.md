# FR Finance M40150 — observação do PostgreSQL 18 original sem SQL

Data: 15/11/2026. Continuidade da verificação M40140 no Termux nativo.

## Evidência de entrada

O Termux sincronizou M40140 no commit `400cd20`; `PASS_STATIC_FR_FINANCE_ONLY`, launcher M38801 validado estaticamente, arquivo privado de configuração presente com metadados protegidos, binários localizados e conexão TCP para `127.0.0.1:8000` recusada. Identidade do servidor PostgreSQL ativo e dono do FastAPI não comprovados.

## M40150

Garante primeiro isolamento original com o verificador M38794: worktree `~/fr-finance`, branch AI Studio, manifesto aprovado, `PGDATA=/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18`, `PG_VERSION=18`, porta declarada `5433`. Não autentica nem lê SQL.

Somente depois realiza duas observações pontuais:

- `pg_ctl -D <PGDATA_FR_FINANCE> status` consulta se o controle do cluster reporta processo em execução. O comando é **status**, não **start/stop/restart**. Saídas de PID ou argumentos são capturadas e descartadas.
- `pg_isready -q -t 2 -h 127.0.0.1 -p 5433 -U frc_ai_owner -d frcaixinha_aistudio_dev` consulta disponibilidade do endpoint PostgreSQL por *handshake não autenticado*. Nenhuma senha é usada, nenhuma sessão SQL ou instrução SQL é executada. As variáveis PG* e DSN do ambiente não são encaminhadas ao subprocesso, evitando override do destino.

Em seguida, faz uma conexão TCP curta a `127.0.0.1:8000`, sem HTTP e sem identificar processo.

Estes três resultados isolados não comprovam, por si só, que o listener 5433 pertence ao mesmo cluster controlado por PGDATA. A identidade autenticada do banco permanece **NOT_ATTESTED**, mesmo quando `pg_ctl status` e `pg_isready` retornarem sucesso. Isso é intencional: é proibido inferir identidade de banco de um `pg_isready` sem SQL.

Nenhum PID, senha, corpo HTTP, processo nem conteúdo de `api.env` é impresso. O FR Caixinha 2.2 em porta 5432 não é acessado.

## Gate

O M40150 nunca concede permissão para inicializar/reiniciar FastAPI: `M40150_LAUNCH_AUTHORIZED=FALSE`, `M40150_RESTART_AUTHORIZED=FALSE`; sempre encerra com código 2 em modo local. Se o PG18 estiver parado ou incerto, a única ação é reportar bloqueio, não iniciá-lo. Também não altera credenciais, migrações, porta ou autenticação.

Comando após sincronização segura:

`python -B backend/scripts/frfinance_m40150_original_pg18_status_readonly.py`

Sem SQL, sem operações reais, sem instalação e sem nova instância. `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCTION=BLOCKED`, `DATABASE_WRITES=NONE`, `MIGRATIONS=NONE`, `SERVICE_START_STOP=NONE`.

Próxima etapa: avaliar os sinais e planejar uma recuperação supervisionada apenas depois de identificar precisamente o serviço e cluster originais e obter autorização operacional específica.
