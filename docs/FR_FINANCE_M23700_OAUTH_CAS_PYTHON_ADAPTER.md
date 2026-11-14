# M23700 — Adaptador Python de consentimento OAuth ao CAS SQL

Nova classe StagingSellerCASRegistry, implementação isolada da interface SellerRegistry prevista pelo M23500. Com conexão PostgreSQL asyncpg **injetada** (não criada automaticamente), chama exclusivamente as funções SECURITY DEFINER do SQL 046 (M23600): mp_staging_oauth_eligible, mp_staging_oauth_activate, mp_staging_oauth_fail_pending e mp_staging_oauth_active_ref.

Controles de bloqueio por padrão: exige enabled=True explicitamente, banco frcaixinha_staging, session_user frcaixinha_mp_oauth_worker, PostgreSQL 18, porta TCP válida diferente de 5433. Confere UUIDs, seller ASCII numérico, formato de revisão e hash SHA-256 antes de consultar funções SQL. Erros de banco retornam bloqueio sem expor credenciais; a consulta active_credential_ref somente devolve referência opaca ao servidor, nunca ao cliente.

Testes com conexões simuladas cobrem sucesso, revogação, conflito CAS, isolamento de tenant, porta 5433 proibida, versão/usuário/banco errados, fingerprints inválidos, bloqueio por padrão e indisponibilidade do banco.

Não foi criado nenhum endpoint público, provedor de tokens, banco, conta Oracle ou configuração de pagamento real. A interface ProtectedCredentialStore ainda necessita implementação protegida que grave e vincule a revisão PENDING usando mp_staging_oauth_stage e generation; sem ela, StagingOAuthTokenSink permanece não operacional. A emissão legítima e auditável de consentimento também está pendente. Não executar migrations de staging no Termux.
