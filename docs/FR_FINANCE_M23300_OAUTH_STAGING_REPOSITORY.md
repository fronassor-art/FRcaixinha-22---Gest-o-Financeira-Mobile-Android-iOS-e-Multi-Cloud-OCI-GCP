# M23300 — Adaptador de staging OAuth com referência PKCE no Vault

Complementa M23100 e M23200, sem ativar endpoints nem operações reais. O retorno do usuário fornece o state em texto ao servidor; o banco guarda só hash do state e referencia o segredo PKCE pelo OCID da OCI. A função de consumo do PostgreSQL deve fazer UPDATE condicional único antes da leitura do segredo. O adaptador reconstitui o OAuthDraft em memória, confere o desafio PKCE e revoga a referência efêmera antes da troca de token.

As três dependências são explicitamente injetadas: conexão PostgreSQL de worker isolado, serviço Vault de verificador efêmero e registro autorizado de seller por tenant/admin. Nenhuma delas é criada automaticamente e o adaptador nasce disabled. Verifica nome exato do banco frcaixinha_staging, usuário frcaixinha_mp_oauth_worker e PostgreSQL 18. A conta local do Termux jamais é aceita.

Os testes M23300 simulam banco, Vault, seller e HTTP Mercado Pago. Verificam replay, acesso cruzado entre tenants, versão/papel incorretos, segredo ou challenge inválido, compensação do Vault após erro SQL e ausência de tokens/verifier em queries. Nenhum teste se conecta à OCI ou a uma base operacional.

Próximas pendências: implementar oficialmente a escrita/leitura/revogação de segredo efêmero em OCI Vault; garantir atomicidade DB/Vault; vincular seller com estado de consentimento persistido e RLS; executar E2E em OCI com HTTPS e callback registrado, além de backups. Pagamentos e repasses reais seguem OFF.
