# AI Studio M2501–M2600 — Gateway GET em sandbox + projeto isolado OCI

Base Git: `35e3420149744ee1d69cc6f88aaa30f44749c282`. PR #2 Draft; sem merge.

## Entregue em código e testes

- `backend/app/mp_readonly_gateway.py`: GET HTTPS de pagamento por ID (transporte injetado), somente escopo **sandbox** e identidade seller explícita; usa serializador preexistente `mercado_pago_adapter.py`. Limites de timeout, corpo, três tentativas e backoff até 4 segundos para 429/502/503/504/erros de transporte. Rejeita redirecionamentos, status estranho, JSON duplicado, valores e identidades divergentes. Não devolve payload completo nem segredos, não grava ou confirma pagamentos.
- Os testes injetam `httpx.MockTransport`; nenhum teste envia HTTP ao Mercado Pago. Mesmo GET `approved` é `APPROVED_SANDBOX_UNSETTLED`, com `bank_reconciled=false` e `payment_marked_paid=false`.
- `infra/oci/staging/network.tf`: definição Terraform de VCN, subnet privada sem IP público, security list sem entradas e route table sem Internet. Nenhum recurso foi provisionado. **O modelo não tem caminho para HTTPS/webhook externo**, intencionalmente: rede somente inicial, para revisar. Não possui compute, DB, Vault nem balanceador.
- `/api/health/features/m2600`: informa `gateway_unwired=true`, `oci_staging_deployed=false`. Sem rota de consulta real, segredo ou flag de go-live.
- CI: regressões FastAPI/MockTransport e verificação estática de desenho OCI. Terraform CLI/provider ainda requer validação em ambiente apropriado; **não executar terraform apply**.

## Pendências mantidas

A [Issue #3](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/issues/3) continua aberta: OAuth conectado por empresa; tokens em Vault; renovação/revogação; autenticação do seller via estado persistente e RLS; webhook público HTTPS com deduplicação e GET; extrato autorizado; conciliação bancária; ledger; OCI staging provisionado e auditado; APK no aparelho; LGPD e fechamento.

O flag `seller_authorization_checked` do gateway NÃO constitui prova do vínculo sem consulta durável da identidade autorizada. Não ligar este módulo à API pública antes da integração de autorização e cofre.

Para OCI, confirmar compartimento, região, orçamento, revisão de IAM/rede, TLS e recuperação de desastres com o proprietário antes de credenciais ou operações de nuvem. Nunca colocar chaves, tokens, arquivo .tfstate ou OCIDs sensíveis em commit.

Fonte técnica: https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/core_subnet.html
