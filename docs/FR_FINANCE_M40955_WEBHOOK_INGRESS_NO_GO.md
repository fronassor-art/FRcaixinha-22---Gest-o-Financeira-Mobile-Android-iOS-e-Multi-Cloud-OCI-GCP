# M40955 — segurança de ingresso Mercado Pago (offline)

Incremento sobre M40954. Payment/Connect e Orders mantêm os contratos
existentes; o parser aceita UTF-8 e rejeita JSON profundamente aninhado,
tipos não textuais em ação/status e identidade divergente. Identificador
de recurso e cabeçalhos são limitados antes de consultar o registro.
A conta resolvida precisa estar explicitamente ativa, pertencer ao
identificador do evento e possuir UUID de tenant antes de ler o segredo.

Testes sintéticos nas suítes M2400/M2900/M4400: nenhuma conexão com
Mercado Pago, Vault, banco original ou rede externa. Não houve alteração
de endpoint implantado, credencial, schema, webhook público ou configuração.

A assinatura HMAC não prova o conteúdo integral do JSON nem liquidação:
o inbox durável, GET autenticado, vínculo independente seller/tenant,
deduplicação e reconciliação permanecem gates externos. O código não
habilita pagamento, Money Out ou PIX, e não declara homologação real.
PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF; PRODUCTION=BLOCKED.
