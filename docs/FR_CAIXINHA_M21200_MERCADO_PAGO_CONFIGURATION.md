# M21200 — Configuração Mercado Pago / Pix — ambiente seguro de testes

## Decisão técnica
A integração FR Finance é multi-tenant. Cada administrador vincula sua própria conta recebedora por OAuth Connect; credencial do aplicativo do Master NÃO serve como conta de recebimento de todos os tenants. Receitas de assinaturas da plataforma são processo separado do fluxo de contribuição das caixinhas. A taxa de 15% sobre lucro anual não significa comissão de checkout por pagamento.

## Painel oficial Mercado Pago
- https://www.mercadopago.com.br/developers/panel/app
- Criar aplicação, nome FR Finance, Pagamentos online, sem plataforma externa, Checkout Transparente / Checkout API (Orders), Marketplace quando aparecer.
- Após criar, obter Client ID/ID da aplicação, Client Secret e credenciais de Teste e Produção. NÃO copiar Client Secret ou tokens para ChatGPT/GitHub/prints.
- Para Pix de entrada: a conta recebedora deve possuir chave Pix e habilitação de pagamento; Orders API recomendada. Nunca criar cobrança real só para testar conexão.
- Para cada tenant, OAuth authorization-code + state + PKCE, callback HTTPS estático e scopes read/write/offline_access conforme capacidade aprovada. URL de callback será definida na etapa OCI; nunca usar localhost/Termux como callback público.
- Webhooks Orders: endpoint HTTPS público distinto por ambiente, tópico Order (Mercado Pago), assinatura secreta x-signature, idempotência e consulta GET autenticada; ainda pendentes da OCI.
- Pix de saída / Money Out requer liberação comercial, assinatura e escopo independente. **Não habilitar automaticamente**.

## Configuração local (somente teste)
Após criar aplicação, com Client ID e Access Token de TESTE disponíveis:
`export AI_STUDIO_APPROVED_SHA=<SHA EXATO APROVADO>`
`python3 backend/scripts/aistudio_mp_credentials_local.py store-test`
O token é recebido por entrada oculta e cifrado com AGE em
`~/.config/frcaixinha-aistudio-mobile/mp-sandbox-credentials.json.age`
com permissão 0600. Nenhum arquivo claro, repositório, API, APK ou log recebe o token. A senha AGE deve ser guardada pelo operador. O script não conecta Mercado Pago e não habilita pagamentos. Auditoria: `python3 backend/scripts/aistudio_mp_credentials_local.py audit`.
**Apenas presença e cifragem do arquivo, sem prova de token válido**. A autenticação TESTE no endpoint Orders foi verificada pelo operador no Termux em 06/11/2026 (M21500). Vínculo OAuth de cada caixinha, Vault e homologação OCI permanecem pendentes.

Não colocar Client Secret nem credenciais de produção no Termux; futuramente usar OCI Vault com políticas restritas e Instance Principal. Não executar a migração 044 novamente; ela já foi comprovada pelo operador com 46 tabelas.
