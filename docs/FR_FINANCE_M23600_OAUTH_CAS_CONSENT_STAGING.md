# M23600 — Controle transacional de vínculo OAuth em staging

Escopo: **somente o banco frcaixinha_staging descartável da CI**, migração 046 ainda não aplicada à OCI. Não executar SQL no banco do celular na porta 5433, no backend operacional ou em produção.

Nova tabela mp_oauth_seller_consents_staging: vínculo tenant + administrador + seller, versão de consentimento, registro de revogação, número de geração e referência da revisão ativa. A aprovação deste vínculo no CI é inserida **pelo DBA de teste**, não pela aplicação nem por um callback do Mercado Pago. O emissor autenticado de consentimento ainda falta.

Nova tabela mp_oauth_token_revisions_staging: somente referência protegida opaca e impressões digitais SHA-256. Sem tokens, segredo OAuth ou chave Pix. FORCE RLS e privilégios diretos negados para aplicação, webhook e worker.

Funções SECURITY DEFINER de uso exclusivo do worker de OAuth: (1) consultar elegibilidade; (2) registrar versão PENDING; (3) ativar sob bloqueio da linha de consentimento, verificando administrador ativo, revogação e geração esperada; (4) marcar falha somente da revisão pendente; (5) consultar a referência ativa apenas com consentimento não revogado. A ativação anterior permanece válida quando uma nova revisão falha; revogação impede obter a referência ativa e novas ativações. A unicidade de vendedor entre caixinhas e o índice de revisão ativa previnem registros concorrentes conflitantes.

CI executa: fixture de dois administradores sintéticos, consumo/ativação, replay, conflito de geração, falha e preservação da revisão anterior, vinculação cruzada, e revogação administrativa antes de uma tentativa de ativação. O uso real de muitas conexões simultâneas ainda exigirá teste de concorrência independente.

NÃO existe adaptador operacional de consentimento/CAS conectado ao StagingOAuthTokenSink, nem gravação protegida de tokens no OCI Vault/KMS ou HTTPS configurado. A Oracle, Pix real, ledger e webhooks públicos permanecem OFF. O controle de consentimento é uma fronteira de segurança preparada, não aprovação para dinheiro real.
