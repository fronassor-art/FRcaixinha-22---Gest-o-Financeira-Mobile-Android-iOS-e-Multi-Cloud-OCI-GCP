# FR Caixinha AI Studio — Supermacropacote M4100–M4800

**Escopo:** SaaS de gestão financeira automatizada (não é banco, custodiante ou instituição financeira). Trabalho exclusivo no repositório AI Studio. Nenhuma alteração no repositório antigo FRcaixinha 2.2.

**Base Git:** `673e87065bdc4fbeba600091807f51b8fd240152`.
**Commit de implementação:** `b48baaae522bd20e9fe712668452769cf3ac6403`.
**Branch:** `atualizacao-ai-studio-9b46a63187`.
**PR #2:** manter Draft e sem merge. **Issue #3:** manter pendências financeiras e infraestrutura abertas.

## Integração oficial Mercado Pago — Brasil (MLB)

- **Pix IN:** preferir Checkout Transparente **Orders API** `POST /v1/orders`, `GET /v1/orders/{order_id}`. Requisição de pagamento: `type=online`, `processing_mode=automatic`, `total_amount` e `transactions.payments[0].amount` como decimal BRL exato em string, `payment_method.id=pix`, `payment_method.type=bank_transfer`, e-mail do pagador obtido do backend e `X-Idempotency-Key` estável por obrigação/tentativa. Não enviar `notification_url` no corpo: configurar tópico `Order` no portal.
- **Pix aguardando pagamento:** `status=action_required`, `status_detail=waiting_transfer`; transação `PAY...`, order `ORD...`. QR code e código Copia e Cola são retornados por `transactions.payments[].payment_method`.
- **Order processada:** `processed/accredited` no GET externo autenticado é requisito para pesquisar a conciliação, mas **não é prova bancária independente nem libera ledger por si só**. Necessário cruzamento com extrato/prova externa e operações idempotentes de DB.
- **Webhook Order:** verificar `x-signature` HMAC, `x-request-id`, `data.id` e `type=order`, vínculos de conta e payload; gravar em inbox durável; nunca baixar capital com o evento assinado isoladamente. Receber `200` após persistência.
- **Connect OAuth:** `authorization_code`, PKCE/state, `offline_access`, renovação de access + refresh token com rotação conjunta no Vault por conta/tenant; revogação bloqueia novas operações.
- **Money Out:** `POST /v1/transaction-intents/process`, `PSP_TRANSFER` no perfil avaliado para Brasil. Necessário aceite comercial do produto, análise específica de desembolso de empréstimos e assinatura autenticada do body em produção. **Este pacote proíbe a criação de Payouts produtivos sem assinatura**, mesmo com flags de conta true. Não presume que `approved` equivale a liquidação.

Documentação oficial verificada:
- https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-integration/websites/pix
- https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/notifications
- https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/integration-model
- https://www.mercadopago.com.br/developers/pt/docs/security/oauth/creation
- https://www.mercadopago.com.br/developers/pt/docs/security/oauth/renewal
- https://www.mercadopago.com.br/developers/es/docs/payouts/integration-configuration/money-transfers

## Checklist — código entregue neste commit, sem dinheiro real

- [x] M4100 — serializador de Orders Pix Brasil, com valores BRL sem float e chave de idempotência.
- [x] M4100 — parser de resposta ORD/PAY, status action_required/waiting_transfer e QR original do PSP.
- [x] M4100 — GET Orders autenticado, com estados processed/accredited **sem baixa**.
- [x] M4100 — validação de conta conectada, referência, moeda contextual Brasil, valor, único pagamento e status.
- [x] M4100 — testes com HTTPX MockTransport, provedor errado, valor errado, método não Pix, estados inválidos e bloqueio de rede real.
- [x] M4200 — contrato de conta autorizada OAuth por tenant, role de administração e offline_access.
- [x] M4200 — CAS de versões de segredos/token no Vault via porta de repositório, fingerprints SHA-256 e escopo de tenant.
- [x] M4200 — bloqueio de renovação após revogação e teste de troca de tokens.
- [x] M4300 — matriz de gates comerciais/jurídicos de Money Out + titularidade da chave/destinatário.
- [x] M4300 — bloqueio explícito da API de Money Out em produção sem assinatura homologada.
- [x] M4300 — requisição de sandbox com X-enforce-signature=false; dados de Pix/CPF nunca em logs.
- [x] M4400 — parser isolado de webhook Orders HMAC e vínculo entre Order e conta Mercado Pago.
- [x] M4400 — endpoint ASGI factory de staging, com limite de 16 KiB, rejeição de duplicatas e HMAC.
- [x] M4400 — replay idempotente em inbox, sem capital/contabilização no processamento do webhook.
- [x] M4500 — migração `036_signed_orders_inbox_staging_only.sql` guardada e separada do Termux.
- [x] M4500 — adaptador PostgreSQL específico para inbox de Orders (função de append restrita ao worker).
- [x] M4600 — contrato de orquestração da cobrança Orders e idempotência de criação.
- [x] M4600 — preflight de 3 fontes: obrigação, GET Orders, prova externa de extrato; imputação de crédito obrigatória.
- [x] M4600 — prevenção de repetições após timeout e definição de recibo com Order/PAY/ledger.
- [x] M4700 — extensão `037_orders_payment_link_staging_only.sql` para vincular IDs ORD/PAY às intenções/comprovantes.
- [x] M4800 — frontend valida `ORD...`, `PAY...`, `action_required/waiting_transfer` e QR oficial, sem marcar pago.
- [x] M4800 — comprovante no frontend exige order_id compatível com a cobrança e prova do servidor.
- [x] M4800 — rota de saúde separada no FastAPI para evidenciar código implantado e dinheiro real ainda bloqueado.
- [x] M4800 — testes backend e frontend incluídos no GitHub Actions.
- [x] Preservação — Payments API legada não é removida silenciosamente nem confundida com Orders.
- [x] Preservação — nenhuma migração staging executada e nenhum dinheiro movimentado.

