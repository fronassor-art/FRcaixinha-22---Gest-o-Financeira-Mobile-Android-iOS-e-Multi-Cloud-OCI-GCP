# FR Finance AI Studio — M28600–M28603: auditoria OCI e indisponibilidade física

**Registro de evidências informadas pelo operador:** 08/11/2026, Debian PRoot no Android, SDK OCI e CLI na região `sa-saopaulo-1`. **Não** é uma atestação automatizada da CI: os dados foram observados em comandos de leitura executados pelo proprietário da tenancy. Nenhum OCID completo, chave API, segredo, token ou credencial é incluído.

## M28600: conta e shapes (read-only)

- Compartment `fr-finance-staging` ativo; VCN nomeada `FR Finance` encontrada na raiz; uma subnet `FR Finance`, disponível, com atribuição de IP público permitida.
- 0 instâncias ativas na raiz; 0 no compartimento de staging.
- AD: `SA-SAOPAULO-1-AD-1`.
- Shape `VM.Standard.A1.Flex` **oferecido**; `VM.Standard.E2.1.Micro` **oferecido**.
- Primeiro diagnóstico de limites retornou 404 por **ordem incorreta dos argumentos** na chamada SDK; corrigido em M28601. A presença do shape no catálogo não comprova capacidade física.

## M28601: quotas de compute (read-only)

| Limite OCI | Definido | Livre | Usado |
| --- | --- | ---: | ---: |
| `standard-a1-core-count` | SIM | 2 | 0 |
| `standard-a1-memory-count` | SIM | 12 GB | 0 |
| `standard-e2-micro-core-count` | SIM | 2 | 0 |

Valores da conta não equivalem a capacidade física de host.

## M28602: rede, imagens e volumes (read-only)

- 1 subnet disponível; atribuição de IP público permitida; 1 rota padrão.
- A varredura das **Security Lists associadas à subnet** não identificou regras de entrada pública para TCP 22, 80, 443, 5432 ou 5433. Essa verificação **não abrange NSGs**, firewall de sistema operacional nem políticas IAM.
- Imagens compatíveis listadas: A1 + Oracle Linux 12; A1 + Ubuntu 19; E2 + Oracle Linux 15; E2 + Ubuntu 22.
- 0 volumes ativos na raiz e no staging; 0 GB usados nesses compartimentos na consulta.
- A existência de rota padrão **não confirma** internet gateway funcional; deve-se auditar o alvo da rota, NSGs e VNIC no momento de provisionamento.
- O CIDR real da VCN FR Finance **ainda não foi conferido** nos relatórios deste checkpoint; não presumir `10.0.0.0/16`.

## M28603: relatório de capacidade física (read-only)

| Shape/configuração | Resultado de capacidade |
| --- | --- |
| A1 Flex, 2 OCPUs / 12 GB | `OUT_OF_HOST_CAPACITY` |
| A1 Flex, 1 OCPU / 6 GB | `OUT_OF_HOST_CAPACITY` |
| E2.1.Micro | `OUT_OF_HOST_CAPACITY` |

Os relatórios foram solicitados para a única AD enumerada com fault domain omitido. **Não houve criação de VM, disco, rede ou mudança de segurança.** O comando `compute-capacity-report create` apenas produz relatório, não provisiona instância.

## Decisões de liberação

1. **Não executar `compute instance launch` nem Terraform apply** sob status negativo. Não trocar região nem fazer upgrade pago por suposição.
2. **Reutilizar VCN `FR Finance` existente somente após auditoria de CIDR, roteamento, NSGs e IAM.** O Terraform legado `infra/oci/staging/network.tf` criaria VCN `10.77.0.0/16`, subnet privada nova e regras isoladas; seu guard `backend/app/oci_staging_plan_guard.py` foi escrito para esses quatro recursos novos. **Não** executar esse blueprint legado no ambiente atual e não modificar o guard silenciosamente.
3. Próximo avanço independente de capacidade: **M28604 inventário somente leitura de Vaults** existentes na raiz e no compartimento staging; não ler conteúdo de segredo. Se nenhum Vault padrão existir, planejar criação apenas após confirmação expressa, documentação do tipo gratuito e controles IAM.
4. A Oracle informa Always Free para chaves protegidas por software e uma franquia de segredos, mas **Virtual Private Vault** não é Always Free. Uma aprovação de recurso gratuito não autoriza criar serviços cobrados.
5. Para recuperar a tentativa de VM futuramente, reconsultar capacidade física; a Oracle indica que falta de host é dinâmica. Não iniciar polling intensivo nem criação automática.
6. APP e banco permanecem fora do OCI; `FR_FINANCE_REAL_MAIL=OFF`, ativação real de usuários OFF, Pix real OFF e PostgreSQL local Termux `5433` preservado.

## Referências oficiais

- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/troubleshooting-out-of-host-capacity.htm
- https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/compute/compute-capacity-report/create.html
- https://docs.oracle.com/en-us/iaas/tools/python/latest/api/key_management/client/oci.key_management.KmsVaultClient.html

**Checkpoint M28603:** testes manuais de consulta **PASS**, provisionamento **BLOQUEADO por capacidade**, serviços financeiros e de e-mail automáticos **OFF**.