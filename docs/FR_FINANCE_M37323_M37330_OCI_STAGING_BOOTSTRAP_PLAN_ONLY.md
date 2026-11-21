# FR Finance AI Studio — M37323–M37330 | OCI staging bootstrap PLAN ONLY

**Base:** M37322 GitHub Actions 6/6 PASS, Termux `FR_FINANCE_M37322_TERMUX=PASS`.
Relatório OCI real em 09/11/2026: `OCI_M37322_STATUS=READ_ONLY_PASS`,
região `sa-saopaulo-1`, 0 VMs RUNNING na raiz, 0 no staging, 0 VMs
PROVISIONING no staging, 0 Vaults ACTIVE no staging, VCN/subnet `FR Finance`
com CIDRs privados, roteamento IGW, subnet que permite IP público,
**sem regra pública de entrada 443 na security list associada**.
Os 11 blockers do M37322 permanecem necessários para a liberação.

## Objetivo do pacote

Preparar **artefatos textuais auditáveis de staging** para uso apenas
depois de existir VM, Vault, IAM, DNS/TLS, banco e autorização expressa.
Sem qualquer criação ou alteração OCI, sem infraestrutura cobrada,
sem envio de e-mails, sem cadastro ou ativação de usuários, sem Pix,
sem alteração de regras de firewall, sem executar Terraform.

Arquivos versionados novos:

- `infra/oci/staging-reuse/fr-finance-staging-api.service.template`:
  proposta systemd para FastAPI sob usuário sem privilégios,
  `uvicorn app.main:app` vinculado **somente ao loopback
  `127.0.0.1:8000`**, um worker, isolamento do processo, arquivo
  runtime em `/run` e `ConditionPathExists` de revisão manual.
  **O arquivo de condição não é autorização de produção** e não
  substitui autenticação/autorização do próprio app.
- `infra/oci/staging-reuse/Caddyfile.template`:
  proposta de proxy HTTPS via hostname ainda **não escolhido nem
  publicado** (placeholder `FR_FINANCE_API_FQDN`), somente
  `/api/*` para o loopback, demais caminhos 404 e headers.
  Certificado não é emitido automaticamente por este pacote.
  80/443 e Caddy NÃO foram instalados nem abertos.
- `infra/oci/staging-reuse/staging-runtime.env.example`:
  exemplo inerte sem secrets, senhas, DSNs, OCIDs ou tokens.
  `ENVIRONMENT=homologation`, região correta, flags de Pix, MP
  webhook e usuários reais em `0`. Esses flags são **defesa adicional,
  NÃO substituem os gates reais de API/RLS/servidor**; não expor
  a aplicação na internet baseando-se apenas neles.
- `backend/app/oci_staging_bootstrap_plan.py`:
  verificação estática fail-closed dos três modelos de arquivo
  (arquivos ausentes/symlink, linhas de segurança, porta local, proxies,
  variáveis duplicadas, operações inseguras e defaults perigosos).
  Calcula somente SHA-256 do conteúdo dos templates versionados.
- `backend/scripts/aistudio_oci_staging_bootstrap_plan_only.py`:
  CLI **offline** sem OCI SDK, rede, `subprocess`, arquivos de
  saída, sistema operacional, instalação, banco ou mutação. Imprime
  `M37330_BOOTSTRAP=PLAN_ONLY_PASS` e
  `OCI_DEPLOYMENT_AUTHORIZED=NO`.
- `backend/tests/test_m37323_m37330_oci_bootstrap_plan_ci.py`:
  testes sintéticos de segurança e regressão, usando cópias em
  diretórios descartáveis, não dados da Oracle.

## Limitações e bloqueios obrigatórios

1. A VM do `fr-finance-staging` precisa estar `RUNNING` e com
   shape/custo verificados; não basta a VCN estar pronta.
2. Instance Principal, Dynamic Group e permissões IAM mínimas
   precisam ser projetadas, aprovadas e atestadas na tenancy.
3. Um Vault **DEFAULT/software** e o ciclo de vida das chaves/segredos
   dependem de revisão de limites, custo e aprovação de criação.
   Não criar Virtual Private Vault/serviços pagos por engano.
4. Confirmar domínio próprio `frfinance.com.br`, nome da API
   (subdomínio ainda **não aprovado**), DNS público, autoridade
   certificadora, método de emissão ACME, TLS e proteção WAF/rate limit.
   Antes de expor 443, revisar NSGs, a security list, IP público,
   firewall da VM e proxy. Nunca expor 22 indiscriminadamente
   nem 5432/5433 à internet.
5. PostgreSQL remoto staging necessita persistência,
   roles sem privilégios excessivos, TLS `verify-full`,
   RLS, migrações controladas, backup cifrado e restauração provada.
   PostgreSQL do Termux porta 5433 não serve como banco de produção.
6. O backend de autenticação produção **não está aprovado**:
   o código legado possui gates específicos. A proposta do serviço
   aponta para app principal apenas como **topologia futura** e não é
   instrução para iniciar um servidor público.
7. Mercado Pago, SMTP Brevo, OAuth e webhooks precisam de evidência
   independente de endpoints e credenciais configurados.
8. Os administradores, membros e Pix real ficam bloqueados até
   autorização separada; CI 6/6 ou `PLAN_ONLY_PASS` nunca é
   prova de implantação pública ou aptidão financeira.

## Comando local após CI e sincronização

```bash
cd "$HOME/fr-finance"
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_m37323_m37330_oci_bootstrap_plan_ci.py
PYTHONPATH=backend python3 backend/scripts/aistudio_oci_staging_bootstrap_plan_only.py
```

Não execute `systemctl enable`, `systemctl start`, `caddy run`,
`terraform apply`, `oci compute instance launch` ou qualquer
comando de criação de Vault apenas com base nesses templates.

## Estado do projeto

Ramo: `atualizacao-ai-studio-9b46a63187`.
Repositório: AI Studio atual, não FR 2.2.
Catálogo SQL: **106** (inalterado).
OCI VM/Vault, firewall, DNS: **nenhuma mutação neste pacote**.
Mercado Pago real, Pix real, ativação real: **OFF**.
