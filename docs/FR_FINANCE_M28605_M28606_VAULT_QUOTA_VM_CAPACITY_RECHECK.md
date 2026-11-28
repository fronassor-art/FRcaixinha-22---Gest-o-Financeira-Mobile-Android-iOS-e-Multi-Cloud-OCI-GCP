# FR Finance AI Studio — M28605–M28606: Vault quota and VM capacity recheck

Registros apresentados pelo operador em **2026-11-08**, Debian PRoot/OCI CLI, região **sa-saopaulo-1**, única AD descoberta **SA-SAOPAULO-1-AD-1**. Esta é uma transcrição resumida de evidência operacional manual: não é execução ou comprovação da GitHub Actions. Não expõe OCID, chaves ou credenciais.

## M28605 — limites de Vault e Key Management Service (somente leitura)

O OCI Limits API do serviço `kms` retornou:

| Limite | Cota informada |
| --- | ---: |
| `virtual-vault-count` | **1** |
| `virtual-vault-keyversion-count` | **20** |
| `virtual-vault-softwarekeyversion-count` | **20** |
| `virtual-private-vault-count` | 0 |
| `virtual-private-vault-keyversion-count` | 0 |
| `virtual-private-vault-softwarekeyversion-count` | 0 |
| `hsm-cluster-count` | 0 |
| `external-vault-count` | 0 |
| `external-privateendpoint-count` | 0 |

Além disso, M28604 identificou **0 vaults** e **0 segredos** na raiz e no staging. M28605 terminou `FR_FINANCE_M28605_READ_ONLY=PASS`, nenhuma criação ou cobrança por script.

A política do projeto requer, quando houver autorização específica, **um Vault padrão DEFAULT no compartment `fr-finance-staging`**, com chaves master de proteção **SOFTWARE** e sem `VIRTUAL_PRIVATE`. Mesmo recursos anunciados como Always Free precisam ter tipo, região, regras IAM e consumo efetivo conferidos antes de criar. Nunca introduzir segredos no GitHub, chat, APK ou cadastro público.

## M28606 — nova consulta de capacidade física

O comando OCI `compute compute-capacity-report create` produz **somente relatório**, não cria VM. A consulta na região/AD já confirmada retornou:

| Configuração | Resultado |
| --- | --- |
| `VM.Standard.A1.Flex`, 2 OCPUs, 12 GiB | `OUT_OF_HOST_CAPACITY` |
| `VM.Standard.A1.Flex`, 1 OCPU, 6 GiB | `OUT_OF_HOST_CAPACITY` |
| `VM.Standard.E2.1.Micro` | `OUT_OF_HOST_CAPACITY` |

Saída final: `FR_FINANCE_M28606=PASS`, `VM_CREATED=NO`, `OCI_VAULT_UNCHANGED=YES`, `PIX_REAL=OFF`.

**Interpretação:** M28601 demonstrou cotas A1 de 2 OCPUs/12 GiB e E2 Micro 2 unidades livres, mas há **falta de host físico nas três configurações**, na hora da consulta. Não é erro de autenticação ou quota, não é autorização de cobrança nem licença para `instance launch`. A Oracle descreve a ausência de capacidade como dinâmica; não há garantia de prazo ou de sucesso em tentativas futuras.

Os relatórios foram obtidos sem `fault_domain` específico, opção que já contempla os fault domains, conforme documentação. Não há ganho em repetir incessantemente a mesma consulta.

## Próxima frente operacional sem depender da VM

1. Preparar Vault `DEFAULT` no staging, **somente após consentimento explícito de criação e revisão de custo e políticas IAM**. Até lá, manter M28605 como diagnóstico, sem escrita na OCI.
2. Preparar documentação de conexão segura do backend FastAPI e PostgreSQL remoto, sem abrir 5432/5433 à internet nem afetar PostgreSQL Termux porta 5433.
3. Corrigir o blueprint legado de Terraform antes de uso: atualmente o arquivo `infra/oci/staging/network.tf` define *nova* VCN `10.77.0.0/16`; o operador já possui VCN `FR Finance`. O CIDR da rede real **não foi comprovado** nos resultados recebidos. Reutilizar rede existente apenas após auditoria de CIDR/NSG/route/compartment e novo plano seguro com guards e regressão.
4. Reavaliar capacidade OCI em intervalos moderados ou quando o operador pedir; sem automatizar provisionamento, sem upgrade pago presumido.
5. `FR_FINANCE_REAL_MAIL=OFF`, `FR_FINANCE_REAL_USER_ACTIVATION=OFF`, `FR_FINANCE_PIX_INBOUND=OFF`, `FR_FINANCE_PIX_OUTBOUND=OFF`. Teste SMTP Brevo externo homologado separadamente (M28500), **não** em produção.

## Referências OCI

- https://docs.oracle.com/pt-br/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://docs.oracle.com/en-us/iaas/tools/python/latest/api/core/models/oci.core.models.CapacityReportShapeAvailability.html
- https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/troubleshooting-out-of-host-capacity.htm

**Checkpoint M28606:** consulta de capacidade PASS; todas as shapes testadas sem host; nenhuma VM, Vault ou segredo criado.
