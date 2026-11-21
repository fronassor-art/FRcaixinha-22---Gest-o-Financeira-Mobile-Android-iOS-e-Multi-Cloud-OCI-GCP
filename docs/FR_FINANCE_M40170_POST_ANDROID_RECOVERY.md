# FR Finance M40170 — Android interrompeu Termux, preparação segura de crash recovery

Data: 15/11/2026. Documento de diagnóstico e gates, não de autorização operacional.

## Última evidência local

- M40160 sincronizado, commit `23dfedc`.
- `pg_ctl status` do PostgreSQL 18 original FR Finance: STOPPED.
- `pg_isready` em 127.0.0.1:5433: NO_RESPONSE.
- `pg_controldata`: `Database cluster state: in production`.
- Espaço livre observado pelo usuário: `AVAILABLE_KB=10574300`, cerca de 10,09 GiB.
- Usuário confirmou que o Android reiniciou o Termux minutos antes.
- API TCP 127.0.0.1:8000: CONNECTION_REFUSED.

O valor `in production` em cluster parado é compatível com desligamento abrupto sem checkpoint de desligamento. **Não prova corrupção** nem sucesso garantido de recuperação, e não prova causa absoluta. A próxima inicialização pode executar redo de WAL e escrever nos arquivos. Esta etapa não inicia nada.

## Observação de segurança do histórico de backup

O script versionado `backend/scripts/frfinance_m39030_pg18_backup_restore_only.sh` declara logo no início estar **obsoleto após M39031**, pois foi elaborado para um esquema de 47 tabelas, enquanto o histórico após migrações 110/111 registra 53. A existência de artefatos M39030 não comprova backup atual do banco de FR Finance. Não executar esse script de backup/restore; não assumir restauro atualizado.

## M40170 — inspeção de metadados

- Autentica apenas a estrutura estática FR Finance, PG18 original, porta 5433 e Termux nativo.
- Só lê o estado resumido de `pg_ctl status`, `pg_isready` e `pg_controldata` usando os guardas M40150/M40160.
- Observa entradas de `pg_wal` por nomes e metadados (até 4096 entradas, sem abrir o conteúdo de WAL), distingue ausência de arquivos de existência de arquivos de segmento. Presença **não significa validade nem completude**.
- Observa se `pg_tblspc` contém ponteiros para tablespaces externos (até 512 entradas); se contiver, bloqueia cópias que ignorem esses dados.
- Classifica o espaço livre sem prometer que há espaço para snapshot físico, pois o tamanho do PGDATA e volume de WAL não foi aferido.
- Reconfirma que o PostgreSQL não foi iniciado durante a verificação.
- Nunca apresenta PIDs, credenciais, dados financeiros, nomes de WAL nem DSNs.

Mesmo que todos os itens passem, `POST_MIGRATION_BACKUP=NOT_ATTESTED`, `WAL_INTEGRITY=NOT_ATTESTED`, `PG_START_AUTHORIZED=FALSE` e `FASTAPI_START_AUTHORIZED=FALSE` permanecem. O código de saída 2 é deliberado.

## Decisão operacional separada

Recomendação: preservar previamente um snapshot físico seguro do PGDATA original e tablespaces, preferencialmente em mídia externa ou destino com capacidade suficiente. Um snapshot offline de um cluster interrompido também terá estado de crash e pode necessitar replay de WAL; **não** equivale a um backup lógico validado nem garante recuperação.

O início controlado da instância original (sem `initdb`, sem `pg_resetwal`, sem migração, sem reiniciar FR Caixinha 2.2) deverá ocorrer somente com autorização explícita, revisão dos limites de armazenamento e backup/preservação. Iniciar o PG18 pode alterar seus arquivos; depois validar a identidade autenticada em transação de leitura e só então revisar o FastAPI.

Operações reais sempre OFF: `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `PRODUCTION=BLOCKED`.
