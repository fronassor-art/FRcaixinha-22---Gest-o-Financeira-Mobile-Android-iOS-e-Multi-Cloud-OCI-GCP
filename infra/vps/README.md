# FR Finance AI Studio — M28612: arquitetura VPS independente de KingHost/Hostinger

**Status:** `DESIGN_ONLY / NOT_DEPLOYABLE / NO_SECRETS / NO_LIVE_FINANCE`  
**Referência:** branch `atualizacao-ai-studio-9b46a63187`, checkpoint anterior `abb3e18`; pesquisa técnica de 08/11/2026.  
**Projeto:** frente FR Finance **AI Studio** somente, sem importar ou alterar o repositório independente FRcaixinha 2.2.

## Veredito

O produto **pode ser hospedado em qualquer VPS Linux com acesso root** (inclusive KingHost VPS 8 GB ou Hostinger KVM 2), mas a branch **ainda não está pronta para produção VPS sem ajustes**. A maior parte da aplicação (React + Vite + Capacitor, FastAPI e PostgreSQL 18) é agnóstica de provedor. Componentes de autenticação/segredos/estágio exigem mudanças auditáveis e homologação. **Não ligar usuários reais, envios de aplicativo ou Pix só por haver VM online.**

Não migrar ou substituir arquivos da OCI, a VCN `FR Finance`, o PostgreSQL Termux da porta `5433`, PR #2, políticas de segurança ou credenciais.

## Comparação comercial verificada — VPS de 8 GB

| Critério | KingHost VPS 8 GB | Hostinger KVM 2 |
| --- | --- | --- |
| Computação anunciada | 6 vCPU, 8 GB, 170 GB SSD | 2 vCPU, 8 GB, 100 GB NVMe |
| Datacenter | Brasil | Brasil disponível, sujeito a estoque na escolha |
| Pagamentos no Brasil | Real; Pix/boleto/cartão | Real; Pix/boleto/cartão |
| Ciclo mensal | Seletor `Mensal` confirmado | Confirmar disponibilidade/preço no checkout |
| Promoções observadas | Black Friday R$63,90/mês **equivalente em contratação longa** | Black Friday KVM 2 R$42,99/mês **equivalente a 24 meses**, total R$1031,76 |
| Contratar um mês | Valor final da KingHost não confirmado no carrinho | Valor final da Hostinger não confirmado no carrinho |
| VPS grátis para novos clientes | Não encontrada oferta oficial de VPS 8 GB sem pagamento | Não oferece VPS gratuita; 30 dias é **prazo para pedir reembolso** condicionado |
| Reembolso | Promo de 30 dias **não lista VPS**; contrato geral diz 7 dias na primeira ativação, confirmar atendimento | Política oficial contempla VPS KVM, condicionada a 30 dias e 180 dias desde último reembolso de VPS |
| Backup do plano VPS | Não presumir que backup diário da hospedagem compartilhada inclua VPS; confirmar e contratar se necessário | Backups semanais anunciados; não substituem PITR/backup externo PostgreSQL |

**Atenção:** preço do plano mensal verdadeiro e total da cobrança só podem ser aprovados após seleção de periodicidade **Mensal**, datacenter Brasil e métodos de pagamento no **checkout oficial**. Evitar compromissos 12/24 meses que aparentem uma mensalidade baixa. Confirmação comercial individual e dados do cartão não devem aparecer neste repositório.

## Auditoria do repositório — portabilidade

