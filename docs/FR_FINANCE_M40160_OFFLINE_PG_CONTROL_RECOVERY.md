# FR Finance M40160 — Estado do pg_control original antes de planejar recuperação

Data: 15/11/2026; continuação M40150, commit d24b43f.
PR #2 permanece em rascunho.

## Evidência do Termux M40150

- `M40150_PROJECT=PASS_STATIC_ORIGINAL_FR_FINANCE_PG18`
- `M40150_PG_CTL_STATUS=ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED`
- `M40150_PG_ISREADY_5433=PORT_5433_NO_RESPONSE`
- `M40150_TCP_8000=TCP_CONNECTION_REFUSED`
- Nenhuma senha foi alterada; nenhuma identidade SQL do banco foi consultada.
- A ausência de FastAPI **não prova** que o PG tenha causado sua parada. A causa de ambos permanece indeterminada.

## M40160: somente leitura offline

Antes de inspecionar metadados do cluster:

1. Valida o diretório original FR Finance por M38794: `/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18`, PostgreSQL 18; nunca o FR Caixinha 2.2.
2. Reconfirma que `pg_ctl status` do cluster original informa parado e `pg_isready` de 127.0.0.1:5433 informa indisponível.
3. Confere apenas formato e propriedade do diretório de dados: `PG_VERSION`, `base`, `global`, `pg_wal`, `global/pg_control`. Não enumera nem lê registros, páginas de banco ou WAL. O resultado é **presença estrutural superficial**, não integridade.
4. Se a verificação estática passar e o cluster continuar parado, chama `pg_controldata -D <PGDATA_FR_FINANCE>`. Essa ferramenta PostgreSQL lê os metadados do arquivo `pg_control`, **sem inicializar o cluster**. O script não exibe o resultado bruto, apenas classes conservadoras da linha `Database cluster state`: encerramento limpo, status não limpo/em produção ou desconhecido. Não imprime ID de sistema, WAL, checkpoint ou caminhos.
5. Reconfirma que o cluster permaneceu parado e a porta 5433 sem resposta. Mudança de estado bloqueia a avaliação.

Mesmo o estado `CLEAN_SHUTDOWN_STATE_REPORTED` **não é garantia de integridade**, consistência de dados, existência de backup, compatibilidade de extensões ou segurança para iniciar. `in production` em um cluster parado pode indicar desligamento abrupto e necessidade de análise de recuperação/WAL; nunca iniciar automaticamente com base nessa etiqueta.

### Não executa

`pg_ctl start/stop/restart`, `initdb`, `pg_resetwal`, `pg_rewind`, SQL, migrações, cópia ou correção de WAL, criação de VM, FastAPI, edição de configuração, senha ou qualquer alteração nos dois bancos.

Se a ferramenta `pg_controldata` estiver ausente, houver layout inesperado ou falha no controle, o resultado será BLOCKED — não instalar pacotes automaticamente. Nenhuma conclusão sobre o FR Caixinha 2.2 é feita.

### Execução

Somente no Termux nativo, após confirmar branch, commit e CI:

`python -B backend/scripts/frfinance_m40160_original_pg_control_offline_readonly.py`

Código de saída local 2 é deliberado; nenhuma saída autoriza start ou restart.

Controles `M40160_PG_START_AUTHORIZED=FALSE`, `M40160_FASTAPI_START_AUTHORIZED=FALSE`, `MIGRATIONS=NONE`, `DATABASE_WRITES=NONE`, `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCTION=BLOCKED`.

A próxima decisão operacional será separada, após avaliar o risco do estado do controle, a disponibilidade de backup e a autorização específica para quaisquer mudanças.
