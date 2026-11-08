# FR Finance AI Studio — M28604: inventário OCI Vault sem segredos

Evidência informada pelo operador em 08/11/2026 após executar auditoria de leitura com o SDK OCI Python em Debian PRoot (Android). Região `sa-saopaulo-1`. Projeto exclusivamente **FR Finance AI Studio**, sem misturar com FRcaixinha 2.2.

## Resultado observado

| Compartimento | Vaults listados | Metadados de segredos listados |
| --- | ---: | ---: |
| Raiz da tenancy | 0 | 0 |
| `fr-finance-staging` | 0 | 0 |

Saída final observada: `FR_FINANCE_M28604_READ_ONLY=PASS`, `VAULT_CREATED=NO`, `SECRET_CREATED=NO`, `SECRET_VALUES_READ=NO`, `VM_CREATED=NO`, `PIX_REAL=OFF`.

Limitação da prova: inventário restrito a **raiz e staging**, não uma afirmação sobre qualquer possível compartimento adicional, nem comprovação de inexistência de segredos fora da OCI.

## Política aprovada para próximo passo (não é autorização de escrita)

1. **M28605:** conferir limites da tenancy relativos ao serviço `kms` (Virtual Vault e Vault Privado) e à gestão de segredos, sem criar recursos.
2. Para o projeto, avaliar **Vault de tipo `DEFAULT`**, display name `fr-finance-staging-vault`, criado no compartment `fr-finance-staging` com região `sa-saopaulo-1`. **Não criar** com este checkpoint; submissão de criação exige comando e consentimento operacional separados.
3. OCI Always Free prevê chaves master **SOFTWARE** gratuitas, 20 versões master HSM grátis e até 150 segredos em toda a tenancy (limites da conta prevalecem). Vault **VIRTUAL_PRIVATE** não integra Always Free e pode ter cobrança horária.
4. Não criar chaves master HSM por padrão: o modo padrão de novas chaves pode ser HSM, portanto exigir `protection_mode=SOFTWARE` e conferir preço e limite antes.
5. Não salvar chave SMTP ou qualquer outro segredo em `provider-public-inputs.json`, Android/APK, Git, capturas, chat ou logs. Somente após Vault existente, chave master adequada e IAM mínimo será possível um fluxo seguro de inserção direta do segredo pelo operador.
6. API FastAPI, envio automático de e-mail, ativação de usuários e Pix real continuam **OFF**; PostgreSQL local `frcaixinha_aistudio_dev` porta `5433` inalterado.
7. A1 Flex e E2 Micro continuam sem capacidade física reportada por M28603. Vault não depende da existência de VM, mas seu uso em runtime exigirá política IAM e identidade confiável.

## Referências oficiais

- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://docs.oracle.com/en-us/iaas/Content/General/service-limits/default.htm
- https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/kms/management/vault/create.html
- https://www.oracle.com/security/cloud-security/key-management/

**Checkpoint:** M28604 **READ_ONLY PASS**, OCI_VAULT **NÃO CRIADO**, plano de cofre **AINDA NÃO EXECUTADO**.
