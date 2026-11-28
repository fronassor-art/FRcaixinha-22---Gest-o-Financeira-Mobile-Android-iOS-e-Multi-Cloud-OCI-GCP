# FR Caixinha AI Studio — MACROPACOTE Pix e Empréstimos M3400–M4000

**Repositório:** AI Studio, PR #2 Draft, sem misturar com projeto FRcaixinha 2.2 independente.
**Documento de autoridade:** cláusulas 6.2–6.6, 7.1–7.6, 8.2–8.9, 9.1–9.9 e 16.2/16.3 do Contrato Técnico Mestre; Caderno Mestre, Fase 4 — Pix, Reservas e Conciliação. As cópias históricas no repositório estão identificadas como 2.2; são referência, não projeto anterior autorizado para alteração.

## Centro de controle: o aplicativo

O **membro** consulta a contribuição do mês/competência, solicita Pix associado à obrigação, vê QR e Copia e Cola **somente se o backend recebeu do provedor**, consulta o comprovante gerado após conciliação, simula e solicita crédito, acompanha empréstimos e gera Pix de prestação.

O **Administrador Contratante** consulta a lista de empréstimos, decide conforme política e reserva, verifica o destino pré-cadastrado do membro, inicia no aplicativo a ordem Pix OUT ao Mercado Pago e acompanha se o desembolso foi definitivamente comprovado. O Master não aprova Pix/emprestimos das caixinhas. O app **não gerencia dinheiro por conta própria**: ele comanda o servidor, que usa a conta Mercado Pago autorizada do tenant.

## Arquivos e contratos de código adicionados

- `backend/app/pix_automation_contract.py`: tipos imutáveis em centavos, referência de cobrança estável sem CPF, tipos CONTRIBUTION/LOAN_INSTALLMENT, imputação de dívida juros→mora→multa→principal, destino Pix mascarado, operação única por empréstimo e validação de comprovantes associados à baixa no Livro-Razão.
- `backend/app/mp_pix_execution.py`: cliente HTTPS para criação e consulta de Pix IN em `/v1/payments`, valida conta, valor, ambiente, moeda, referência e `qr_code`; método Payouts de transferência Pix com perfil Brasil `BR_TRANSACTION_INTENTS_PROCESS_V1` (rota `/v1/transaction-intents/process` **sujeita à confirmação de elegibilidade/solução no portal**), idempotência e status não definitivo. **Não foi chamado com dinheiro real**; uso do MockTransport na CI.
- `backend/app/pix_automation_workflows.py`: orquestrador com portas persistentes para reserva, envio, conciliação tripla e comprovantes. No timeout, bloqueia repetição automática e aguarda consulta externa. Data da Tabela Price definitiva vem da **liberação efetivamente confirmada** (8.4–8.5), e somente então o repositório pode gravar cronograma.
- `backend/staging_migrations/035_pix_payment_automation_staging_only.sql`: esquema para destinatários com referência Vault (sem guardar chave Pix/CPF aberta), cobranças, provas bancárias, recibos e ordens de saída, chaves únicas e RLS. **Não aplicada; sem GRANT de escrita ao aplicativo.** Ainda faltam funções auditadas de commit/estorno e testes de migração real em staging.
- `backend/app/routers/pix_automation.py`: rotas FastAPI para cota, parcela, prévia de transferência e comandos de Pix. POST depende de runtime financeiro autenticado e provisionamento verificado; atualmente responde 503, portanto **não realiza operações financeiras reais ou simuladas que alterem saldos**.
- `src/services/pixAutomationBoundary.ts`: validação estrita de código Pix oficial e recibo conciliado; status `pending` nunca é `QUITADA`.
- `src/components/RealPixCheckout.tsx`: QR oficial e Copia e Cola com botão de consulta de comprovante; não há botão de baixa manual.
- `src/components/ContributionsView.tsx`: acionamento por contribuição/competência e mensagem segura em caso de indisponibilidade do provedor.
- `src/components/LoansAutomationPanel.tsx` integrado ao `ServerLoansView`: pedido, prévia do destino, Pix de liberação e Pix de cada parcela pelo próprio app, sem uso de saldo local.
- `src/services/financialApiService.ts`: novos métodos para o backend, sem segredo/token no Android.

