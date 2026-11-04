# AI Studio M2601–M2700 — gate de segurança do plano OCI

Base M2600: `665a807c0b78fb320a6e1d740bc1261c4ad1f68e`. PR #2 permanece Draft e o projeto FRcaixinha 2.2 permanece independente.

## Implementado

- `backend/app/oci_staging_plan_guard.py` e `backend/scripts/aistudio_oci_plan_guard.py`: validam **localmente e sem credenciais** o JSON gerado por `terraform show -json`. Recusam arquivo excessivo, JSON não canônico, atributos de rede desconhecidos, CIDRs fora do projeto, porta pública, IPv6 não aprovado, regras de entrada/saída, gateway, recurso extra, atualização ou destruição. Somente quatro recursos autorizados: VCN isolada, security list sem regras, tabela de rotas vazia, subnet privada.
- O script imprime somente PASS/BLOCKED, quantidade de recursos e `APPLY_AUTORIZADO=NAO`, **sem logar dados do plano**.
- `backend/tests/test_m2700_oci_plan_guard_ci.py`: regressão e ataques simulados a planos maliciosos, invalidação de segredos impressos e proteção de arquivos locais.
- `.gitignore`: impede commit acidental de `.tfstate`, variáveis secretas `.tfvars`, plano binário `.tfplan`, JSON de plano e pasta `.terraform`.
- Health `/api/health/features/m2700` não lê nuvem nem imprime OCIDs; CI executa testes offline. Nenhuma infraestrutura é criada.

## Uso futuro seguro (NÃO executar enquanto OCI não for autorizada)

1. Auditoria de tenancy, compartment, região, identidade, orçamento e IAM.
2. Preparar Terraform em ambiente autorizado, com state remoto cifrado e bloqueio de concorrência, jamais enviar variáveis/tokens ao GitHub.
3. Gerar `terraform plan -out=...tfplan`, exportar via `terraform show -json ...tfplan > ...tfplan.json`, executar `python backend/scripts/aistudio_oci_plan_guard.py ...tfplan.json`.
4. Plano PASS é **apenas requisito**, não aprovação para `terraform apply`. Revisão humana, diff, custo, segurança de rede, recuperação e autorização explícita continuam obrigatórios.

O blueprint M2600 possui security list sem entrada/saída e rota sem Internet: rede isolada **não serve ainda** para webhook público ou GET real. Será necessário projetar zonas de entrada HTTPS separadas de rede privada, egress controlado e cofre de segredos, com evidência do provedor.

## Pendências operacionais

A [Issue #3](https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP/issues/3) continua aberta. Os testes de política não comprovam plano real emitido contra conta OCI, implantação, consentimento Mercado Pago, reconciliação ou funcionamento do APK no telefone. Nenhuma migração é aplicada em Termux e operações financeiras permanecem bloqueadas.

Documentação OCI: https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/core_subnet.html
