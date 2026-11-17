# OCI A1 pelo GitHub Actions

A automação fica em `.github/workflows/frfinance-oci-a1-autolaunch.yml`. O cron é `*/5 * * * *`; o GitHub executa agendamentos apenas a partir da branch padrão `main`, e pode atrasar ou omitir uma execução sob carga. A `main` já contém uma versão anterior do workflow, registrada como ativa, mas seu job permanece bloqueado enquanto `FR_FINANCE_OCI_CREATOR_ENABLED` não for `true`. As correções desta branch só passam a valer na `main` após integração.

## Controles de ativação

- `FR_FINANCE_OCI_CREATOR_ENABLED=true` permite ao cron executar o preflight. Ausente ou diferente de `true`, o job agendado é ignorado.
- `FR_FINANCE_OCI_LAUNCH_ENABLED=true` permite **somente ao cron** chamar `launch_instance`, e apenas após o preflight e o guard persistente. Deixar ausente até homologação e autorização explícita para criação real.
- `workflow_dispatch` executa sempre em modo sem criação, mesmo que a variável de lançamento esteja ativa.
- Secrets necessários para o preflight: `FRF_OCI_USER_OCID`, `FRF_OCI_TENANCY_OCID`, `FRF_OCI_FINGERPRINT`, `FRF_OCI_PRIVATE_KEY_PEM`. O lançamento exige também `FRF_OCI_SSH_PUBLIC_KEY`, correspondente a uma chave privada guardada pelo operador. O conteúdo de nenhum secret deve ser registrado em logs.
- `FR_FINANCE_OCI_MONITOR_ENABLED` é de outro fluxo e não habilita este criador.

O preflight exige assinatura `FREE_TIER`, confirmação de `sa-saopaulo-1` como home region, A1 Flex, rede existente e SSH 22 restrito a IPv4 /32. Exige ausência de outras instâncias e volumes ativos. O lançamento fixa 2 OCPUs, 12 GB de RAM, boot de 50 GB e imagem Ubuntu 24.04 ARM64. O runner não altera PIX, pagamentos, produção, banco de dados ou processos locais.

## Reconciliação e parada

Antes de pedir criação, o runner cria uma issue de guard com um token OCI de idempotência. Se a resposta OCI for incerta, a issue continua aberta. Cada execução consulta as instâncias de todos os compartments acessíveis: se encontrar a VM, registra a aceitação e desativa o workflow. Se a VM ainda não for visível, tenta novamente **com o mesmo token** dentro de 23 horas. Após esse prazo, ou se o guard antigo não tiver token, bloqueia novas tentativas para revisão humana. Um erro confirmado de falta de capacidade fecha a issue e permite uma nova tentativa futura. Uma issue de aceitação, inclusive fechada, impede novo lançamento mesmo se a VM for encerrada.

O endpoint de desativação requer `actions: write` no `GITHUB_TOKEN`. Se a desativação falhar, o próximo cron ainda encontra a VM ou a issue e não lança outra. Concessões IAM insuficientes, mudança no inventário ou imagem fixada indisponível bloqueiam o fluxo; não devem ser contornadas por criação manual automática.

## Homologação

`python -m unittest discover -s .github/tests -p 'test_oci_a1.py' -v` executa testes offline sem secrets e sem OCI. O workflow `frfinance-oci-a1-ci.yml` roda esses testes no push da branch de desenvolvimento e em PR para `main`. Após integrar o criador à `main`, `workflow_dispatch` serve para preflight OCI real somente leitura. A criação real exige nova autorização explícita e configuração consciente das duas variáveis, além do secret SSH.

Referências: [GitHub schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [OCI retry token](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/usingapi.htm#RetryToken).
