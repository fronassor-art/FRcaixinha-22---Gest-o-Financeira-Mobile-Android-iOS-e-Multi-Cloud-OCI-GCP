# M22100: Pré-voo remoto OCI PostgreSQL 18, somente leitura

Este pacote prepara a auditoria técnica de três roles de autenticação diretamente na futura VM OCI, quando ela estiver disponível. Ainda NÃO existe servidor provisionado.

Valida identidade do banco, servidor PG18, pg_stat_ssl ativo, sessão somente leitura, roles sem SUPERUSER/BYPASSRLS e FORCE RLS em users, credentials, sessions e auth_login_proofs. Verifica grants distintos para app, Auth e verifier. Todos os comandos SQL são SELECT; conexões usam default_transaction_read_only=on, timeout e sslmode=verify-full no DSN.

O operador precisa ativar FR_FINANCE_DB_PREFLIGHT_CONFIRM=READ_ONLY_OCI e configurar os requisitos do M22000, apenas no ambiente remoto. Nenhuma senha, DSN ou token pode ser enviado ao chat ou GitHub.

Mesmo com READ_ONLY_PASS, o resultado não comprova login real E2E, backups e restauração, homologação de pagamentos, isolamento dos tenants nem segurança total. A produção continua bloqueada até as demais provas. O Termux local na porta 5433 não participa deste auditor OCI.
