# AI Studio M3201–M3300 — endurecimento do webhook Mercado Pago

O pacote M3000 já continha a fábrica de receptor real para OCI staging, mas ainda era importante proteger o endpoint contra payload HTTP sem tamanho declarado (*chunked*) e ambiguidade de cabeçalhos assinados.

## Alterações

- A fábrica `create_webhook_staging_router` agora limita o corpo a **16.384 bytes durante a leitura dos chunks**, rejeitando o fluxo antes de acumular conteúdo excessivo. Confiar somente em `Content-Length` ou carregar todo o corpo antes do limite permitiria uso excessivo de memória.
- `x-request-id` e `x-signature` exigem **uma ocorrência cada**; cabeçalhos duplicados são rejeitados antes de resolver a conta ou recuperar segredo no Oracle. `Content-Type` também exige ocorrência única.
- O requisito HTTPS é avaliado sobre o esquema recebido no ASGI, e não pela presença isolada do cabeçalho `X-Forwarded-Proto`, que qualquer cliente poderia falsificar. Na OCI, o proxy deve configurar explicitamente **lista de IPs confiáveis** para encaminhamento de headers e TLS real no LB, sem permitir acesso direto ao serviço privado.
- `SellerContext.provider_account_id` é alias de nomenclatura ao `seller_id` técnico do Mercado Pago, sem adicionar papéis de usuário; usar apenas `MASTER`, `TENANT_ADMIN` e `TENANT_MEMBER`.
- Testes adversariais de streaming, duplicação de header e falsificação de HTTPS. Nenhuma chamada real ao Mercado Pago e nenhum lançamento financeiro.

## Gates restantes

O bootstrap OCI, DNS/TLS, WAF, IAM, backup, failover, cadastro de aplicação MP, consentimento dos administradores e migrações staging ainda não aconteceram. O servidor continua desabilitado no Termux e esta mudança não autoriza dinheiro real. PR #2 Draft e Issue #3 permanecem abertas.

Cláusulas históricas de referência: 2.1–2.3, 9.1–9.9, 13.1–13.6. Não modificar o projeto independente FRcaixinha 2.2.
