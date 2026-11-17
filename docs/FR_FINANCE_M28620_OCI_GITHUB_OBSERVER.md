# FR Finance — M28620: GitHub Actions observador da OCI (somente leitura)

**Status: PREPARADO, NAO ATIVADO.** O script de criacao M28619 no Debian/Termux continua sendo o **unico** autorizado a tentar provisionar uma A1. Este pacote **nao chama** `launch_instance`, nao muda billing, nao cria recursos, nao reinicia o script local e nao altera a branch `atualizacao-ai-studio-9b46a63187` nem PR #2.

## Objetivo

- Um job `ubuntu-24.04` executa a cada 15 minutos (UTC: 07, 22, 37, 52).
- Faz `ListCompartments`, `ListInstances` e, quando encontra a instancia planejada, `GetInstance` na regiao `sa-saopaulo-1`.
- Busca `fr-finance-a1-always-free` e valida `VM.Standard.A1.Flex`, 2 OCPUs, 12 GB.
- Ausente: registra `NOT_FOUND` com job verde.
- Presente: registra estado de ciclo de vida (`PROVISIONING`, `RUNNING`, etc.), e cria **uma unica issue publica de aviso** sem OCIDs, IPs, tokens ou outros segredos.
- Erros e nomes duplicados: falha fechada; nao cria instancia.
- No GitHub, a pasta `.github/workflows` deve existir em `main` para agendamento. O fluxo de desenvolvimento e PR #2 permanece isolado.

## Arquivos

- `.github/workflows/frfinance-oci-a1-observer.yml`
- `.github/scripts/frfinance_oci_a1_observer.py`

## Trava principal

O cron existe, mas o job somente inicia quando a **Repository Variable** `FR_FINANCE_OCI_MONITOR_ENABLED` estiver exatamente `true`. Enquanto ausente, agendamentos ficam `skipped`. `workflow_dispatch` permite um teste manual depois da configuracao das credenciais.

## Segredos de GitHub — mesma identidade OCI usada no Termux

O operador escolheu reutilizar o usuario e a chave de assinatura OCI atuais. Esse metodo funciona, mas **a chave da conta atual pode ter permissoes amplas, inclusive de criacao/exclusao**. Uma falha de permissao/um workflow comprometido pode expor todo o alcance da conta. Preferir uma identidade monitor-only no futuro; o job atual usa exclusivamente APIs de consulta.

Cadastrar **diretamente** em Settings > Secrets and variables > Actions > Repository secrets:

- `FRF_OCI_USER_OCID`: campo `user` do `/root/.oci/config`
- `FRF_OCI_TENANCY_OCID`: campo `tenancy`
- `FRF_OCI_FINGERPRINT`: campo `fingerprint`
- `FRF_OCI_PRIVATE_KEY_PEM`: conteudo original do arquivo referenciado pelo `key_file` (multilinha, inclusive BEGIN/END)

Nunca enviar esses valores em chat, issue, commit, screenshot ou artifact. Esta automacao **nao precisa da chave SSH** `frfinance_oci_a1_ed25519`: essa chave serve para acessar o sistema operacional da futura VM, nao para consultar a API OCI. A chave de API OCI é outra.

## Configuracao sem exibir chaves — opcao via GH CLI no Debian

1. Verificar `gh --version` e `gh auth status`. Se nao houver `gh`, instalar o pacote GH CLI ou usar a interface do GitHub.
2. Se necessario, autenticar via `gh auth login -h github.com -p https --web`, concluindo a autorizacao fora do chat.
3. Definir `REPO='fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP'`.
4. Enviar os quatro campos de `oci.config.from_file('/root/.oci/config')` diretamente por stdin para `gh secret set NAME -R "$REPO"`, sem imprimi-los. Para a chave, usar redirecionamento `gh secret set FRF_OCI_PRIVATE_KEY_PEM -R "$REPO" < /root/.oci/frcaixinha_oci_api_key.pem` depois de verificar que o caminho é o `key_file` atual.
5. Executar um teste manual `gh workflow run frfinance-oci-a1-observer.yml --ref main -R "$REPO"`; analisar o resultado sem expor segredos.
6. **Somente apos teste PASS**, habilitar a variable: `gh variable set FR_FINANCE_OCI_MONITOR_ENABLED -b true -R "$REPO"`.
7. Desabilitar sem revogar as credenciais: `gh variable set FR_FINANCE_OCI_MONITOR_ENABLED -b false -R "$REPO"`.

## Limites e riscos

- Intervalo minimo oficial de 5 minutos; agendamentos podem atrasar/ser descartados. Escolhido 15 minutos por reduzir chamadas e consumo de runner.
- Monitora a existencia da VM, **nao** o processo local M28619. Se o Termux morrer sem criar a VM, o observador mostrara `NOT_FOUND` indefinidamente.
- Se surgir VM com outro nome, tamanho ou shape, faz fail closed ou nao detecta: registrar um alias exige revisao.
- O workflow nao configura SSH, PostgreSQL, backup, API, DNS ou front-end. Deploy via GitHub Actions na futura VM exigira um workflow **distinto** e acesso SSH separado com permissoes limitadas.
- Nenhum segredo consta do repositorio. Nenhuma VM paga sera criada. A issue publica de aviso contem apenas a identidade do produto, forma e estado da A1.

## Fontes

- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- https://cli.github.com/manual/gh_secret_set
- https://cli.github.com/manual/gh_variable_set
- https://docs.oracle.com/en-us/iaas/Content/Identity/Reference/corepolicyreference.htm

**M28620=WORKFLOW_PREPARED / GH_SECRETS_NOT_SET / AUTOMATIC_MONITOR_DISABLED / OCI_MUTATIONS=NONE**.
