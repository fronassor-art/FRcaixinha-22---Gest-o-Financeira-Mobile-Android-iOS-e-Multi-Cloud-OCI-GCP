# FR Finance — M38797, inspeção não destrutiva do WAL e armazenamento

## Evidências recebidas do Termux

No checkpoint M38796, o Termux executou **12.698 testes PASS, 130 SKIP, 1 aviso e 0 falhas**, no commit `d0cf6d8`, e confirmou:

| Campo | Valor |
|---|---|
| `M38796_PROJECT` | `FR_FINANCE_AI_STUDIO` |
| `M38796_PROCESS` | `NOT_RUNNING_REPORTED` |
| `M38796_PORT_5433` | `NO_RESPONSE` |
| `M38796_POSTMASTER_PID` | `PRESENT_UNVERIFIED_STALE` |
| `M38796_PG_CONTROL_STATE` | `UNCLEAN_OR_RUNNING_STATE_REPORTED` |
| `M38796_NEXT_STEP` | `UNCLEAN_CONTROL_STATE_POSSIBLE_WAL_RECOVERY_NO_ACTION` |
| `M38796_OPERATION_ALLOWED` | `NONE` |

A mensagem `in production` do pg_control quando o processo está parado é compatível com interrupção abrupta. **Não é, isoladamente, prova de corrupção, ausência de WAL ou perda de dados.** Se for permitido iniciar o PostgreSQL no futuro, ele poderá executar recuperação automática de WAL e modificar os arquivos do cluster. Nenhuma inicialização foi autorizada neste estágio.

## Novo controle M38797

O script `backend/scripts/frfinance_m38797_wal_storage_preflight.py` realiza leitura restrita ao `PGDATA` histórico e exclusivo do FR Finance:

`/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18`

A inspeção ocorre **somente depois** do preflight M38796, que confere repositório, branch, diretório PostgreSQL, separação do FR Caixinha 2.2, PID não ativo, servidor parado e porta 5433 indisponível. O programa lê metadados do diretório `pg_wal`, identifica apenas a presença de nomes no formato de segmento WAL (sem abrir ou validar o conteúdo), detecta apontadores de tablespaces em `pg_tblspc` e consulta o espaço disponível por `statvfs` em faixas amplas. Repete o preflight M38796 após a inspeção para detectar mudança de estado.

### Possíveis resultados

- `M38797_WAL_DIRECTORY=SEGMENT_FILES_OBSERVED_UNVERIFIED`: existem entradas com nomes compatíveis com segmentos WAL. **Não comprova continuidade, correção ou suficiência de WAL para recuperação.**
- `M38797_WAL_DIRECTORY=NO_SEGMENT_FILES_OBSERVED_REVIEW`: segmentos não observados na inspeção superficial; exige revisão, não autoriza formatação ou limpeza.
- `M38797_TABLESPACE_POINTERS=EXTERNAL_POINTERS_PRESENT_MANUAL_BACKUP_REVIEW`: tablespaces apontam para outro local e um futuro backup deve incluí-los.
- `M38797_STORAGE_FREE`: faixa de espaço livre (`LESS_THAN_1_GIB`, `FROM_1_TO_4_GIB`, `FROM_4_TO_16_GIB` ou `AT_LEAST_16_GIB`); o espaço disponível sozinho **não atesta capacidade suficiente de backup**.

Os controles `M38797_WAL_INTEGRITY=NOT_ATTESTED`, `M38797_RESTORABLE_BACKUP=NOT_ATTESTED`, `M38797_RECOVERY_PERMISSION=NOT_GRANTED` e `M38797_PRODUCTION=BLOCKED` permanecem fixos. O programa não busca nem confirma backups privados: essa etapa requer inventário separado e consentimento para eventual cópia física.

## Comandos locais

Depois de sincronizar a branch do FR Finance:

```bash
cd "$HOME/fr-finance"
python backend/scripts/frfinance_m38797_wal_storage_preflight.py offline
python backend/scripts/frfinance_m38797_wal_storage_preflight.py local AUTHORIZE_FRFINANCE_PG18_WAL_STORAGE_READONLY
```

A modalidade `local` é uma autorização explícita **somente de leitura** para o cluster FR Finance. Não solicita senha, não usa a porta 5432, não abre SQL e não acessa a base FR Caixinha 2.2. Se o WAL estiver em um link simbólico ou diretório incompatível, a inspeção falha em segurança para revisão manual.

## Etapa futura para recuperar o ambiente

Antes de qualquer `pg_ctl start`, eventual remoção de `postmaster.pid`, `pg_resetwal`, restauro, migração 043/044 ou ativação de usuários, exigir pelo menos: identificação do cluster exclusivamente FR Finance, evidência de ausência de outros processos usando o PGDATA, análise do WAL, avaliação de backup físico consistente e restaurável, armazenamento suficiente e autorização explícita para alterar o estado do banco. Uma cópia simples de um cluster em execução pode não constituir backup consistente.

**Nenhuma das operações acima é realizada neste macropacote.**

Referências oficiais:

- PostgreSQL 18, `pg_controldata`: https://www.postgresql.org/docs/18/app-pgcontroldata.html
- PostgreSQL 18, backup de arquivos e WAL: https://www.postgresql.org/docs/18/backup-file.html
- PostgreSQL 18, `pg_resetwal` (último recurso, não permitido neste procedimento): https://www.postgresql.org/docs/18/app-pgresetwal.html
