M23100 — Coordenador OAuth Connect apenas em sandbox, sem rotas públicas.

Fluxo em código: Administrador do tenant inicia PKCE e exige persistência prévia; callback exige consumo único do digest SHA-256 vinculado a tenant, ator, redirect e prazo de 10 minutos, antes do POST ao Mercado Pago; identidade seller vem do servidor, não da URL; tokens só geram metadados depois do sink de Vault informar persistência.

Portas DurableOAuthAttempts e VaultBoundTokenSink AINDA NÃO POSSUEM IMPLEMENTAÇÃO OPERACIONAL OCI. O teste utiliza mocks em memória e não comprova segurança de armazenamento, transação ou consentimento real. Nenhuma rota foi montada, nenhum token de terceiros armazenado, nenhum dinheiro real autorizado. Para disponibilizar: implementar SQL transacional com RLS, Vault por tenant, domínio HTTPS e testes E2E OCI. Nunca enviar tokens para o chat ou GitHub.
