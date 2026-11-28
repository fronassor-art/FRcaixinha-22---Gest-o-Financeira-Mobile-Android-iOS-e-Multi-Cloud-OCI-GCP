# AI Studio M2901–M3000 — servidor OCI staging integrado ao Mercado Pago

## Implementado para implantação futura

`backend/app/oci_mp_staging_server.py` é uma aplicação **ASGI separada** que pode operar na OCI depois do provisionamento e da configuração do portal Mercado Pago. Ela reúne:

- Identidade OCI Compute via **Instance Principals**, sem API key pessoal nem arquivo `~/.oci/config`.
- OCI SecretBundle `CURRENT` para buscar a URL de conexão protegida do PostgreSQL e a assinatura do webhook. Em variáveis de ambiente ficam apenas **OCIDs de referência**, nunca credenciais ou tokens em texto.
- Validação estrita de PostgreSQL staging: database `frcaixinha_staging`, login dedicado `frcaixinha_mp_webhook_ingest`, host remoto, `sslmode=verify-full`. Banco e login são verificados no início, e conexões são encerradas ao parar o processo.
- Uma rota `POST /integrations/mercadopago/webhook` via FastAPI é registrada **somente** ao iniciar este processo em modo autorizado `RECEIVE_ONLY`. Recebe HTTPS, valida HMAC, consulta seller no banco, busca secret no OCI e grava notificação assinada no inbox idempotente.
- Resposta não confirma pagamento. **Nunca há operação financeira, saque, Pix, fechamento ou lançamento contábil**, e o `backend/app/main.py` usado pelo Termux permanece sem essa rota.
- Testes OCI/PostgreSQL simulados verificam o encadeamento completo da aplicação sem efetuar rede.
- Requisitos de servidor isolados em `backend/requirements-oci-staging.txt`.

## Configuração de servidor proposta (NÃO executar ainda)

Somente quando OCI estiver provisionada e houver autorização do proprietário:

- `ENVIRONMENT=homologation`
- `OCI_REGION=<regiao autorizada>`
- `FRC_MP_OCI_STAGING_ENABLED=1`
- `FRC_MP_STAGING_SERVER_MODE=RECEIVE_ONLY`
- `FRC_MP_STAGING_DB_SECRET_OCID=<OCID do segredo da DSN TLS do banco>`
- `FRC_MP_ACCEPT_LIVE_NOTIFICATIONS` ausente ou `0` no começo.

Com ambiente, IAM, segurança, domínio/certificado HTTPS, banco exclusivo, credenciais e webhook Mercado Pago configurados, entrada ASGI: `uvicorn app.oci_mp_staging_server:app`, atrás de proxy reverso confiável. **Não abrir o servidor diretamente na internet; configure allowlist de IPs do proxy, body limit, WAF/rate limiting e TLS.** Não usar URL pública sem HTTPS; não deixar o webhook em HTTP. Terraform, migration 034 e API Mercado Pago continuam sem execução neste pacote.

## Bloqueios ainda em aberto

Este código é tecnicamente conectável, mas **não confirma OCI provisionada nem seller autorizado**, pois não existem contas/secret bundles/migrações staging homologadas. App Mercado Pago e scopes devem ser criados no portal depois; login/sessões de usuários em produção, callback OAuth real com prova persistente, rotação de credenciais, auditoria, backup/restore, retry/dead letter e reconciliador bancário ainda demandam implementação/homologação.

O gateway M2600 continua sem lançamento financeiro. Para a futura conexão em produção será necessário passar por auditoria e autorização específica e comprovar que empresa e recebedor permanecem isolados.

PR #2 Draft, Issue #3 aberta. Nenhuma mudança em FRcaixinha 2.2 ou PostgreSQL local.

Referências: https://docs.oracle.com/en-us/iaas/Content/Identity/callresources/callingservicesfrominstances.htm e https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/optional-notifications