| Componente existente | Evidência de código | Ajuste necessário |
| --- | --- | --- |
| React/Vite/Capacitor | `package.json`, `capacitor.config.ts` | Gerar `dist` para nginx/Caddy e APK release apontando para HTTPS real; não usar Termux loopback no APK comercial |
| API FastAPI | `backend/app/main.py`, `backend/requirements.txt` | Subir Uvicorn como serviço privado sob reverse proxy; bloquear docs de produção e rotas sintéticas |
| Postgres/RLS | `backend/migrations`, `backend/app/dependencies.py` | Criar **novo PG18 no VPS**, testar schema/roles/RLS e restore, nunca migrar CI/staging automaticamente |
| Autenticação produção | `backend/app/production_auth_gate.py` | Hoje há marcador explícito `OCI_STAGING_REVIEWED` e DSN TLS `verify-full` com hostname; implementar outro perfil **VPS_PRODUCTION_REVIEWED**, com requisitos equivalentes e testes negativos, sem desabilitar gate OCI |
| Segredos OCI | `backend/app/oci_secret_bridge.py`, `backend/app/oci_mp_staging_server.py` | Introduzir abstração de provedor de segredos: OCI permanece, novo adaptador VPS somente em staging aprovado; isolamento por função e tenant |
| E-mail | `backend/app/onboarding_mail_transport.py`, M28500 | Brevo SMTP já aceitou mensagem de teste; worker/outbox persistente, política de retentativas e callbacks ainda precisam de homologação |
| MP OAuth/webhooks | `backend/app/mp_*`, `backend/app/oci_mp_staging_server.py` | Recepção HTTPS com assinatura `x-signature` em staging, PKCE/state, tenant binding, sem enviar dinheiro real |
| Proxy desenvolvimento | `server.ts` | **Não** usar `tsx server.ts`/servidor Vite como produção; preparar frontend estático e API FastAPI isolada; revisar CSRF/cookies e proxy |
| CI/Android | `.github/workflows/validacao-atualizacao.yml`, `docs/FR_FINANCE_M21700_ANDROID_RELEASE_OCI.md` | Criar CI de implantação VPS independente; release APK assinada e compatível com URL pública sem regressão |

Uma incompatibilidade específica: `production_auth_gate._dsn` exige banco com sufixo `_prod`, porta `5432`, `sslmode=verify-full` e **host DNS FQDN**, não aceita `localhost`/IP. Portanto não assumir que basta escrever `localhost` no `DATABASE_URL`. Adaptar de forma segura a conexão privada (TLS válido com hostname interno, ou Unix socket autenticado e testado), preservando três contas `frc_ai_app`, `frc_ai_auth`, `frc_ai_verifier` e RLS.

## Topologia proposta — idêntica nas duas VPS

```text
Registro.br DNS (somente novos A/AAAA de app e api)
      |
https://app.frfinance.com.br          https://api.frfinance.com.br
      |                                     |
      +------------------+------------------+
                         |
                 Reverse proxy (Caddy/Nginx)
                     80/443 HTTPS
                         |
           +-------------+-------------+
           |                           |
    React build /dist         FastAPI/Uvicorn localhost
                                       |
                                PostgreSQL 18
                           private socket/interface only
                                       |
                       durable outbox + jobs, idempotência
                        /            |                 \
                 Brevo SMTP    Mercado Pago       Backup externo
                  (OFF)       (sandbox OFF)      (cifrado/testado)
```

- Única VPS Linux **x86_64**, Ubuntu 24.04 LTS ou Debian estável, com 8 GB de RAM. Não instalar painel pago ou n8n/OpenClaw (desnecessários para o FR Finance).
- Build do frontend em CI com Node 22 LTS e publicação dos **arquivos compilados**; backend em virtualenv isolado Python 3.12 (validar requisitos e wheels) com Uvicorn como serviço systemd restrito ou container não-root.
- Redis **opcional**, não assumir necessidade. Jobs duráveis com PostgreSQL existente, índices, limites, conexões e alerta de falha.
- PostgreSQL 18 isolado e não exposto; portas 5432/5433 **fechadas externamente**. Separar contas de acesso e dados entre tenants. TLS/identidade da conexão precisam atender o gate de produção.
- Caddy/Nginx público apenas 80/443; SSH (22) por chave, sem senha, idealmente IP restrito/VPN; Uvicorn/Node/PG sem binding público.
- Firewall, atualização de segurança, relógio NTP, restart automático systemd, limites de recursos, health checks, monitoramento externo e alertas.
- Backups **externos cifrados** de banco/arquivos, com retenção e restauração testada; backup do próprio provedor não substitui essa evidência. RPO/RTO ainda devem ser definidos e aprovados.
- Hostinger/KingHost são opções de VPS, **não dois ambientes simultâneos**. Implantar **um único servidor** escolhido pelo operador. OCI permanece apenas como contingência, sem custo novo.