## Onde estão os limites reais

| Funcionalidade | Implementação de código | Ativação de dinheiro real |
|---|---|---|
| Pix mensalidade de R$ 150 por competência | domínio + adaptador + tela + rota | Bloqueado: contas/OCI/worker |
| QR oficial e Pix Copia e Cola | leitura e exibição de resposta verdadeira | Bloqueado até API real |
| Webhook e GET de pagamento | M2900/3300 + novo gateway | Bloqueado até endpoint/segredo |
| Baixa e comprovante | modelos + portas + schema staging | Bloqueado até commit atômico e conciliação |
| Simular/solicitar crédito | FastAPI e tela integrada | Pedido condicionado ao banco |
| Aprovar e reservar desembolso | contrato + ordem estável | Bloqueado até reserva transacional |
| Enviar Pix ao membro | gateway Payouts e controle no app | Bloqueado até elegibilidade Payouts |
| Amortizar parcela juros/principal | motor decimal e split em centavos | Bloqueado até prova externa + ledger |
| Cronograma baseado na data real do Pix | orquestrador calcula após confirmação | Bloqueado até worker/DB |
| Reversão/chargeback e devolução | contrato de eventos não destrutivos | Ainda requer execução e testes completos |

**Não interpretar CI verde como dinheiro liquidado ou integração operacional.** Os ports de workflow e o esquema 035 ainda exigem implementação/instalação de repositório PostgreSQL com commits transacionais, validação real de extrato e worker OCI + Vault. Não existem contas bancárias conectadas, nem habilitação Payouts, nem terraforming OCI realizado. Nenhum comando deste pacote executa `terraform apply` ou migra o banco local.

## Próximo gate técnico de liberação

1. Provisionar infraestrutura OCI autorizada, TLS, PostgreSQL staging, roles separados, IAM e Vault.
2. Registrar aplicação Mercado Pago, validar Pix IN + perfil de Pix OUT **para a conta e finalidade** e obter consentimentos reais dos administradores.
3. Implementar e testar repositório atômico com prova autêntica de extrato, RLS, idempotência concorrente, reversões, reservas financeiras e recibo imutável; executar AT-11, AT-16, AT-23, AT-28/29, AT-37 e AT-41 do Caderno.
4. Conectar runtime financeiro sob autenticação servidor/tenant, sem aceitar indicação de conta, estado 'pago' ou valor do HTTP do cliente; conduzir piloto isolado com valores fictícios e aprovação de conformidade antes de produção.
5. Corrigir legado: aprovação atual de empréstimo gera cronograma antes da data real de desembolso; funcionalidade permanecerá pendente até uso do mecanismo de reserva e data efetiva. Rever os detalhes de 1 a 12 parcelas e políticas de cada tenant.
6. Concluir avaliação jurídica/regulatória de crédito, LGPD, termos de aceitação e efetiva disponibilidade do provedor; sem ativação prematura.

## Referências Mercado Pago oficiais consultadas

- https://www.mercadopago.com.br/developers/pt/docs/checkout-api-payments/integration-configuration/integrate-pix
- https://www.mercadopago.com.br/developers/pt/docs/payouts/resources/api-endpoints
- https://www.mercadopago.com.br/developers/es/docs/payouts/integration-configuration/money-transfers
- https://www.mercadopago.com.br/developers/pt/docs/payouts/resources/transaction-status-and-errors

No Brasil existem APIs/famílias distintas de Payouts; **confirmar endpoint, contrato de payload e elegibilidade na conta de cada caixinha**. `approved` não é sempre dinheiro entregue. O desenvolvimento pode avançar sem cadastrar agora token, chaves ou conta real.
