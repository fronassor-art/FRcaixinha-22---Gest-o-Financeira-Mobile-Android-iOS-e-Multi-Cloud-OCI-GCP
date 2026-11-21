# FR Finance M40820 — bloqueio de SMTP real padrão (NO-GO)

**Base:** M40810 `fcbd839`; supermacropacote M40800–M40820. Sem envio de mensagens, servidor SMTP, DB original, dispositivo ou migração.

## Pendência observada

`backend/app/onboarding_mail_transport.py` tinha `smtp_factory=smtplib.SMTP` como transporte padrão. Embora atualmente nenhum endpoint público de convite/recuperação chame o envio, um código Python ligado futuramente a esse adaptador poderia abrir uma conexão real SMTP e submeter mensagens sem os gates de outbox, consentimento e entrega que ainda não estão homologados.

## Defesa de escopo

A função `submit_access_message` rejeita agora as fábricas `smtplib.SMTP` e `smtplib.SMTP_SSL` **antes de construir ou abrir cliente**. Os testes existentes com `FakeSMTP` injetado permanecem em laboratório, inclusive o contrato de STARTTLS sintético, tratamento de erros e classificação `smtp_accepted` que não equivale a entrega.

**Limitação importante:** qualquer factory Python injetada explicitamente é código confiável do chamador e pode implementar sua própria rede; portanto esta trava protege o caminho padrão, mas NÃO é firewall global nem prova de impossibilidade de envios sob código comprometido. Nenhum worker real foi conectado. Para e-mail real, exigem-se outbox persistida, deduplicação, consentimento, métricas e autorização separada.

## Pendências de produção

- M40570: GUC spoofing continua **NO-GO** sob SQL arbitrário da role app.
- M40730: comprometimento da credencial do SQL signer contorna prova Ed25519 (**NO-GO**).
- OCI, Vault/KMS, TLS, runtime owner, SMTP Brevo, credenciais de produção, MFA Master, revisão regulatória e homologação Android continuam sem prova operacional suficiente.
- CI M40820 e CI geral devem aprovar o commit antes da sincronização source-only; nenhuma migração SQL foi introduzida por M40800–M40820.

`MIGRATIONS=NONE`; `LOCAL_DB_WRITES=NONE`; `SERVICE_RESTARTS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`; PR #2 Draft, main intacta.
