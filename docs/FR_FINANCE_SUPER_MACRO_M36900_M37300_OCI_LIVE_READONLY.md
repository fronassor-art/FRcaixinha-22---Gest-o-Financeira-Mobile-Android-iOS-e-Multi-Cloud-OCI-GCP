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
  privado (não revela nem registra OCIDs);
- recusa outra região que não `sa-saopaulo-1` e verifica assinatura/home
  region `READY`;
- observa `fr-finance-staging` em IAM e a VCN/subnet `FR Finance`
  existentes no compartimento raiz;
- consulta **somente com comandos list** as VMs no compartment de staging
  (RUNNING e PROVISIONING) e Vaults ativos nesse compartment;
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
