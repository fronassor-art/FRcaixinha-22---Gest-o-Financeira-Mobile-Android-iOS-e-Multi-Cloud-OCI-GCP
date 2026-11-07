# Pacote 20 — Prévia anual individual comprovável

Baseline: 6e05b4ee0ddf9634c2c96ba712f263588d7b8440
PR #2 Draft; projeto AI Studio Mobile, não FRcaixinha 2.2.

A homologação no APK 180 comprovou uma cota e doze contribuições
pendentes de R$ 100,00 cada, persistidas no PostgreSQL 18 AI Studio.

## Implementação
- Endpoint GET /api/v1/tenants/{tenant_id}/contributions/annual-preview/me?year=2027,
  somente leitura, protegido por sessão TENANT_MEMBER, tenant e PostgreSQL RLS.
- Soma em Decimal no banco: quantidade, pendências, total devido, pago
  REGISTRADO e saldo pendente. Não equivale a valor bancariamente conciliado.
- Profit_amount é SEMPRE null: o endpoint não calcula nem comunica lucro,
  rateio, fechamento, saldos disponíveis ou rendimento não realizado.
- A tela MEU_RESULTADO exibe um resumo PROVISÓRIO com atualização
  por servidor, sem seeds locais e descartando resultados de outra sessão.
- Teste PostgreSQL descartável com dois tenants, dois membros do mesmo
  tenant e administrador/Master recusados. Teste TS com respostas adulteradas.
- Nenhuma migration, contabilização, lançamento, baixa, webhook ou Pix,
  nenhuma mudança de política de crédito ou assinatura do aplicativo.
- O fechamento definitivo continuará indisponível até conciliação e
  validação contratual; o demonstrativo individual não o substitui.
- Inspeção manual programada para checkpoint APK 190.
