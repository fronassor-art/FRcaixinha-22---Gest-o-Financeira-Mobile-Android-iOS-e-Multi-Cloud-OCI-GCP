# M22200 — Webhook de staging OCI não aceita notificação live

A lógica do servidor de homologação M3000 já aceitava ativar a antiga opção accept_live_notifications. M22200 elimina esse caminho perigoso: mesmo quando a variável FRC_MP_ACCEPT_LIVE_NOTIFICATIONS=1 é definida por engano, a inicialização do serviço OCI staging falha.

O servidor segue apenas RECEIVE_ONLY, com Vault e inbox de teste, sem rota de dinheiro real. O registro de uma notificação assinada NÃO marca obrigação paga, não prova settlement, não escreve Livro-Razão e não libera empréstimo.

O teste no GitHub Actions verifica a rejeição de sinalizadores live e que o servidor desabilitado não expõe webhook. Nenhum certificado, Vault, banco OCI ou servidor real foi criado neste pacote.
