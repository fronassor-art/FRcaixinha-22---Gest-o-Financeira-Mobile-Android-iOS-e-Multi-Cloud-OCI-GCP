# Backup do banco FRcaixinha no Termux

Estado: procedimento preparado e ensaiado somente em PostgreSQL descartável no GitHub Actions. Não restaura o banco real do celular.

Use um banco e diretórios próprios deste projeto. Instale no Termux PostgreSQL, cliente `pg_dump/pg_restore` da mesma família de versão do servidor e `age`; confira `psql --version`, `pg_dump --version`, `age --version` e `node --version`. O CI usa PostgreSQL 16, Python 3.11, Node 22 e Java 21; essas versões não comprovam compatibilidade do ambiente local.

1. Guarde a identidade `age` fora do repositório, com permissões de dono. Gere-a no ambiente do proprietário e faça uma cópia protegida independente. Nunca coloque a chave privada, senha ou backup no Git.
2. Configure `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE` e `PGPASSWORD` no processo local, sem imprimir o valor. Confirme que `PGDATABASE` aponta ao banco FRcaixinha dedicado. Configure `AGE_RECIPIENT` com a chave pública e `BACKUP_OUTPUT` com um caminho novo terminado em `.age`, fora do clone.
3. Execute `bash backend/scripts/backup_age.sh`. O script usa `pg_dump -Fc`, cifra a saída com `age`, falha se o arquivo já existir e remove arquivos parciais. Restrinja o acesso ao diretório de backups.
4. Teste periodicamente restauração em **outro** banco descartável e compare contagens, referências, ledger e integridade. O script `restore_disposable_ci.sh` aceita somente `frcaixinha_restore_ci` em localhost. O workflow realiza esse ensaio sem chave persistente e sem publicar artefato.

Após restaurar um snapshot antigo, mantenha o sistema em modo de reconciliação: consulte o provedor por canal autenticado para cada operação pendente ou posterior ao backup; compare `provider_payment_id`, operação econômica, recebedor, valor, moeda e status; reimporte eventos idempotentemente e só então reabra gravações. Um backup anterior a pagamento confirmado **não autoriza novo Pix** nem baixa com base apenas no snapshot. O ensaio do CI valida recuperação de dados sintéticos, não esse procedimento externo de reconciliação.