A marca `[x]` significa **código versionado e cobertura de CI**, não funcionalidade externa homologada, salvo declaração expressa.

## Checklist — dependências técnicas ainda abertas

- [ ] Ligar o novo `OrdersCollectionAutomation` a um runtime OCI com contas efetivas do Mercado Pago e token específico de cada administrador. Hoje a rota financeira pública retorna HTTP 503.
- [ ] Provisionar infraestrutura OCI real autorizada e segura; configurar TLS/trusted proxy, PostgreSQL staging, IAM/Vault, DNS e observabilidade.
- [ ] Auditar e executar, em staging autorizado e com backup, 034, 035, 036 e 037; atenção aos nomes dos papéis em 034, que não coincidem necessariamente com as roles atuais no Termux.
- [ ] Implementar repositório PostgreSQL transacional efetivo das orders com locks, idempotência entre processos, outbox, RLS, journals e rollback/estorno.
- [ ] Conectar autenticador de extratos externos e provar conciliação de três fontes a partir de dados do provedor e banco; um GET processado sozinho não é dinheiro conciliado.
- [ ] Registrar e gerenciar contas conectadas OAuth efetivas de cada admin em Vault, com PKCE, expiração, refresh-token rotativo e desautorização.
- [ ] Vincular webhook Orders ao servidor staging e à inbox 036; testar replay concorrente, notificação perdida e consulta de recuperação.
- [ ] Integrar recibos financeiros verdadeiros a lançamentos equilibrados de Caixa/Capital/Receita/Juros/Crédito e prova bancária imutável.
- [ ] Implementar atualização transacional de obrigação mensal e estorno não destrutivo após confirmação/reversão.
- [ ] Implementar efetivamente cobrança de prestações, juros, mora simples, multa única, pagamento parcial e amortização por competência, sem inventar parâmetros do tenant.
- [ ] Corrigir aprovação legada que gera parcelas antes do desembolso efetivamente confirmado; usar data real do Pix na Tabela Price e respeitar fim do ciclo.
- [ ] Implementar destinatário Pix do membro com cadastro validado pelo próprio membro/admin, titularidade comprovada, mascaramento e segredo Vault.
- [ ] Implantar reserva atômica do saldo livre, gestão de limite de crédito e consentimentos, idempotência econômica e classificação de timeout ambíguo.
- [ ] Obter homologação comercial de Money Out para conta conectada e especificamente para crédito de terceiros, além de assinatura digital auditada do body e status final por provedor.
- [ ] Validar encargos e estrutura jurídica de crédito para o modelo de SaaS não bancário.
- [ ] Completar telas administrativas de aprovação/recusa, reserva e acompanhamento de desembolso de empréstimo com trilha auditável.
- [ ] Homologar tudo em ambiente de teste **sem dinheiro real**, com testes adversariais, concorrência, reversões e permissões.
- [ ] Executar os 50 cenários de aceite contratuais e homologação mobile com Master/Admin/Membro num APK instalado.
- [ ] Liberar produção apenas após aceites legais/comerciais/de segurança/backup e avaliação de custos; sem essa evidência, permanecer bloqueado.

## Conflitos documentais a regularizar

A matriz histórica de 147 cláusulas registra 5 divergências: 1.6 (demonstração de rifa), 1.8 (Flutter x React/Capacitor), 4.1 (política financeira), 5.3 (suporte) e 8.2 (Price parametrizável até 12 x limite local 6). Decisões explícitas do proprietário em relação à frente AI Studio precisam constar em aditivo documental, sem alterar tacitamente os PDFs históricos nem mudar o repositório antigo.

## Segurança operacional

Nenhum token real, CPF, chave Pix ou senha deve ser inserido em arquivo, terminal público ou CI. Nenhuma pessoa deve inferir que validação de API ou 6/6 do GitHub é homologação do Mercado Pago ou disponibilidade bancária. Não aplicar as migrações 034–037 no PostgreSQL local 5433. O Macropacote M4100–M4800 não executa Pix, não envia empréstimos e não dá baixa real.
