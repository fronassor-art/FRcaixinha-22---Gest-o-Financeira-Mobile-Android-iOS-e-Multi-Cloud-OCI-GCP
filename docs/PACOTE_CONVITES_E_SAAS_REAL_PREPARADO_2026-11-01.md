# AI Studio — Pacote conjunto: convites verificáveis e cobrança/ativação SaaS

**Projeto**: aplicativo exportado do Google AI Studio, PR #2, branch
`atualizacao-ai-studio-9b46a63187`. Esta implementação **não modifica**
o repositório independente de qualquer outra versão do FRcaixinha.

**Decisão vigente do proprietário**: não realizar migrações no Termux.
Última verificação fornecida: PostgreSQL 18.6 `frcaixinha_aistudio_dev`
na porta 5433 com **zero tabelas**. Todos os testes são em PostgreSQL efêmero
ou provedores falsos em memória. Nenhum e-mail, Pix, contratação ou ativação
de licença foi realizado com pessoas/contas reais.

## Entrega A — convite para cadastro e vínculos

Arquivos:
- `018_invite_email_verification.sql`: data de verificação, e-mail único
  normalizado, tabela de prova do link com SHA-256 do token e RLS FORCED,
  revogação/consumo/expiração; nenhum app/auth pode ler tokens.
- `invite_registration_ci.py`: valida titularidade do link entregue,
  CPF com dígitos verificadores, email único, versão contratual,
  situação do tenant e permissão ATUAL do remetente. Cadastro só ocorre
  em transação única: `users`, `credentials` com senha hash,
  `contract_acceptances`, `memberships`, consumo do token, aceite e auditoria.
  **Nunca** pode criar o papel MASTER por convite.
- `platform_provider_adapters.py`: envio SMTP genuíno por TLS/HTTPS,
  com link de uso único. Erro não equivale a convite entregue.
- O fluxo preliminar de administrador, sem tenant ainda criado, permanece
  reservado para contratação segura, não cria tenant por inferência.

**Limitação crítica**: a lógica de cadastro CI exige
`FRCAIXINHA_CI_ISOLATED=1` e uma base `frcaixinha_ci` descartável, na
porta 5432. Os endpoints públicos de convite/aceite NÃO são habilitados
neste pacote. Para o funcionamento real, são necessárias: infraestrutura
SMTP/dominio verificado, servidor HTTPS, identidade real validada,
consentimento explícito e fluxo de ativação segura de tenant preliminar.
Apenas configurar credenciais não autoriza enviar convites.

## Entrega B — cobrança e ativação de licença SaaS

Arquivos:
- `017_saas_payment_activation.sql` cria:
  - `saas_payment_intents` com valor exato em centavos, versão fixa do preço,
    pagador, tenant, conta cobradora da **plataforma**, idempotência,
    referência externa, live_mode e status;
  - `saas_license_entitlements` com `ACTIVE`, `SUSPENDED`,
    `EXPIRED`, `REVOKED`, validade de um mês ou ano civil a partir da
    conciliação;
  - `saas_provider_webhook_receipts` para idempotência/rastreabilidade
    de notificações verificadas.
- `platform_provider_adapters.py`: utiliza a integração Mercado Pago
  existente para criar Pix, consultar pagamento `GET /v1/payments/{id}`,
  validar assinatura HMAC, timestamp, collector, live_mode, referência,
  status e valor exato. Webhook NÃO comprova pagamento sozinho.
- `saas_billing_ci.py`: intenção com preço exclusivamente do banco,
  aprovação idempotente (uma licença por intenção), expiração com
  tolerância zero no instante exato, revogação após reembolso confirmado.
  Nenhum lançamento é realizado no ledger financeiro de membros.
- `GET /api/v1/master/saas-payment-status`,
  `GET /api/v1/tenants/{tenant_id}/saas-payment-status` e
  `GET /api/v1/master/integration-readiness` mostram apenas dados
  autorizados, sem credenciais ou acionamento de cobranças.
- O painel de licenciamento do Master e do administrador exibe o
  status real da API, sem considerar uma preparação como licença ativa.

