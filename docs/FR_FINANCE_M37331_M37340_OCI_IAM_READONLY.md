# FR Finance AI Studio — M37331–M37340 | OCI IAM real, somente leitura

**Base comprovada** — M37330: GitHub 6/6 PASS, `29 passed` no Termux,
`M37330_BOOTSTRAP=PLAN_ONLY_PASS`, 106 SQL versionados, 11 blockers
abertos de hospedagem, nenhum recurso OCI provisionado por este trabalho.

## Por que a auditoria IAM vem agora

O backend staging depende de um mecanismo de autenticação de serviço
**Instance Principals** e de autorizações mínimas para ler segredos de
um futuro Vault. Até M37322, o resultado real da OCI era: 0 VMs
`RUNNING` na raiz e staging, 0 `PROVISIONING` no staging,
0 Vaults `ACTIVE` no staging. Não há teste legítimo de
`InstancePrincipalsSecurityTokenSigner` sem uma instância OCI ativa.

A documentação oficial do `oci.identity.IdentityClient` permite:
`list_compartments`, `list_dynamic_groups` (raiz) e `list_policies`
(raiz ou compartimento). São **consultas de leitura**, não criação,
alteração nem ativação de grupos/políticas.

## Implementação nova, já versionada e inerte

- `backend/app/oci_iam_readiness_readonly.py`: interpreta respostas
  mínimas, separa os compartimentos, valida IDs/estados e conta
  grupos/políticas legíveis e **candidatos** de política para
  `read secret-bundles`. Alerta sobre algumas configurações de amplo
  escopo para revisão manual. O classificador não tenta interpretar
  todo o IAM da Oracle.
- `backend/scripts/aistudio_oci_iam_readonly.py`: usa o SDK da
  virtualenv OCI do Debian (`/root/.venvs/oci-cli/bin/python3`)
  para fazer quatro grupos de listagens autenticadas, paginadas e
  verificadas por HTTP 200: compartimentos da raiz, grupos dinâmicos
  da raiz, políticas da raiz e políticas diretamente anexadas ao
  `fr-finance-staging`. Não consulta usuários, senhas, tokens
  nem secret bundles.
- `backend/tests/test_m37331_m37340_oci_iam_readonly_ci.py`:
  testes offline com cliente OCI simulado, cobrindo JSON inválido,
  403, exceções de rede, paginação/cursores, grupos ambíguos e
  redaction de regras/identificadores.

**Dados expostos no relatório:** região, contagens de grupos e políticas
ativos e contagem de possíveis políticas pertinentes. **NÃO expostos:**
OCIDs, regras `matching_rule`, `statements`, nomes reais de grupos,
nomes reais de políticas, IPs, chaves ou respostas brutas do SDK.
O comando retorna `BLOCKED` em acesso insuficiente ou erro de API.
Lista vazia só é confirmada mediante HTTP 200, objeto tipado e
paginação concluída.

**Atenção:** `OCI_CANDIDATE_SECRET_BUNDLE_STATEMENTS>0` não é prova
de que o aplicativo tenha acesso a algum segredo. Políticas herdadas
de subcompartimentos, identity domains e condições de IAM podem
requerer revisão adicional. Um nome associado ao projeto tampouco
prova o escopo de `matching_rule`. Nenhuma sinalização permite
ativar backend, Pix, pagamentos ou usuários.

## Políticas de futuro staging — design para revisão, NÃO aplicar

A regra de grupo dinâmico deverá referenciar as **instâncias exatas**
autorizadas no staging (OCIDs de VMs ainda inexistentes), não o
compartimento inteiro sem revisão de abrangência. A política deverá
permitir somente as operações de leitura de secret bundle efetivamente
necessárias, no compartimento de staging e, se compatível com o IAM,
com condição vinculada ao segredo/compartimento específico. Não usar
`manage secret-family in tenancy` nem políticas `manage all-resources`
para facilitar implantação. Não atribuir ao administrador acesso geral
aos segredos de todos os tenants. A política IAM final precisa ser
validada pelo provedor e pela autenticação da VM, não só por texto.

## Execução após 6/6 PASS e sincronização

No Termux, dentro de `~/fr-finance`:
```bash
proot-distro login debian \
  --bind "$HOME/fr-finance:/mnt/fr-finance" \
  -- bash -c '
    set -eu
    export PATH="/root/.venvs/oci-cli/bin:$PATH"
    export PYTHONDONTWRITEBYTECODE=1
    /root/.venvs/oci-cli/bin/python3 \
      /mnt/fr-finance/backend/scripts/aistudio_oci_iam_readonly.py
  '
```

Não copiar `/root/.oci/config`, PEM, tokens, listas IAM completas ou
declarações `matching_rule` ao chat.

## Limitações e estado de segurança

O resultado é uma auditoria de configuração e alcance de API. Não
comprova funcionamento do signer Instance Principals, do Vault,
chave de software, TLS, aplicação online, roles PostgreSQL,
backup, restore, ou aprovação de faturamento. A VCN/subnet existente
segue candidata a reuso; 443 ainda depende de plano seguro de
DNS/certificado e autorização separada. A1/VM e Vault continuam
pendentes, sem se presumir custo ZERO na OCI.

Banco PostgreSQL local 5433: **não modificado**. Catálogo 106 SQL.
Mercado Pago real: OFF. Pix real: OFF. Membros/admins reais: OFF.
Nenhuma política/grupo/VM/Vault é criada pelo script.

Referências oficiais:
- https://docs.oracle.com/en-us/iaas/tools/python/latest/api/identity/client/oci.identity.IdentityClient.html
- https://docs.oracle.com/en-us/iaas/Content/Identity/callresources/Writing_Policies_for_Dynamic_Groups.htm
- https://docs.oracle.com/en-us/iaas/Content/Identity/Concepts/commonpolicies.htm
