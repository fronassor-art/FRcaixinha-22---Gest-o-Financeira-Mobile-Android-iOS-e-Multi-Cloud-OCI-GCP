# FR Finance M39910 — históricos documentais nos caixas do Master e Administrador

Data: 14/11/2026. Base de continuidade: M39900, GitHub PR #2 Draft.
Termux: M39800 sincronizado em `fedadfd`, API `FR_FINANCE_ONLINE`,
`ANDROID_PROC_RESTRICTED`, `BLOCKED_NO_PROCESS_PROOF`. Nenhum reinício
é permitido ou efetuado nesta etapa.

## Contrato da entrega

O **Master** possui domínio patrimonial exclusivo `PLATFORM_MASTER`
(SaaS, licenças e despesas próprias da plataforma). O **Administrador da
Caixinha** tem domínio próprio `TENANT_ADMIN_OWN` para sua remuneração
eventualmente apurada e domínio diferente `TENANT_COLLECTIVE` para
contribuições, crédito, amortizações e custos da caixinha. Nenhum desses
domínios é a conta bancária da plataforma.

A regra contratual em vigor para apuração anual permanece **15% do
lucro líquido real elegível para o administrador / 85% para membros
elegíveis por Capital-Dias**. O valor depende de política versionada
do ciclo, prova de resultado, elegibilidade, fechamento e conciliação.
Esta entrega NÃO apura comissão, não cria extrato bancário nem calcula
saldo ou competência.

## API GET M39910

- `GET /api/v1/master/exclusive-cashbox/history`: apenas Master
  autenticado. Até 10 eventos mais recentes de intenções de cobrança
  SaaS e preparações de assinatura, sem identificadores de tenant,
  pagador, valores, referências externas, tokens ou prova bancária.
- `GET /api/v1/tenants/{tenant_id}/admin-exclusive-cashbox/history`:
  apenas Administrador titular autenticado, tenant ativo e RLS; até
  10 registros temporais do Livro-Razão **coletivo**, sempre rotulados
  `RECORDED_NOT_REMUNERATION`. Não existe histórico pessoal de
  remuneração comprovado nesta etapa.
- Ambos usam SQL exclusivamente SELECT, respostas `Cache-Control:
  private, no-store`, `Pragma: no-cache`, `Vary: Authorization`,
  `available_balance_cents=null`, `amount_cents=null`,
  `settlement_verified=false`, `cash_movement_verified=false`,
  `transfer_enabled=false`. Estado `DOCUMENTARY_ONLY_NOT_RECONCILED`.
- Os status SaaS `APPROVED` e `PENDING_PAYMENT` são eventos
  administrativos, **não provam receita recebida**. A API não fornece
  método POST de histórico, não faz conciliação nem transação.
- Ordens em UTC com quebra de empate por identificador; validar datas,
  IDs e status, limitar dados e devolver HTTP 503 em valores não
  comprovados, sem expor registros no erro.

## Aplicativo

`src/services/exclusiveCashboxHistoryBoundary.ts` rejeita alteração de
escopo, tenant cruzado, eventos desconhecidos, duplicatas, ordem errada,
campos a mais, valor numérico ou promessa de transferência. Na interface,
a requisição do histórico é **independente** do painel M39090: erro 404
do FastAPI anterior só torna o histórico indisponível, sem inventar
lançamentos e sem esconder os demais registros autorizados.

Testes de regressão em backend sintético (sem PostgreSQL) e frontend
contemplam papel Master, Admin titular, membro, não titular, troca
de tenant, origem e estado de registros, limite, cache, e ausência de
saldos e remuneração fictícios.

## Pendências para operabilidade financeira real

Persistência segregada e imutável de receitas liquidadas SaaS, despesas
com documento, contas de titularidade e diário de remuneração pessoal
ainda **não implementados**. Projetar migrações futuras somente após
revisão contratual, autorização expressa e CI de PostgreSQL descartável,
com apuração por competência, idempotência, estorno e reconciliação
provada com o provedor. Somente então considerar saldo/saque real.

## Portas e limites

- PostgreSQL original FR Finance: porta 5433; não acessar por M39910.
- PostgreSQL FR Caixinha 2.2: outro projeto; intocado.
- FastAPI original porta 8000: sem reiniciar; a inspeção do processo
  continua bloqueada pela política Android até prova manual separada.
- `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`,
  `ATIVACAO_REAL=OFF`, `MIGRACOES_LOCAIS=NONE`,
  `DATABASE_WRITES=NONE`, `PRODUCAO=BLOCKED`.

A publicação no GitHub não comprova implantação Android nem runtime.
A sincronização posterior do Termux deve ser apenas fast-forward sem
reiniciar API, migrar banco, reabrir produção ou movimentar recursos.
