# Mercado Pago e Pix — preparação, sem dinheiro real

As cláusulas 9.1–9.9 separam receitas da plataforma e recursos de cada caixinha. O adaptador atual só monta requisições e valida respostas sintéticas; não envia Pix, não armazena credencial, não recebe webhooks e não baixa obrigações. Os endpoints financeiros permanecem bloqueados até integração e reconciliação comprovadas.

A documentação oficial atual consultada em 01/11/2026 exige `X-Idempotency-Key` no Pix e descreve `/v1/payments`, assinatura `x-signature` de webhooks e OAuth para autorização de contas conectadas:

- [Pix via Checkout API](https://www.mercadopago.com.br/developers/en/docs/checkout-api-payments/integration-configuration/integrate-pix)
- [Webhooks e assinatura](https://www.mercadopago.com.br/developers/pt/docs/checkout-pro-preferences/payment-notifications)
- [Proteção de credenciais e OAuth](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-payments/best-practices/credentials-best-practices/secure-credentials)

Próximo gate técnico: identidade da conta recebedora por tenant e finalidade, consentimento do administrador, OAuth aprovado pelo provedor, armazenamento cifrado segregado no backend, chave de idempotência estável por obrigação, eventos persistentes, consulta autenticada ao provedor, conferência de recebedor/valor/moeda/referência/status e lançamento atômico uma única vez. Notificação isolada, print ou token não bastam para marcar pago. Timeout exige consulta antes de qualquer nova tentativa. Pix de saída depende de capacidade e aprovação específicas do provedor.

**BLOQUEADO externamente:** credenciais, conta homologada, endpoint HTTPS público, aprovação de finalidade e evidência de capacidade Pix de saída. A chave do proprietário será configurada posteriormente no Termux, fora do código, frontend, APK, logs e relatório.
