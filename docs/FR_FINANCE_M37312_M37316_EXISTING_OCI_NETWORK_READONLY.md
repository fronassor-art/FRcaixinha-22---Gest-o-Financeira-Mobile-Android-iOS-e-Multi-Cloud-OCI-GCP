# FR Finance — M37312–M37316 | Rede OCI existente: auditoria operacional somente leitura

**Ponto de partida real:** M37311, commit `065e44faadc19fc2f0741cf8290f64d19b33c390`.
No dia 09/11/2026 a conta `sa-saopaulo-1` retornou por SDK autenticado:
`fr-finance-staging=ACTIVE`, VCN `FR Finance=AVAILABLE`, subnet
`FR Finance=AVAILABLE`, **0 VMs RUNNING na raiz**, **0 RUNNING ou
PROVISIONING no staging** e **0 Vaults ACTIVE no staging**.

Os dados não comprovam ausência de VMs desligadas ou recursos em todos
os demais compartimentos. Não há backend hospedado comprovado.

## Objetivo

O Terraform legado `infra/oci/staging/network.tf` criaria uma segunda VCN
privada `10.77.0.0/16` e uma subnet sem IP público. **Não aplicar**
este blueprint nem usá-lo para alterar a VCN existente sem uma revisão
específica e uma autorização separada.

O novo módulo `backend/app/oci_existing_network_audit.py` e o script
`backend/scripts/aistudio_oci_existing_network_readonly.py` examinam
a **VCN real** chamada `FR Finance` e sua subnet nomeada `FR Finance`.
Eles efetuam somente operações OCI SDK de listagem/detalhe:

1. VCN do compartimento raiz: nome não ambíguo, CIDR IPv4 privado,
   ciclo de vida `AVAILABLE`;
2. subnet atrelada à mesma VCN: CIDR IPv4 privado, permissão de IP
   público em futuras VNICs e as security lists vinculadas;
3. tabela de rotas da subnet, default route `0.0.0.0/0` até Internet
   Gateway **habilitado** e disponível;
4. regras **de entrada das security lists vinculadas à subnet**:
   acesso público TCP 80, 443, 22, 5432 ou 5433. Uma regra de todos
   os protocolos de fonte pública também é considerada exposição;
5. status resumido, redigido e sem OCIDs, IPs, CIDRs, chaves,
   respostas brutas, cabeçalhos, erros de serviço, tokens ou segredos.

A listagem de recursos exige HTTP 200 e respostas SDK estruturadas,
continua até o fim da paginação e bloqueia respostas malformadas.
A auditoria não cria NSG, firewall, VM, rota, DNS ou Vault. Nenhuma
ação tem custo solicitado.

## Limitações fundamentais

A ausência de regra TCP 443 na **security list** não prova ausência
de regras de NSG, nem a existência de 443 comprova HTTPS.
NSGs associados a futuras VNICs, firewall Linux, IAM, portas de
containers, WAF, certificado, DNS, provedor de IP, conectividade
externa e desempenho **não são verificados** por esta etapa.

Um status `READ_ONLY_PASS` significa que as respostas de rede
foram legíveis e coerentes; não é sinal verde para publicar a API
ou ativar autenticação, membros ou Pix. Mesmo com rota IGW e entrada
443, a produção permanece `NOT_AUTHORIZED`.

**Nunca expor PostgreSQL 5432/5433 à internet.** TCP 22 não deve ser
aberto indiscriminadamente. Não executar alterações de rota/firewall
nem provisionamento sem aprovação separada do plano e das despesas.

## Execução após CI

O comando deve rodar usando o SDK Python instalado na virtualenv
`/root/.venvs/oci-cli` no Debian PRoot e a cópia atualizada do
projeto montada em `/mnt/fr-finance`:

```bash
export PYTHONDONTWRITEBYTECODE=1
/root/.venvs/oci-cli/bin/python3 /mnt/fr-finance/backend/scripts/aistudio_oci_existing_network_readonly.py
```

Não compartilhar configuração `~/.oci/config`, PEM ou tokens.

## Próximo passo com os dados reais

Se a rede estiver coerente: planejar **sem executar** o bootstrap
de backend staging com proxy 443/TLS, acesso restrito, Instance Principal,
Vault `DEFAULT`, PostgreSQL remoto com TLS/roles/RLS, backup/restauração
e verificação de run SHA/assinatura do APK. O provisionamento da VM
continua bloqueado por falta de capacidade física relatada e
por ausência de autorização para upgrade pago.

**Catálogo:** 106 SQL; nenhuma migração executada no banco local 5433.
**Pix, Mercado Pago real e ativação de administradores/membros:** OFF.

Referência SDK Oracle:
https://docs.oracle.com/en-us/iaas/tools/python/latest/api/core/client/oci.core.VirtualNetworkClient.html