## Plano por gates (execução futura, não rodar como receita pronta)

**Gate 0 — Cotação/contratação:** mostrar total exato de **um mês**, preço normal de renovação, tributos, backup, IP e forma Pix. Verificar disponibilidade Brasil, Linux, SSH root, liberdade de instalação PostgreSQL/Docker, proibição de taxas ou autorização de cartão inesperadas. Compra somente pelo proprietário.

**Gate 1 — VM fechada:** instalar OS, firewall, SSH por chave e atualização, sem DNS público apontado, sem segredos reais. Validar arquitetura x86_64, RAM e armazenamento físico e latência Belém↔Brasil.

**Gate 2 — DB staging novo:** preparar PostgreSQL 18 com contas de menor privilégio, TLS/Unix socket conforme gate, migrar schema **somente após inventário e revisão**. Não copiar usuários/credenciais do Termux sem autorização. Testar backup/restauração, RLS e transações financeiras.

**Gate 3 — backend fail-closed e adaptadores:** implementar `VPS_PRODUCTION_REVIEWED` como novo perfil de configuração; OCI continua intocada. Refatorar segredos para interface `SecretProvider` selecionada por implantação e validada no boot, com separação por finalidade/tenant e rotação; impedir fallback silencioso. Corrigir eventuais acoplamentos de endpoints OCI; testes unitários e negativos completos.

**Gate 4 — site e HTTPS:** preservar DNS MX/TXT SPF, DKIM e DMARC de ImprovMX/Brevo no Registro.br. Adicionar apenas A/AAAA para `app` e `api` após VM provisionada, obter certificados TLS e validar origem CORS/cookies/CSRF. Sem credenciais no frontend ou na APK.

**Gate 5 — homologação ponta a ponta:** Master/Admin/Membro com contas fictícias, convite/ativação sob controles, regressão financeira de ciclos, bloqueios, Ledger, backup/restore, concorrência, integridade do webhook, carga e reinício. E-mail real da aplicação **OFF até aprovação separada**. Pix inbound/outbound real **OFF**.

**Gate 6 — liberação escalonada:** após prova de segurança e contratos, liberar acesso de homologação externo e atualizar APK de homologação apontando para a API HTTPS. Separar processo para futura produção e dinheiro real, com aprovação do operador.

## Critérios mínimos de aceitação operacional

- 8 GB / x86_64 / SSD; CPU real observada e *stress test*, sem inventar capacidade para N usuários.
- 24x7 esperado; VPS única **não** é alta disponibilidade. O SLA do provedor não cobre falhas da aplicação.
- API 2xx nos probes seguros; headers TLS/CORS/sessões corretos; PG18 em conexão privada; backup offsite restaurado.
- CI e regressão sem mudança nas 147 cláusulas, sem alterações na identidade Master nem no cadastro de provedores OCI, e sem migrations no PostgreSQL Termux `5433`.
- Custos fixos explícitos de um mês e alertas de vencimento/renovação; não depender de promoções 24 meses.

## Fontes oficiais

- https://king.host/servidor-vps
- https://king.host/wiki/base-de-conhecimento/financeiro/
- https://king.host/pdf/contrato-hospedagem.pdf
- https://king.host/pdf/termo-de-prazo-para-cancelamento.pdf
- https://www.hostinger.com/br/servidor-vps
- https://www.hostinger.com/br/legal/refund-policy
- https://www.hostinger.com/br/support/1583267-onde-estao-localizados-os-servidores-da-hostinger/
- https://www.hostinger.com/br/support/1583236-quais-as-formas-de-pagamento-aceitas-pela-hostinger/

**Este arquivo é documentação de arquitetura e critérios de liberação; nenhum arquivo Docker Compose, token, migração, credencial ou deploy operacional foi criado.**
