# FR Caixinha AI Studio — M381–M400: auditoria dos dois caixas e Pix

Data: 04/11/2026. Base da auditoria: `1edbdffc34b8b416aa29f27bd5ace38b9268a83b`. PR #2 Draft, sem merge. Projeto AI Studio exclusivo, separado do projeto FRcaixinha 2.2 independente.

## Resposta da auditoria
**Master / plataforma:** migrations 016–017 já criaram preparações SaaS, `saas_payment_intents`, `saas_license_entitlements` e recebimentos de webhook; `backend/app/saas_billing_ci.py` tem conciliação **somente CI**. `master.py` indica `NOT_CONNECTED_TO_RECONCILED_BILLING`. **Não existe caixa empresarial operacional com saldo disponível/receita líquida conciliada, despesas, tarifas e reembolsos completos.** Preço de assinatura é receita empresarial do operador SaaS, nunca pertence à caixinha contratante.

**Tenant / caixinha:** migration 003 cria conta canônica `1.1.1 — Caixa Financeiro Reconciliado` para cada tenant, `1.2.1` crédito a receber, `2.1.1` capital de membros e `4.1.1` receita de juros. A presença de um nome de conta **não comprova liquidez externa, saldo real, reserva disponível, pagamento efetivo ou Pix conciliado**. Contas e lançamentos são isolados por tenant/RLS; falta conta recebedora externa vinculada ao administrador, provas de recebimento/estorno e apropriação da taxa administrativa.

**15%/85%:** em `backend/app/routers/closings.py` há código que calcula 15% do lucro realizado ao administrador da própria caixinha e 85% para seus membros, com Capital-Dias e maiores restos, mas a rota encerra com 503 antes das gravações. **Não está disponível para fechamento real**. O código legado parte de conta 4.1.1 e não prova sozinho lucro líquido após despesas, conciliação ou rateio pós-pagamento.

**Pix/Mercado Pago:** `backend/app/mercado_pago_adapter.py` monta POST /v1/payments e GET /v1/payments/{id}, valida ambiente, recebedor, valor e referência. `mercado_pago_safety.py` confere assinatura HMAC e respostas. **Ainda faltam configuração OAuth multiempresa, provedor testado, webhooks assinados/replay, reconciliação financeira transacional, ciclos de estorno e Pix de saída**. Não há webhook Pix habilitado nem chave de produção para usar.

## Modelo contratual aprovado para desenvolvimento

| Dinheiro recebido | Destino externo pretendido | Registro/conta interna | Regra |
|---|---|---|---|
| Assinatura SaaS de um administrador | **Conta exclusiva do operador da plataforma (Master empresarial)** | Caixa empresarial SaaS **a implementar** | Nunca contabilizar capital ou lucro de caixinha |
| Cota paga por membro | **Conta recebedora do tenant/caixinha correspondente** | 1.1.1 Caixa e 2.1.1 Capital do membro, após conciliação **a implementar** | **Não** incidir 15% sobre a contribuição |
| Juros/mora/multa efetivamente realizados | Conta da caixinha | 4.1.1 Receita realizada; apuração líquida com custos **a implementar** | Integrar pagamentos, custo e auditoria |
| Lucro líquido anual da caixinha (ex.: R$ 10.000,00) | Até apuração: fundo da caixinha; destinação conforme autorização | Taxa administrador: R$ 1.500,00; pool membros: R$ 8.500,00 | 15%/85% sobre lucro **líquido realizado**, não sobre valor de cotas |
| Rateio do pool de membros | Membros elegíveis | Alocação Capital-Dias por maiores restos | Conservação exata de centavos, sem autoaprovação |

**Conta contábil não é conta de pagamento nem carteira bancária do provedor.** Mesmo que o administrador e a caixinha operem sob a mesma titularidade, entradas das cotas, remuneração administrativa e assinatura SaaS precisam de evidências financeiras e responsabilidades distintas. A taxa de administração de ciclo não é o split de marketplace de cada pagamento Pix.

## Código incluído no pacote M400 — somente simulação

