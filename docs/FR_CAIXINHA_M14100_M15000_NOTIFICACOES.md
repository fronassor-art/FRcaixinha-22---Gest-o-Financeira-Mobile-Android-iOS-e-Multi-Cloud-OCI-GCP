# AI Studio — M14100 a M15000: Notificações — contrato, política e interface segura

## Auditoria documental antes da codificação

Fontes comuns versionadas no **REPOSITÓRIO DESTE PROJETO**, mesmo que os nomes históricos dos PDFs contenham \`2.2\`:
- \`public/assets/aistudio/FRcaixinha_2.2___Caderno_Mestre_LIMPO___147_cl_usulas_94d2a15c.pdf\`, SHA256 94d2a15c…, 57 páginas.
- \`public/assets/aistudio/FRcaixinha_2.2___Contrato_T_cnico_Mestre_ORIGINAL_LIMPO_7b28d5d5.pdf\`, SHA256 7b28d5d5…, 38 páginas.
- \`docs/CHECKPOINT_CONTRATO_2026-11-01.md\`, matriz de 147 cláusulas. Regras comuns de produto, **jamais migração de código/banco da frente anterior**.

**Requisitos expressos relevantes:**
- 3.9: reversão/regularização de licença implica notificação e oportunidade de regularização; jamais confirmação fictícia.
- 5.3: acesso emergencial técnico exige aviso ao administrador quando viável.
- 3.1-A.1 e 6.1-A: e-mail confirmado e contato verificado quando usado para autenticação/recuperação; convite/aceite ainda sujeitos a autorização.
- 9.2/9.3: notificações do provedor são webhooks autenticados RECEBIDOS e conciliação autoritativa, NÃO avisos de marketing; evento não significa pagamento.
- 11.3: não comunicar "pago" para Pix apenas solicitado; transparência financeira.
- 12/13: identidade, RLS, LGPD, minimização e registros auditáveis como requisitos transversais.

**Ainda SEM decisão contratual específica de implementação:** antecedência de lembretes (ex.: D-7 ou D-1), repetições, janela de silêncio, canais obrigatórios, taxas e custos de WhatsApp, necessidade de opt-in por finalidade, políticas de retenção, provedor e prioridade de mensagens. Não inventar aprovação. Política M15000 apenas enumera categorias iniciais como **PROPOSTA FUNCIONAL**.

## Entrega M14100–M15000

1. 10 categorias de aviso operacional, segurança, licença e obrigação.
2. 3 perfis com isolamento: Master plataforma, Admin de tenant, Membro de tenant.
3. Rejeita aviso financeiro de membro ao Master.
4. Rejeita aviso exclusivo de administrador ao Membro.
5. Rejeita Master com tenant e papéis tenant sem vínculo.
6. Exige evento e destinatário UUIDs não nulos.
7. Exige ano de ciclo para contextos tenant.
8. Exige relógio com timezone.
9. Normaliza carimbos temporais UTC para fingerprint.
10. Exige fingerprint de referência no formato SHA256.
11. Exige alegações de validação da origem e destinatário com bool estrito.
12. Impede payload arbitrário de PII em template.
13. Texto informativo de contribuição não cria cobrança.
14. Status de Pix pendente não vira pago.
15. Conciliação bancária sempre false.
16. Ledger, payout, envio externo sempre false.
17. Canais IN_APP, EMAIL, PUSH, WHATSAPP tipados.
18. Canal externo exige alegação de opt-in.
19. Canal externo exige alegação de contato validado.
20. Canal externo exige alegação de finalidade documentada.
21. Nunca interpreta essas alegações como permissão real de entrega.
22. Lote limitado a 100 itens.
23. Deduplica replay idêntico na mesma identidade.
24. Recusa replay divergente.
25. Recusa cruzamento de tenant no lote.
26. Rotas capacidades exigem sessão autenticada e escopo coerente.
27. Rota de inbox responde 503 até persistência/RLS reais.
28. Health M15000 não declara serviço de envio ativo.
29. Tela Notificações disponível aos três perfis, sem dados seed privados.
30. Nenhuma contagem não lida inventada ou push-token coletado.
31. Testes backend de papéis/consentimentos/duplicidade/segurança.
32. Testes frontend de acesso por papel e ausência de envio fictício.
33. CI GitHub e compilação APK debug.
34. Local Termux não necessita nem aplica migração neste pacote.

## Arquitetura futura necessária antes de habilitar entrega

\`FinancialBusinessEvent\` autenticado e sem PII → roteador de eventos por tenant/recipient → outbox transacional (evento, template versionado, dedup e preferência/canal) → fila com worker autenticado e rate limit → inbox RLS do destinatário → canais externos após confirmação/consentimento → retries, DLQ e auditoria sem segredos → visualização/lido sem cross-tenant.

### Backlog de notificações — P0/P1/P2

P0: tabela \`notification_outbox\` com unique(tenant_id,event_id,recipient_id,channel), isolamento RLS, sessão verificada e inserção transacional autenticada; templates aprovados; aviso separado de liquidação; sem false success. Nada aplicado localmente ainda.

P1: endpoints \`GET /notifications\`, \`POST /notifications/{id}/read\`, cursor paginado/contadores precisos, isolamento Master e Member, preferências e consentimentos versionados, opt-in/opt-out conforme bases legais e LGPD, expiração/revogação de dispositivos.

P1: motor de eventos usando fontes autoritativas e trabalho periódico seguro, calendário por ciclo/vencimento aprovado, sem disparo por simples formulário/claim, sem spam; fallback e política de silêncio.

P1: e-mail (provedor/segredos Vault, SPF/DKIM/DMARC, bounce), push Android/iOS (FCM/APNs, permissão, revogação) e WhatsApp Business API (templates e opt-in, cobrança/rate limit), **somente após habilitação e consentimento aplicáveis**.

P2: experiência de usuário, leitura/unread real, indicador de falha, idioma, acessibilidade, métricas de entregabilidade, auditoria de incidentes de envio, AT-51+ como PROPOSTA de testes adicionais sem alterar matriz 147 ou AT-01–50 aprovadas.

## Escopo não entregue

Nenhuma mensagem real enviada, nenhuma migração SQL local, nenhuma integração FCM/APNs/WhatsApp/SMTP, nenhum webhook Mercado Pago ativado, nenhuma nova autorização financeira, nenhuma base sintética de caixa de entrada exibida como real.

**CHECKPOINT PREVISTO:** BASE \`f47248d\` → M15000 GitHub CI → somente após 6/6 PASS Termux fast-forward. PR #2 segue Draft.
