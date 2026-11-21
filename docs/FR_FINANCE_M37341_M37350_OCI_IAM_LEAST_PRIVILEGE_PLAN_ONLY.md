# FR Finance AI Studio — M37341–M37350 | IAM de privilégios mínimos (PLANO, NÃO APLICAR)

## Base autenticada de 09/11/2026

O operador homologou o M37340 no Termux:
- Commit `a9c4de7bb7b127c7dc4c61cb8d96266491c6d891`, GitHub 6/6 PASS e 28 testes IAM locais PASS.
- `M37340_IAM=READ_ONLY_PASS` na região `sa-saopaulo-1`;
  compartimento `fr-finance-staging=ACTIVE`;
  `OCI_ROOT_DYNAMIC_GROUPS_ACTIVE=0`,
  `OCI_ROOT_POLICIES_ACTIVE=1`,
  `OCI_STAGING_POLICIES_ACTIVE=0`,
  `OCI_CANDIDATE_SECRET_BUNDLE_STATEMENTS=0`.
- Nenhuma política, grupo, instância, Vault ou secret foi criado.
  `PIX_REAL=OFF`, `REAL_USER_ACTIVATION=OFF`, PostgreSQL local intacto.
- A auditoria M37322 registrou 0 VMs RUNNING na raiz e staging,
  0 VMs PROVISIONING no staging e 0 Vaults ACTIVE no staging.

**Interpretação:** a única política da raiz ainda não foi avaliada
manualmente quanto a seu conteúdo/efeito. A consulta de dynamic groups
não deve ser interpretada como uma enumeração completa de todos os
domínios IAM. A contagem de políticas candidatas é uma **heurística**,
não um atestado de acesso real nem prova de ausência de políticas
indiretas/herdadas. Condições, identidade e herança exigem avaliação
posterior.

## M37341 — corrigir classificação de candidatos IAM

O classificador original do M37340 considerava apenas:
`Allow dynamic-group NAME to read secret-bundles in compartment fr-finance-staging`.
Isso não abrangia as formas legítimas documentadas pela Oracle com
`compartment id <OCID>`, grupo dinâmico qualificado por domínio
`'<domain>'/'<group>'` e `in tenancy where target.secret.id = '<OCID>'`.

A nova regex considera **candidatos a inspeção manual**, nunca permissões
confirmadas. Um candidato pode pertencer a outro aplicativo; mesmo
uma ocorrência legível pode não autorizar nenhuma instância. O
diagnóstico anterior de zero candidatos deve ser **rechecado por
consulta real M37340 após a sincronização deste pacote**, sem
concluir que todo o IAM está vazio.

## M37342–M37350 — arquitetura para futuro Instance Principal

Ficheiros versionados:

- `infra/oci/staging-reuse/iam-instance-principal.review.template`:
  template **não executável**, sem OCIDs reais, para grupo dinâmico
  restrito por **ambas** as condições `instance.id` e
  `instance.compartment.id` via `all { ... }`;
  política `read secret-bundles` condicionada a
  `target.secret.id` de **um único segredo específico**.
  O domínio IAM, VM, compartment e secret são marcadores, não
  valores válidos para uma implantação.
- `backend/app/oci_iam_least_privilege_review.py`:
  rejeita modificações que ampliem o escopo, criem regras `any`,
  troquem `read secret-bundles` por `manage secret-family`,
  permitam Pix ou usuários reais ou gravem qualquer OCID no template.
  Relata apenas hash SHA-256, contagem e bloqueios — **sem IAM, OCI,
  subprocess, HTTP ou escrita em arquivos**.
- `backend/scripts/aistudio_oci_iam_least_privilege_plan_only.py`:
  gera relatório local offline `M37350_IAM_PLAN=PLAN_ONLY_PASS`.
  Um PASS não equivale a permissão, Vault, VM, servidor, aplicação,
  certificado ou autorização de implantação.
- `backend/tests/test_m37341_m37350_oci_iam_review_plan_ci.py`:
  casos de ampliação indevida, credencial em repositório, domínios,
  políticas de `tenancy` e modelos de resposta segura.

## Sequência futura, ainda não autorizada

1. Aguardar VM autorizada e RUNNING, confirmar shape, dispêndio,
   propriedade e OCID com verificação autenticada.
2. Confirmar identity domain do projeto, OCID do compartment staging,
   tipo e custo de Vault DEFAULT e secret criado **por procedimento
   seguro separado**. Jamais copiar segredo ou credencial ao Git/chat.
3. Revisar política de grupo dinâmico escopada à instância exata e
   as condições de `target.secret.id`, inclusive possíveis direitos
   herdados. Uma política por segredo/necessidade, sem permissões
   `manage all-resources`, `manage secret-family` ou acesso
   universal à tenancy.
4. Obter autorização explícita para mutações IAM; criá-las só então
   usando fluxo autenticado e verificação de identidade.
5. Esperar propagação IAM, e na própria VM autorizada testar
   `InstancePrincipalsSecurityTokenSigner` e leitura do segredo
   **sem imprimir conteúdo**, com logs redigidos. O teste posterior
   deve demonstrar negação de acesso a outro segredo e a outro tenant.
6. Avançar apenas após Vault, PostgreSQL staging com TLS e RLS,
   backup/restore, proxy HTTPS/DNS e autenticação real estarem
   comprovados; nenhuma liberação de Pix ou usuários por herança.

A documentação Oracle observa que mudanças de matching rules podem
levar cerca de uma hora para surtir efeito; não executar retries
inseguros ou ampliar direitos diante de falha inicial.

## Execução offline, após CI aprovada

```bash
cd "$HOME/fr-finance"
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_m37341_m37350_oci_iam_review_plan_ci.py
PYTHONPATH=backend python3 backend/scripts/aistudio_oci_iam_least_privilege_plan_only.py
```

Para verificar de novo as políticas da conta Oracle, usar o **mesmo**
script somente leitura M37340, no Debian PRoot com SDK e configuração
já homologados. **Não executar nenhum `oci iam dynamic-group create`,
`oci iam policy create`, `terraform apply` ou comando de Secrets**.

**Estado:** 106 SQL esperados e nenhuma migração deste pacote. VM,
Vault, IAM, DNS e portas OCI não alterados. PostgreSQL local 5433
não modificado. Pix real, MP real e usuários reais permanecem OFF.

Referências:
- https://docs.oracle.com/en-us/iaas/Content/Identity/dynamicgroups/Writing_Matching_Rules_to_Define_Dynamic_Groups.htm
- https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingdynamicgroups.htm
- https://docs.oracle.com/en-us/iaas/Content/APIGateway/Tasks/apigatewaytroubleshooting_topic-gateway_create_or_update_fails.htm
