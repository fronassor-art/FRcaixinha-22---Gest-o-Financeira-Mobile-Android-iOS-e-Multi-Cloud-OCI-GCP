# FR Finance AI Studio — M37306–M37310 | Inventário OCI: Compute por SDK

**Base:** M37303 homologado `c5f9bcf436d0d91a50b8e10b6dc9cd46993b3501`.
**Escopo:** correção do inventário, nenhuma mudança financeira/SQL/instância.

## Evidência real observada, 09/11/2026

No Debian PRoot, a CLI OCI 3.96.0 em `/root/.venvs/oci-cli/bin/oci`
retornou **código 0 e saída de zero bytes** nos quatro comandos:

- instâncias raiz com `--all`;
- instâncias raiz com `--limit 1`;
- instâncias staging com `--all`;
- instâncias staging com `--limit 1`.

Isso **não é uma confirmação segura de zero instâncias**. Região,
compartimento (atributo IAM `name`), VCN e subnet foram consultados com
JSON válido, antes da falha de listagem Compute. Nenhum OCID, token ou
payload de resposta deve ser impresso no chat.

## M37306–M37310

O script existente `backend/scripts/aistudio_oci_live_inventory_readonly.py`
continua usando comandos OCI CLI `list` para rede, identidade e Vault,
mas utiliza agora o **SDK Python da mesma virtualenv OCI CLI** para
`ComputeClient.list_instances`. O SDK confere:

1. Região explícita `sa-saopaulo-1`, igual ao perfil selecionado,
   e compartimento OCI informado pelo auditor;
2. Chamada **somente de leitura** ao método `list_instances` e
   status HTTP **200**, não código de saída CLI;
3. Resposta `data` obrigatoriamente lista tipada (lista vazia é válida
   somente após resposta HTTP 200);
4. Paginação até o fim com `opc-next-page`, recusando loops,
   tokens inválidos, respostas malformadas e excesso de páginas;
5. Exportação mínima apenas de ID e estado para o auditor original,
   que já redige estados e contagens e nunca imprime IDs.

**Nenhum método OCI de criação, mutação, stop/start ou billing é chamado.**
Não há `terraform apply`, comandos de rede, SQL, Pix, troca de plano ou
alteração do monitor de capacidade A1 existente.

O SDK é carregado em Debian pelo Python da virtualenv:
`/root/.venvs/oci-cli/bin/python3`.
Não presumir que o Python geral de Termux possua `oci` instalado.

## Como testar após CI e sincronização

No Termux, após atualizar o commit e validar testes locais,
entrar pelo `proot-distro login debian` com bind para
`/mnt/fr-finance`, configurar `PATH=/root/.venvs/oci-cli/bin:$PATH` e
executar:

```bash
/root/.venvs/oci-cli/bin/python3 /mnt/fr-finance/backend/scripts/aistudio_oci_live_inventory_readonly.py
```

Se `OCI_M37300_LIVE_INVENTORY=READ_ONLY_PASS` e
`OCI_COMPUTE_SOURCE=SDK_HTTP_200_TYPED_LIST` estiverem presentes,
as contagens observadas pela API serão confiáveis **somente para a conta,
região, compartimentos e instante consultados**. Instância presente não
comprova DNS público, Vault configurado, HTTPS, banco TLS/RLS,
backup/restauração, licenças, Pix ou prontidão de produção.

**Catálogo:** 106 SQL, sem nova migração. Banco PostgreSQL local porta
5433 intacto. Mercado Pago e Pix reais OFF; ativação real não autorizada.

## Extensão M37311 — Vaults pelo SDK

As consultas `kms management vault list` também não devem converter
retorno de stdout vazio (mesmo com código CLI 0) em zero recursos.
Antes que o operador execute novamente o inventário, o comando passa a
usar `oci.key_management.KmsVaultClient.list_vaults`, em modo de leitura,
exigindo HTTP 200, lista tipada e paginação segura. Apenas o estado do
Vault (`ACTIVE`, etc.) chega à camada de inventário; os OCIDs não são
mostrados, e chaves e segredos não são consultados.

Isso **não significa** que exista Vault ativo, nem que política IAM esteja
correta. Somente uma resposta autenticada da conta atual comprovará
quantidade e estados de Vaults nesse compartimento. A prova não autoriza
gastos, migrations, usuários ou pagamentos reais.

O código deve ser executado com o Python da virtualenv OCI CLI, que
contém o SDK. A CLI permanece em uso para IAM, VCN e subnet, cujas
respostas JSON já foram confirmadas no diagnóstico real M37304.
