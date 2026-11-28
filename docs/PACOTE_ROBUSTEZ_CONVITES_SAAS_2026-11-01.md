# AI Studio — Auditoria de robustez do ciclo de convites e SaaS

**Escopo**: PR #2, branch `atualizacao-ai-studio-9b46a63187`. Este
documento complementa o pacote 017/018, sem habilitar nenhum efeito real.

## Correções desta rodada

1. **Webhooks Mercado Pago em milissegundos** — a assinatura
   `x-signature` pode conter `ts` com 13 dígitos (milissegundos). O
   verificador admite também 10 dígitos legados (segundos), converte
   **somente para o cálculo da janela de ±300s** e mantém o timestamp
   original no manifesto HMAC. Recusa duplicação de campo `ts`, pagamento
   com ID divergente e notificações antigas/futuras. A assinatura não é
   prova de liquidação; exige GET autenticado ao provedor.

2. **SMTP cifrado e links de convite** — senha SMTP não é enviada quando
   `STARTTLS` foi desabilitado; o adaptador falha fechado. O link utiliza
   fragmento `#token=...` em vez de query `?token=...`, para não
   transmitir o segredo no request inicial nem em logs HTTP comuns.
   A futura página de aceite deve **remover o fragmento do histórico
   imediatamente**, impedir scripts de terceiros e enviar o token somente
   por POST seguro. A página ainda **não está habilitada** e o adaptador
   não envia e-mails sem as autorizações de governança.

3. **Conta existente: consentimento obrigatório** — o executor CI de
   `accept_existing_identity_ci` agora exige `consent=True`,
   `document_id` publicado na modalidade TENANT_MEMBERSHIP e a versão
   `required_document_id` previamente vinculada ao convite. Somente
   então cria o vínculo e registra aceite individual auditável, em
   uma única transação. Sem consentimento, sem versão, ou com versão
   errada, não altera o banco. Retornos de erro, vínculos duplicados
   e mudança de privilégios do convidante seguem bloqueados.
   O teste usa **prova sintética**, não assinatura válida juridicamente.

4. **Conciliação repetida** — mesmo para status APPROVED, o executor CI
   revalida identificador do pagamento, conta cobradora, referência,
   moeda, valor exato e live_mode antes de retornar a licença existente.
   A repetição válida devolve a mesma licença, sem gerar nova vigência.

5. **Estornos integrais vs. parciais** — revogação por reembolso exige
   a resposta autoritativa com `status=refunded` e
   `transaction_amount_refunded` **exatamente igual** ao valor da
   cobrança original, além das verificações de conta, moeda e referência.
   Campo ausente, float, valor parcial ou divergente fazem o fluxo
   falhar fechado. Estornos parciais permanecem pendentes de política
   contratual específica. Não executar pedidos de reembolso: apenas
   observar eventos confirmados.

6. **Replay de webhook** — evento repetido com mesmo request-id e
   mesmos dados retorna idempotência; request-id repetido com payload
   divergente gera erro, preservando a auditoria imutável. Nenhum webhook
   ativa a licença sem consulta GET autenticada.

## Cobertura técnica

- `test_platform_provider_adapters.py`: HMAC com timestamp ms/seg,
  tolerância de tempo, assinatura alterada, SMTP STARTTLS, fragmentos de
  URL e comportamento bloqueado por padrão.
- `test_mercado_pago_safety.py`: critérios para aprovação e reembolso
  integral, impedimento de float impreciso, valor parcial e dados de
  outra conta.
- `test_aistudio_live_engines_ci.py`: replay de webhook diferente,
  conciliação repetida válida e inválida, estorno parcial/total e
  preservação de licenças.
- `test_aistudio_account_lifecycle_ci.py`: contrato do convite,
  consentimento explícito, isolamento por identidade, registro de
  aceite, duplicidade e rollback de teste. Usa transação de teste
  que é desfeita, evitando exclusão de aceites imutáveis.

## Restrições e critérios de saída

Não há nova migração nesta rodada: a sequência permanece **001–018**.
O CI usa PostgreSQL descartável. O PostgreSQL do Termux
(`frcaixinha_aistudio_dev`, 18.6, porta 5433) deve manter **zero
tabelas** até autorização expressa do proprietário.

**Não criar usuários reais, enviar convites, configurar flags de
`AI_STUDIO_REAL_*`, cobrar Pix, revogar licença real nem instalar APK.**
As funções com sufixo `_ci` não são caminhos de produção. A implementação
real ainda exige endpoint público validado, identidade/autorização,
infraestrutura de e-mail e credenciais do Mercado Pago da plataforma
no gerenciador de segredos, conciliação de estornos e revisão jurídica.

A aprovação no GitHub Actions comprova apenas o escopo testado; não
significa autorização para produção nem reclassifica automaticamente
as 147 cláusulas históricas.

## Fontes técnicas

- Mercado Pago: documentação de validação HMAC em
  https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/optional-notifications
- Mercado Pago: consulta de reembolsos em
  https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api-payments/get-refunds/get
