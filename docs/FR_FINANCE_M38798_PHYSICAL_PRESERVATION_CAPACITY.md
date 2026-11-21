# FR Finance — M38798: dimensão do cluster e capacidade de preservação física (somente leitura)

## Evidências reais recebidas em 11/11/2026

O Termux sincronizou `83751c0`, com **12.722 testes aprovados**, 130 ignorados, um aviso e nenhuma falha. O diagnóstico local M38797 relatou:

- `PROJECT=FR_FINANCE_AI_STUDIO` e `PGDATA_IDENTITY=FR_FINANCE_PG18_ONLY`
- `CONTROL=UNCLEAN_OR_RUNNING_STATE_REPORTED`
- `WAL_DIRECTORY=SEGMENT_FILES_OBSERVED_UNVERIFIED`
- `TABLESPACE_POINTERS=NO_EXTERNAL_POINTERS_OBSERVED`
- `STORAGE_FREE=FROM_4_TO_16_GIB`
- `WAL_INTEGRITY=NOT_ATTESTED`
- `RESTORABLE_BACKUP=NOT_ATTESTED`
- `RECOVERY_PERMISSION=NOT_GRANTED`

Essas informações mostram que alguns nomes de segmentos WAL estão presentes e que existe espaço livre, mas não provam que os arquivos estão íntegros, que o cluster possa ser recuperado ou que exista uma cópia válida.

## Objetivo e limites

O script `backend/scripts/frfinance_m38798_cold_snapshot_capacity_readonly.py` estima o tamanho **lógico não comprimido** dos arquivos regulares do diretório PostgreSQL **exclusivo do FR Finance**, sem abrir seus conteúdos ou consultar qualquer tabela. Também estima o espaço livre pelo filesystem de origem. Compara esse espaço a uma reserva operacional conservadora de **120% do tamanho lógico + 2 GiB**.

O programa **não faz backup** nem seleciona automaticamente um destino, não copia nem compacta arquivos, não valida checksums do WAL, não remove `postmaster.pid`, não executa `pg_ctl start`, não faz reparo, não aplica migrações e não acessa a porta 5432 do FR Caixinha 2.2.

A classificação `ON_DEVICE_SPACE_CANDIDATE_ONLY_NO_BACKUP_APPROVAL` significa apenas que a capacidade numérica parece suficiente para considerar uma cópia *no mesmo armazenamento*. **Uma cópia no mesmo telefone não protege contra perda ou falha do dispositivo e não substitui uma cópia externa confiável.** Mesmo com espaço suficiente, o backup, a consistência e a restaurabilidade continuam não atestados.

`ON_DEVICE_UNCOMPRESSED_CAPACITY_INSUFFICIENT` indica que não há espaço livre estimado suficiente, conforme a margem adotada. `SYMLINKS_PRESENT_REVIEW_REQUIRED` indica algum link simbólico dentro do PGDATA que requer revisão do alcance do backup antes de copiar.

Os testes sintéticos do GitHub garantem que a execução de referência não acessa diretórios reais, que nenhuma operação de escrita é implementada, que o identificador do projeto e o estado interrompido são conferidos antes da leitura, que links não são percorridos e que mudanças de estado durante o scan interrompem o procedimento.

## Execução local

Depois de sincronizar os commits da mesma branch do FR Finance:

```bash
cd "$HOME/fr-finance"
python backend/scripts/frfinance_m38798_cold_snapshot_capacity_readonly.py offline
python backend/scripts/frfinance_m38798_cold_snapshot_capacity_readonly.py local AUTHORIZE_FRFINANCE_PG18_SNAPSHOT_CAPACITY_READONLY
```

O modo `local` exige consentimento para consultar metadados de arquivos no diretório exclusivo do FR Finance. A leitura pode percorrer muitos arquivos e levar mais tempo do que testes sintéticos. Não requer senha e não acessa dados de negócio.

## Próxima etapa de recuperação

Após obter `M38798_PGDATA_LOGICAL_MIB`, `M38798_DESTINATION_UNSELECTED_FREE_MIB`, `M38798_PLANNED_CAPACITY_MIB` e `M38798_CAPACITY_DECISION`, será possível propor um plano de **preservação física em um destino separado**, com manifesto, hashes e conferência de espaço e permissões. A execução de backup e qualquer tentativa posterior de recuperação precisam de autorização explícita e de um procedimento novo, específico e revisado. Não executar diretamente comandos genéricos de exclusão do PID ou `pg_resetwal`.

### Referências PostgreSQL 18

- Cópia de arquivos com servidor desligado e necessidade de cópia completa do cluster: https://www.postgresql.org/docs/18/backup-file.html
- WAL, continuidade e recuperação após falhas: https://www.postgresql.org/docs/18/continuous-archiving.html
- `pg_controldata` e estado do cluster: https://www.postgresql.org/docs/18/app-pgcontroldata.html
