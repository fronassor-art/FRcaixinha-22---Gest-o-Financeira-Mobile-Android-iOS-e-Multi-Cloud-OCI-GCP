# AI Studio — M16100–M17000 | Assinatura sintética de origem de notificações

Origem: M16000 sincronizado no Termux, commit \`33d0e9b\`, FastAPI PID 21275, PostgreSQL AI Studio 5433, 10 contratos PASS; migração 041 local NÃO aplicada, envios reais desativados.

## Objetivo
Assinar e verificar envelopes de eventos **100% sintéticos** com HMAC-SHA256 de propósito segregado e relógio UTC, vinculando evento, destinatário, tenant, papel, ano, tipo e hash de referência. O verificador recebe segredo de teste explícito (nunca incluído no produto), e não disponibiliza endpoint que emite assinatura. Assinatura válida **não** implica autenticidade da origem real, autorização de envio, liquidação, banco reconciliado ou integração com provedor de mensagens.

Migração 041 de staging (apenas GitHub Actions descartável) fortalecida para exigir vínculo ativo do destinatário e usuário \`ACTIVE\` na política de leitura RLS. A identidade da sessão nos GUC SQL em testes ainda é alegada, portanto não oferece prova contra credencial de banco vazada.

## Verificações
- Contrato assinado com domínio exclusivo M17000.
- Exige 8 campos exatos, UUID canônico e enum real de evento/papel.
- Rejeita corpo alterado, evento/tenant/user/role/ciclo/tipo/data/hash modificados.
- Rejeita extra keys, formatos de data não canônicos, datas com fuso trocado.
- Valida HMAC com \`compare_digest\`; segredos menores que 32 bytes são recusados.
- Janela UTC válida entre -30 segundos futuros e +300 segundos passados.
- Rejeita replay temporal fora da janela (mas prevenção *persistente* de replay exige banco oficial).
- Preserva templates neutros existentes, sem CPF, dados financeiros, PII ou falsas confirmações.
- Nenhum endpoint de emissão de assinatura nem assinatura automática para eventos externos.
- Não ativa \`GET /notifications\`; permanece 503 para sessão válida.
- Não implanta migração 041 no Termux/OCI e não instala/ativa provedores.
- Run CI frontend, backend, PG16, PG18, ZIP e APK antes de liberação do fast-forward.
- Pendências P0: origem real autenticada (service-to-service), segredo em Vault com rotação, prova anti-replay transacional, políticas RLS vinculadas à sessão real, conexão segura de leitura com backend autenticado.
- Pendências P1: cursor assinado, paginação, leitura idempotente, preferências, cronograma e push/e-mail/WhatsApp com aprovação e LGPD.
- Pendências P2: três perfis no aparelho, notificações reais e acessibilidade, evidências AT-01–50.

Nenhuma migração local/OCI, nenhum dinheiro real, nenhum fechamento ou pagamento foi autorizado.


## M17000 também entrega o contrato de paginação estrita (não conectado)

- \`backend/app/notification_inbox_page_boundary.py\`: valida contrato das linhas \`notification_inbox_staging\`, usuário, papel, tenant, datas com timezone e ordenação keyset estrita.
- Cursor HMAC-SHA256 de domínio exclusivo, vinculado a destinatário/papel/tenant, com TTL de 15 minutos e margem de relógio 30 s, checagem de assinatura constant-time, base64 canônico.
- Limite de 1 a 50 registros + 1, rejeição de registros repetidos, respostas fora de ordem, scopes e carimbos forjados; página com \`unread_count=None\` para evitar contagem falsa.
- A API ainda responde 503 com sessão válida, pois a migração 041 não foi aplicada no Termux e não há autenticação produtiva das fontes.
- Testes \`backend/tests/test_m17000_notification_page_cursor_ci.py\` cobrem adversários e limites, sem acesso SQL ou envio de mensagens.