- `backend/app/financial_cashboxes.py`: valida rota de recebimento **SaaS Master vs contribuição/parcelas do tenant**, exige conta recebedora correspondente e referência que vincula tenant e obrigação; usa verificador autoritativo existente. Aceitar pagamento em memória **não confirma Pix real**.
- Cálculo `simulate_annual_profit_split` com `Decimal`, centavos inteiros, 15/85, pesos Capital-Dias com quatro casas, maiores restos e desempate determinístico por UUID; rejeita pessoa duplicada, tenant cruzado, lucro negativo e rateio de pool sem membros elegíveis; devolve sempre `simulation_only=True`, `bank_reconciled=False` e `closing_authorized=False`.
- `backend/tests/test_cashbox_segregation_and_profit_ci.py`: monta Pix usando adaptador existente e resposta **mock HTTP**; não envia requisições externas; testa recebedores independentes, Pix pendente, ambiente, idempotência, ausência de comissão sobre cota e exemplo R$ 10 mil → R$ 1.500/R$ 8.500.
- Workflows CI no backend sem banco e PostgreSQL descartáveis 16/18. **Nenhuma migration**, nenhum dado inserido no PostgreSQL 5433, nenhuma API real, nenhuma tela de caixa operacional.

## Mercado Pago: homologação real planejada — SEGMENTADA

1. Criar duas classes de credenciais, **operador SaaS** e **vendedor/administrador de cada caixinha**. Associação dos vendedores requer OAuth e autorização individual; não reutilizar o token Master para cobrar contribuições de empresas diferentes. Credenciais somente backend/gerenciador de segredos.
2. Estágio de sandbox do provedor: validar aplicativo, conta de teste vendedor, testador, capacidade Pix e modalidade **Checkout API Payments /v1/payments ou Checkout API Orders /v1/orders** antes de codificar a rota efetiva. O ambiente oficial oferece fluxos diferentes; não presumir que uma cobrança teste equivale a liquidação real. Consultar documentação e políticas atuais.
3. Requisições Pix autenticadas com idempotência persistente; intents `PENDING`, timeouts, retentativas e expiração. **Não gerar Pix bancário real ou receber dinheiro** sem acordo de ambiente.
4. Webhook público HTTPS validado por assinatura, timestamp/replay, busca GET autoritativa com token da conta correta, checagem de ID, valor, BRL, recebedor, `live_mode`, tenant, obrigação, status, idempotência por pagamento e evento.
5. Para teste fictício, reproduzir **aprovação, rejeição, expiração, duplicação, reembolso e estorno** em base efêmera, com lançamento contábil pareado no mesmo commit transacional e possibilidade de rollback. Jamais classificar webhook isolado como pagamento.
6. Só após testes reais no provedor e autorização jurídica/contratual avaliar Pix de saída, saque/rateio/transferência. Não confundir Split de marketplace com **15% do lucro anual**.

Referências oficiais:
- https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/integration-test/pix
- https://www.mercadopago.com.br/developers/pt/docs/checkout-api-payments/integration-configuration/integrate-pix
- https://www.mercadopago.com.br/developers/pt/docs/split-payments/split-1-1/integration-configuration/integrate-marketplace

## Matriz de pendências ainda abertas para venda na Oracle OCI
- **Alta:** definição de titularidade e autorização de cada conta/empresa, OAuth, endpoint HTTPS, segredo protegido, KYC, consentimentos, provedor, recebimentos e liquidação sem dinheiro real na homologação.
- **Alta:** caixa SaaS persistente com razão empresarial separado e taxa de transação; caixa tenant com ingressos, saídas, receitas líquidas e custo; histórico de reembolsos/chargeback, reserva, contabilidade de passivos e reconciliação banco→razão.
- **Alta:** apuração autorizada do lucro realmente líquido, faltas/inadimplência e contrato do ciclo; rateio 15/85, limites de autoaprovação, centavos técnicos, armazenamento idempotente e prestação de contas.
- **Alta:** reconciliação Pix recebedor/valor/obrigação/status, pagamento parcial, múltiplos pagamentos, estornos, prova de liquidação e movimentação financeira somente com aprovação expressa.
- **Alta:** auditoria RLS/multiempresa ponta a ponta, backup restore off-device, segregação por tenant e prova de ambiente de staging Oracle.
- **Média:** telas de caixa Master e caixinha com filtro, extrato, saldo "não conciliado" e auditoria sem expor patrimônio de terceiros. Concluir somente quando backend e PostgreSQL oferecerem dados reais auditáveis.

**NÃO DECLARAR pendências sanadas com base em testes sintéticos.** Cada etapa requer: requisito contratual, código com autorização, evidência unitária, integração PG real isolada, provedor sandbox, logs sem segredos, ensaio APK, homologação e decisão de implantação. `main` e banco operacional separados.

## Segredos
O proprietário possui token de Mercado Pago. **Não publicar em chat, GitHub, README, arquivo ZIP, screenshots, APK, log ou frontend**. Usar secret manager OCI ou configuração backend restrita; nunca gerar token fictício com privilégios reais nem criar chave sem a conta e autorização no painel do provedor.
