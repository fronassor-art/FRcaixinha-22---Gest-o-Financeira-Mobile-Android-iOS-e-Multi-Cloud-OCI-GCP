# M22700 — Conexão OAuth por administrador: contrato de escopos e PKCE

O Pix M21500 foi homologado com token TESTE da própria aplicação. Isso não equivale a conectar a conta de cada administrador da plataforma. OAuth Connect requer consentimento do titular, URL de callback HTTPS registrada no painel, state/PKCE de uso único ligado a tenant e sessão, persistência atômica em banco e token cifrado em Vault.

M22700 endurece o adaptador existente: tokens de teste sem os escopos read e offline_access (ou com escopos duplicados/desconhecidos) são recusados. Um draft de callback falsificado com localhost, porta não HTTPS padrão ou domínio interno é rejeitado mesmo que tenha sido construído manualmente. Testes mockados cobrem duas caixinhas com estados e administradores distintos.

A documentação oficial confirma Authorization Code para terceiros, PKCE recomendado, refresh_token e prazo de código de até dez minutos:
https://www.mercadopago.com.br/developers/pt/docs/security/oauth/creation
A permissão offline_access deve estar habilitada nas configurações da aplicação MP.

Nenhum fluxo OAuth público foi ativado, nenhum token real de administrador foi cadastrado, nenhum webhook foi registrado e nenhum dinheiro real foi movimentado. A conclusão operacional depende da OCI com domínio, banco, Vault e consentimento dos administradores.
