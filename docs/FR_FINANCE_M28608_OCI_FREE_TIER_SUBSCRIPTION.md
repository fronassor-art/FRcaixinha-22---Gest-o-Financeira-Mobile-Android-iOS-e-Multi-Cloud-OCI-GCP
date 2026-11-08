# FR Finance AI Studio — M28608: confirmação de assinatura OCI FREE_TIER

Data: 2026-11-08. Evidência manual recebida de execução Python OCI SDK, Debian PRoot no Android, região `sa-saopaulo-1`.

## Evidência observada

- Consulta: `oci.osp_gateway.SubscriptionServiceClient(cfg).list_subscriptions("sa-saopaulo-1", tenancy)`.
- `SUBSCRIPTIONS_FOUND=1`
- `PLAN_TYPE=FREE_TIER`
- `PLAN_STATUS=NOT_REPORTED` (campo de status não fornecido; **não** confundir com conta suspensa/ativa ou com crédito promocional).
- `OCI_ACCOUNT_TYPE=FREE_TIER`
- `FR_FINANCE_M28608_READ_ONLY=PASS`
- `ACCOUNT_CHANGED=NO`, `BILLING_CHANGED=NO`, `VM_CREATED=NO`.

**Conclusão limitada:** a assinatura examinada permanece identificada como **FREE_TIER**, não PAYG. Esta informação não comprova que os US$ 300 de créditos promocionais continuem ativos, nem liberação de capacidade Compute. O M28606 continua com `OUT_OF_HOST_CAPACITY` nas três configurações A1 2/12, A1 1/6 e E2 Micro.

## Regras operacionais

A Oracle permite somente **uma conta Free Trial ou Always Free por pessoa**; não tentar uma segunda conta gratuita no mesmo titular ou usar dados de terceiro como identidade de fachada para contornar essa restrição. Uma pessoa distinta pode ser titular genuína de sua própria conta com os direitos, as responsabilidades e a autorização correspondentes.

Recursos Always Free de computação devem ser provisionados na **home region** (a conta atual tem home `sa-saopaulo-1`), região que não pode ser alterada após inscrição. Ações pagas, troca de tenancy e criação de novos usuários/contas não estão autorizadas por este checkpoint.

## Infraestrutura e segurança

- Preservar compartment `fr-finance-staging`, VCN `FR Finance`, sem nova VM.
- M28605 confirmou limite 1 virtual vault e 20 versões de chave; ainda nenhum Vault criado.
- PostgreSQL Termux porta 5433 inalterado.
- `FR_FINANCE_REAL_MAIL=OFF`, `FR_FINANCE_REAL_USER_ACTIVATION=OFF`, `PIX_INBOUND=OFF`, `PIX_OUTBOUND=OFF`.
- Teste SMTP Brevo M28500 aprovado isoladamente, sem ligar worker automático.

## Fontes oficiais

- https://docs.oracle.com/en-us/iaas/tools/python/latest/api/osp_gateway/models/oci.osp_gateway.models.SubscriptionSummary.html
- https://www.oracle.com/br/cloud/free/faq/
- https://docs.oracle.com/pt-br/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://docs.oracle.com/pt-br/iaas/Content/GSG/Tasks/signingup_topic-Sign_Up_for_Free_Oracle_Cloud_Promotion.htm

**Status:** M28608 PASS (read-only); nenhuma modificação da conta.
