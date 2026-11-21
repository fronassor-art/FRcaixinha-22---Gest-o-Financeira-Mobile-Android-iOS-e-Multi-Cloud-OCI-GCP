# FR Finance AI Studio — M28609–M28610: A2 Flex 1 OCPU / 8 GB

Data: 2026-11-08. Evidência manual do operador em Debian PRoot com SDK/CLI OCI. Região `sa-saopaulo-1`, disponibilidade AD1. Projeto exclusivo **FR Finance AI Studio**, branch `atualizacao-ai-studio-9b46a63187`.

## Decisão de dimensionamento

O proprietário priorizou `VM.Standard.A2.Flex` com **1 OCPU e 8 GB de RAM** para uma implantação inicial 24×7 do FastAPI, PostgreSQL, HTTPS e workers. É uma **hipótese de sizing**, não homologação de carga ou disponibilidade.

## Evidência M28609

- `list_shapes`: A1 e A2 `OFFERED=True`; A4, E3, E4, E5, E6 e Standard3 `OFFERED=False` para a lista solicitada.
- A tentativa de `compute-capacity-report create` para A2 1 OCPU/4 GB retornou `HTTP 400 InvalidParameter`, com texto indicando `Invalid ratio of memory in GB to OCPUs. Current ratio: 2.0. Valid ratio range: 0 - 0`.
- Devido ao `set -e`, a tentativa de 8 GB **não foi executada** nessa etapa.
- Nenhuma instância criada.

## Evidência M28610

- `A2_SHAPE_FOUND=1`; `FLEXIBLE=True`; `BILLING_TYPE=PAID`.
- `MIN_OCPU=1`; `MAX_OCPU=78`.
- `MIN_RAM_GB=1`; `MAX_RAM_GB=946`.
- SDK listou `RAM_PER_OCPU_MIN=0.0` e `MAX=0.0`, inconsistente com a documentação de formas A2.
- Limites no serviço compute: `standard-a2-core-count=8`, `standard-a2-memory-count=96`. **Limite disponível não prova capacidade física de host.**
- Relatório de capacidade para **A2 1 OCPU/8 GB** retornou `HTTP_STATUS=400`, `ERROR_CODE=InvalidParameter`.
- `FR_FINANCE_M28610_READ_ONLY=PASS`, `VM_CREATED=NO`, `ACCOUNT_UPGRADED=NO`, `BILLING_CHANGED=NO`, `PIX_REAL=OFF`.

## Interpretação e custo

Segundo documentação OCI, `VM.Standard.A2.Flex` suporta mínimo 1 OCPU e memória flexível de até 64 GB por OCPU (sujeito a limites totais). Portanto 1 OCPU/8 GB é uma combinação tecnicamente válida. Existe relato público da Oracle Community de conta Free Tier retornando a mesma razão `0-0` em A2 Flex. **Não provar** que upgrade resolverá esse erro: pode envolver restrições do plano, inconsistência de metadados ou comportamento da API. A capacidade de host A2 permanece **NÃO DETERMINADA**.

Preço de referência da lista Oracle Brasil consultada em 2026-11-08: A2 OCPU R$ 0,0732998 por hora, memória R$ 0,0104714 por GB-hora. Para 730 h: processamento `730 * 0.0732998 = R$ 53,51`; RAM `730 * 8 * 0.0104714 = R$ 61,15`; **total R$ 114,66/mês**, computação exclusivamente. Não é tarifa fixa, nem teto; exclui custos adicionais e tributos.

Fontes oficiais:
- https://docs.oracle.com/pt-br/iaas/Content/Compute/References/computeshapes.htm
- https://www.oracle.com/br/cloud/price-list/
- https://community.oracle.com/CustomerConnect/discussion/913146/why-am-i-getting-a-ratio-error-when-creating-an-instance-on-my-free-tier-account
- https://docs.oracle.com/pt-br/iaas/Content/Billing/Tasks/changingpaymentmethod.htm

## Próximo gate

1. Proprietário pode solicitar upgrade da **mesma conta** para Pay As You Go **pela Console**, revisando titular, condição de autorização temporária do cartão, termos e eventual cobrança. **Nenhuma atualização de faturamento foi realizada por este checkpoint.**
2. Após upgrade efetivo e evidenciado por plano `PAYG`, repetir somente o relatório A2 1 OCPU/8 GB. Se `400` persistir, escalar com Oracle Support; não tratar como `AVAILABLE`.
3. Se houver capacidade, antes de `instance launch` verificar orçamento e alerta, quotas operacionais, imagem ARM64, subnet/NSGs, 50 GB boot volume, chaves SSH, IAM e plano de backup. Exigir aprovação separada da criação de recurso pago.
4. Manter PostgreSQL Termux `5433` inalterado, `FR_FINANCE_REAL_MAIL=OFF`, `REAL_USER_ACTIVATION=OFF`, Pix real OFF.

**Status:** M28610 consulta concluída; contrato/preço A2 documentados; capacidade física não confirmada e upgrade ainda não realizado.
