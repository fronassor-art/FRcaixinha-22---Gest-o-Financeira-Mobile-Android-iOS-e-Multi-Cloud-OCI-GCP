# FR Finance AI Studio — M37470 | Inventário OCI real somente leitura + matriz de produção

## Checkpoint

M37469, commit `dbdd12d`: 36 testes PASS no Termux e 6/6 jobs GitHub Actions aprovados. O inventário anterior registra 20 provas operacionais de lançamento e sete etapas de provedores. O PostgreSQL local possui 106 SQL versionados, sem migrações executadas pelos pacotes de CI.

## Objetivo operacional

Consultar **somente leitura** a Oracle Cloud Infrastructure (OCI) `sa-saopaulo-1`, usando o ambiente OCI CLI/SDK já configurado no Debian/Termux, e distinguir:

- `NO_RUNNING_STAGING_INSTANCE_OBSERVED`: nenhuma VM de staging `RUNNING` observada;
- `PROVISIONING_OBSERVED_NOT_RUNNING`: uma ou mais instâncias ainda em provisionamento, nenhuma em execução;
- `RUNNING_OBSERVED_NOT_PUBLIC_SERVICE_PROOF`: pelo menos uma instância do compartimento de staging está `RUNNING`, **sem inferir que a API, HTTPS, autenticação ou DNS estejam funcionando**;
- `BLOCKED_...`: consulta OCI não concluída ou não confiável; estado real permanece desconhecido, não ausente por presunção.

O M37470 não tenta provisionar VM, alterar IAM/VCN/security list, acessar segredos do Vault, criar banco, instalar backend, ativar contratos ou realizar Pix.

## Implementação

`backend/app/oci_live_release_bridge_m37470.py` aceita apenas os três relatórios tipados já produzidos pelos auditores M37300 (compute/vault), M37316 (rede) e M37340 (IAM). Impõe região correta, origem API autenticada, consistência de contagens e nenhum sinalizador prematuro de permissão. Reaproveita também a validação M37360 de readiness unificada.

`backend/scripts/aistudio_m37470_oci_live_release_readonly.py` possui três ações:

- `offline` (padrão): relatório de bloqueios sem rede, seguro em GitHub Actions e no Termux.
- `live`: consulta OCI **autenticada** via SDK/CLI existente; imprime apenas estados, números e riscos de rede, sem OCIDs, chaves, endereços IP ou respostas completas.
- `json`: executa as mesmas leituras reais e retorna o diagnóstico estruturado para consulta interna. Não autoriza o lançamento.

A função `attach_oci_observation_to_release` cruza essa leitura de OCI com o relatório M37469 e não altera `live_gates_verified=0`, `provider_gates_verified=0`, `production_authorized=false`. Uma VM `RUNNING` não prova que HTTPS público responde, o firewall do SO está correto, PostgreSQL TLS/RLS está homologado, backup foi restaurado ou que autenticação e pagamentos funcionam.

`backend/tests/test_m37470_oci_live_release_bridge_ci.py` testa estados de VM, região inválida, dados injetados, contagens incoerentes, permissões falsificadas, sigilo de credenciais e funcionamento da interface `offline/live/json` com SDK **simulado**, sem contatar o OCI real dentro do GitHub Actions.

## Execução no Debian/Termux

Estando no ambiente com o pacote Python `oci` e o perfil CLI configurado:

```bash
cd "$HOME/fr-finance"
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37470_oci_live_release_bridge_ci.py
python backend/scripts/aistudio_m37470_oci_live_release_readonly.py offline
python backend/scripts/aistudio_m37470_oci_live_release_readonly.py live
```

A ação `live` pode falhar caso o perfil OCI não esteja instalado naquele interpretador, as permissões IAM faltem ou a rede esteja indisponível. Nesse caso, o sistema imprime `BLOCKED` **sem afirmar que a VM não existe**, e nenhuma alteração é executada.

**Nunca colar no chat chaves privadas OCI, tokens, senhas, arquivos de configuração, retorno JSON bruto com OCIDs ou credenciais.**

## Próximas provas após leitura real da OCI

Se a VM continuar ausente, permanecerá pendente a capacidade e o provisionamento autorizado da instância sem custo. Se ela estiver realmente `RUNNING`, a próxima etapa deverá focar no acesso seguro, HTTPS, deploy de staging, TLS PostgreSQL, restauração de backup e testes E2E de autenticação/aceite. São atividades diferentes da observação de VM e requerem autorização e validação próprias.

**Status comercial permanece bloqueado:** licenças, pagamentos, Pix e ativação real OFF; nenhum SQL local é aplicado.
