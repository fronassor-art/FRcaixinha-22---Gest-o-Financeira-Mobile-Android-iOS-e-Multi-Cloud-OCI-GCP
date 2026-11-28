# FR Finance AI Studio — M26900: OCI Vault Secrets, SDK de teste e autenticação de instância

## Implementação versionada

`backend/app/oci_vault_envelope_keys.py` implementa o protocolo
`KeyProvider.load_key(key_id)` já consumido pelos pacotes M26400/M26800.
O segredo AES-256 é representado por bytes de 32 posições,
armazenados futuramente no **OCI Vault Secrets** como conteúdo BASE64.

- O alias interno da caixinha, de 4–80 caracteres, é separado do
  OCID `ocid1.vaultsecret...` e não é um valor de chave secreta.
- Referência do segredo **com versão numérica fixa**:
  `SecretsClient.get_secret_bundle(secret_id=...,version_number=...)`.
  O adaptador confere no retorno o OCID, a versão, o formato `BASE64`,
  canonicalidade base64 e o comprimento exato (32 bytes).
- `CURRENT`/`LATEST` **não** são aceitos como substitutos de uma
  versão fixa: a rotação exige aprovação e atualização do catálogo
  M26800, e a chave anterior só pode permanecer para decifrar.
- `build_instance_principals_secrets_client(operator_oci_approved=True)`
  é uma fábrica explícita para instâncias OCI já provisionadas com
  IAM e `InstancePrincipalsSecurityTokenSigner`. Não carrega
  `~/.oci/config`, chaves privadas, tokens do Termux, variáveis de
  fallback nem endpoint de metadata customizado.
- Falhas na autenticação, resposta, base64, versão ou revogação
  bloqueiam a operação com mensagem genérica. Não registrar o
  conteúdo de `response.data` nem imprimir o segredo.
- O SDK opcional está isolado em
  `backend/requirements-oci-vault.txt`: `oci==2.190.0`.
  **Não instalar essa dependência no Termux nem na CI regular.**

## Contrato de testes

`backend/tests/test_m26900_oci_vault_keys_ci.py` usa exclusivamente
clientes sintéticos injetados, sem rede:
1. valida versão e OCID exatos, conteúdo BASE64 e tamanho AES-256;
2. rejeita chave inexistente, versão alterada, formato inválido,
   corpo de tamanho incorreto e falha HTTP simulada;
3. comprova integração com o M26800 (tenant/papel) e M26400 (AES-GCM);
4. verifica a fábrica com signer fictício e sem arquivo de API key;
5. confirma que não há rota pública de Vault, cadastro ou Pix.

A CI comprova **a interface e a política**, não a autenticação na
conta Oracle, a permissão de ler um segredo real nem a operação da VM.

## Dependências externas para implantação

Antes de habilitar o adaptador em staging OCI, precisam existir:
- tenancy e região definidas, VM/serviço ativo, domínio e HTTPS;
- Vault com segredo rotacionável por tenant e versão aprovada;
- Dynamic Group da instância e política IAM mínima para apenas os
  segredos aprovados. Separar acesso de selagem e de decifragem;
- backend independente da porta local `5433`, segregação de roles,
  banco de staging/produção com migrações específicas e backup;
- comprovação de acesso sem imprimir a chave, rastreio de auditoria,
  limites, rejeição de versões erradas, rotação e revogação testadas;
- confirmação real do provedor de e-mail e controle do destinatário,
  documento contratual válido, MFA e dupla aprovação quando aplicável.

Os SQL de CI/staging do M26700 são **proibidos no banco do Termux e
também não são migrações prontas para produção**. O código do M26900
não dispara solicitações OCI sem uma chamada explícita à fábrica e
sem a própria instância possuir autenticação configurada.

## Referências de API Oracle

- https://docs.oracle.com/en-us/iaas/tools/python/latest/api/secrets/client/oci.secrets.SecretsClient.html
- https://docs.oracle.com/en-us/iaas/tools/python/latest/api/secrets/models/oci.secrets.models.SecretBundle.html
- https://docs.oracle.com/en-us/iaas/tools/python/latest/api/secrets/models/oci.secrets.models.Base64SecretBundleContentDetails.html
- https://docs.oracle.com/en-us/iaas/tools/python/latest/api/signing.html