**Limitação crítica**: a lógica transacional de pagamento/ativação foi
implementada em **laboratório descartável**. A comunicação externa real
está no adaptador e exige variáveis seguras, homologação e autorização.
Não há no aplicativo endpoint público capaz de cobrar/ativar dinheiro
real hoje; a conexão com uma conta real da plataforma e o processamento
autenticado de webhook precisam de liberação e revisão independentes.
Uma assinatura da API Mercado Pago pode ser recorrente via
`/preapproval`, mas esse fluxo difere do Pix unitário implementado nesta
fase. Não declarar renovação recorrente implementada.

## Segurança adicional

- Ambos os motores ficam bloqueados por padrão. O adaptador real exige
  `AI_STUDIO_REAL_INVITES=APPROVED` ou
  `AI_STUDIO_REAL_SAAS=APPROVED`, **além** de
  `AI_STUDIO_LEGAL_CLEARANCE=APPROVED` e
  `AI_STUDIO_OPERATIONAL_REVIEW=APPROVED`.
  **Não definir essas variáveis antes de aprovação expressa do Master.**
- Não armazenar tokens de provedores em JavaScript, logs, banco em claro,
  .env versionado nem GitHub Actions. Usar secret manager no ambiente
  homologado e contas segregadas.
- Os papéis `frcaixinha_app_role` e `frcaixinha_auth_role` não têm
  INSERT/UPDATE nos registros de cobrança/ativação nem acesso aos tokens.
- Nunca misturar cobrança SaaS da plataforma com Pix/caixa/ledger de tenants.
  A receita SaaS não é parte dos 15% de administração das caixinhas.
- O aceite contratual sintético não representa assinatura jurídica real.
- RLS e o timestamp do webhook não substituem teste de concorrência,
  entregas repetidas, observabilidade e análise de incidente.
- A migração `001–018` só é executada em PostgreSQL 16/18 **descartável**
  no CI. Nada é aplicado no banco do Termux.

## Testes acrescentados

- Convite: e-mail confirmado, cadastro de identidade única e contrato,
  CPF, chave única, expiração/revogação, replay, versão documental errada,
  mudança de papel do remetente e conflito de CPF/e-mail.
- Provedor: SMTP falso sem rede, Pix com `httpx.MockTransport`,
  assinatura HMAC válida/inválida, timestamp antigo, confirmação pelo GET,
  valor/collector/referência/live_mode divergentes.
- SaaS: valor congelado R$ 89,90 mensal e R$ 899,00 anual,
  uma intenção pendente, conciliação idempotente, rejeição de pagamento
  insuficiente/falso, validade exata, expiração e estorno.
- Perfis: Master lê apenas a gestão de licenças; administrador
  restringe a própria caixinha; membro não consulta faturamento.
- PostgreSQL 18: valida tabelas vazias e nenhuma ativação durante migração.

## Referências técnicas públicas (Mercado Pago)

- Webhooks/HMAC:
  https://www.mercadopago.com.br/developers/pt/docs/checkout-pro-preferences/payment-notifications
- Consulta autoritativa de pagamento:
  https://www.mercadopago.com.br/developers/pt/reference/online-payments/subscriptions/overview
- API de cobrança recorrente `/preapproval`:
  https://www.mercadopago.com.br/developers/pt/reference/online-payments/subscriptions/create-preapproval/post

## Checklist antes da operação real

1. Confirmar domínio HTTPS do app, SMTP verificado, destinatários e
   regras da LGPD (sem dados reais nos testes).
2. Validar identidade/CPF/aceite jurídicos e fluxos de usuário novo,
   existente e administrador preliminar. Implementar API pública com
   rate limit distribuído e privilégios mínimos do serviço dedicado.
3. Definir conta Mercado Pago **da plataforma** para cobrança SaaS e
   credenciais seguras, separar da integração Connect financeira das caixinhas.
4. Revisar webhooks reais, idempotência distribuída e consulta direta
   ao provedor, reembolso e pagamento contestado.
5. Testar suspensão e expiração por job agendado e conciliação recorrente.
6. Revisão jurídica, segurança independente e autorização operacional
   antes de qualquer cobrança, e-mail enviado ou migração local.

**Não rodar `apply`, não criar conta Master, não ativar flags reais
e não instalar APK.** O commit é apenas avanço de código homologável.
