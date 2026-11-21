# M23200 — OAuth Connect: transações de state em PostgreSQL staging

M23200 adiciona a migração **045 do diretório exclusivo staging**, mantendo as migrações locais 042–044 e o PostgreSQL Termux 5433 intocados. A CI cria um banco descartável chamado frcaixinha_staging na porta 5432 e executa o SQL com guardas de superusuário, nome exato do banco e flag explícita. Nenhuma migração OCI é aplicada automaticamente.

Tabela nova: mp_oauth_attempts_staging, protegida por RLS/FORCE RLS, sem acesso direto para os logins de aplicação, webhook ou OAuth. Guarda somente hash de state, hash do redirect, challenge PKCE, identificador do segredo de verifier armazenável futuramente no Vault, tenant, actor e prazo de até dez minutos. Nunca armazena access_token, refresh_token, code_verifier em texto ou dados de pagamento.

Funções exclusivas para frcaixinha_mp_oauth_worker: iniciar tentativa apenas com administrador ativo pertencente ao tenant; consumir um único estado por UPDATE condicional atomizado (tenant, actor, state, redirect, TTL). CI testa replay, alteração de tenant/ator/redirect e associação de actor não autorizado. O idempotente não se aplica a tentativas de autorização; uma falha exige novo state.

PENDÊNCIA: o adaptador OCI real de repositório + Vault que produz/reconstrói a referência PKCE ainda não está implementado, assim como autenticação da sessão contra o worker, pre-bind e revogação de seller, compensação em caso de falha do Vault, CI e E2E em OCI. Nenhum endpoint foi montado nem pagamento real ativado. Nunca executar este SQL no Termux nem reutilizar a senha "ci-test-only" fora do GitHub Actions descartável.
