# FR Finance AI Studio — M36900–M37300 | Auditoria real OCI sem mutação

**Origem:** M36800 / `2c1bc6b868ab9d192314dcf0bb1544e8d5f3af8b`.
Esta fase visa descobrir o estado **real da conta Oracle**, não simular
provisionamento. Nenhuma alteração ao projeto FRcaixinha 2.2.

## Diagnóstico e artefatos

O projeto já possui `infra/oci/staging/network.tf`, que define VCN privada,
security list sem entradas e subnet proibindo IP público. Esse blueprint é
adequado para isolamento, mas **não entrega API pública HTTPS**.
Existe também workflow manual `.github/workflows/fr-finance-oci-staging-apk.yml`
para APK apontando para uma URL HTTPS **já funcional**, não para hospedar o
backend. Não invocar o workflow como prova de instância criada.

Novo `backend/scripts/aistudio_oci_live_inventory_readonly.py`:

- usa **OCI CLI já configurado**, lendo apenas tenancy e região do perfil
  privado (não revela nem registra OCIDs), respeitando o mesmo
  `OCI_CLI_PROFILE` e `OCI_CLI_CONFIG_FILE` em todas as consultas;
- recusa outra região que não `sa-saopaulo-1` e verifica assinatura/home
  region `READY`;
- observa `fr-finance-staging` em IAM pelo atributo oficial `name`
  (diferente de `display-name`, usado pela VCN/subnet `FR Finance`)
  no compartimento raiz; nunca conclui ausência de um compartment
  apenas por um atributo JSON de outro tipo de recurso;
- consulta **somente com comandos list** as VMs no compartimento raiz
  (contagem separada), as VMs no staging (RUNNING e PROVISIONING) e os
  Vaults ativos no staging. Uma VM fora do staging não comprova deploy;
- imprime **apenas estados e contagens**, nunca detalhes das respostas
  OCI, endereços IP, OCIDs, credenciais, arquivos ou erros do serviço;
- usa timeout, limite de JSON e trava no primeiro erro de autorização,
  schema ambíguo, configuração ou região equivocada.

O módulo `backend/app/oci_staging_live_inventory.py` contém todo o
contrato puro de validação; os testes CI usam comandos OCI **mockados**.
A CI não tem acesso à conta nem comprova VM/HTTPS/Vault reais.

### Execução posterior no próprio Debian/Termux com OCI CLI

```bash
cd "$HOME/fr-finance"
PYTHONPATH=backend python3 backend/scripts/aistudio_oci_live_inventory_readonly.py
```

Se `oci` estiver disponível apenas no Debian PRoot, executar nessa
sessão, após acessar a mesma cópia do repositório sincronizada.
Não colar configuração `~/.oci/config`, PEM ou tokens no chat.

### Interpretação correta

`OCI_M37300_LIVE_INVENTORY=READ_ONLY_PASS` prova apenas que as
consultas OCI funcionaram e retornaram os estados listados.
Uma instância `RUNNING` **não comprova** IP público, DNS, API,
firewall, HTTPS, PostgreSQL TLS, backup, Vault IAM seguro, autenticação,
Mercado Pago nem aptidão para ativar usuários.

Próximas ações, **dependentes de autorização financeira e operacional**:
classificar a VM em running/provisioning/capacity, definir plano de
endereço/portas DNS/TLS (sem reutilizar a subnet privada como pública
por acidente), configurar Vault mínimo, PostgreSQL isolado e restaurar
backup em staging OCI. Só então executar os 20 gates técnicos e os
7 externos com evidências reais.

**Sempre bloqueados:** terraform apply, lançamento/parada de VM,
alteração de VCN/firewall, upgrade pago, migrações no PostgreSQL local
5433, pagamentos, Pix real e ativação de usuários.

**Catálogo SQL:** permanece 106; não há nova migração. O observador
automatizado A1 existente não é alterado nem duplicado.

## Correção M37303 — campo IAM confirmado

A primeira execução real, com OCI CLI 3.96.0 localizado em
`/root/.venvs/oci-cli/bin/oci`, retornou o bloqueio
`OCI_STAGING_COMPARTMENT_NOT_FOUND`. A API de compartimentos fornece
`name`, mas o contrato inicial procurava `display-name`. O parser e os
fixtures de CI foram corrigidos. Não houve operação de criação, exclusão,
implantação ou cobrança. O novo PASS da CI permanece apenas ensaio de
parser sintético; a conta Oracle precisa ser consultada novamente no Debian.
