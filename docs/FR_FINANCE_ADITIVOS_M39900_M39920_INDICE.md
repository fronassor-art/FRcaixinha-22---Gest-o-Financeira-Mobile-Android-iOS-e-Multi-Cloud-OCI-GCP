# FR Finance — Aditivos de Engenharia M39900–M39920

**Data de registro:** 15/11/2026. **Escopo:** FR Finance AI Studio,
PR #2 Draft. Este documento funciona como índice de aditivos; não substitui
o Caderno Mestre nem o Contrato Técnico Mestre selados no checkpoint
`FR_FINANCE_CP20261114_CHECKLIST_INTEGRAL_330_V1`.

## Baseline contratual selada

- `docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md`: preservado no
  blob Git SHA-1 `535e3d745c214de6ec4cd716edafaa374fb2c572`.
- `docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md`:
  preservado no blob Git SHA-1
  `0572456988908465d6ef7f09183cb39c02400c77`.
- Auditor `backend/app/m39100_full_traceability.py` rastreia 330 itens,
  2310 tarefas, 147 cláusulas históricas e as evidências de produção,
  sem jamais permitir elevar status de produção por mera alteração documental.
- O bloqueio `M39100_SOURCE_BLOB_DRIFT` foi corrigido restaurando o
  conteúdo **idêntico ao hash original**, não desativando nem enfraquecendo
  a comparação de origem, contagem ou exigências de aceite.

## Aditivos subsequentes (não absorvidos pelo checklist congelado)

1. `docs/FR_FINANCE_M39900_CAIXAS_MASTER_ADMIN_CONTINUIDADE.md`:
   distingue Master SaaS, administração própria e caixa coletivo;
   orienta os painéis documentais e suas pendências.
2. `docs/FR_FINANCE_M39910_HISTORICO_DOCUMENTAL_CAIXAS.md`:
   estabelece histórico somente leitura e sem valores, status ou saques
   não comprovados, com papéis e RLS.
3. `docs/FR_FINANCE_M39920_ESCRITURACAO_PREPARACAO_CAIXAS.md`:
   descreve pré-escrituração pura, partidas dobradas, fingerprint de
   candidato e CI PostgreSQL descartável com ROLLBACK.

**Política de prevalência:** os aditivos são especificações incrementais
subordinadas à baseline contratual; não mudam os 330 itens ou os 2310
estágios imutáveis, não introduzem aprovação de produção, não alteram
o rateio 15%/85% e não criam efeitos jurídicos de assinatura por si sós.
Uma nova versão de checklist selado com inclusão formal das cláusulas
será necessária para incorporá-las ao caderno normativo, mediante
revisão e aprovação documental específicas.

## Proibição operacional

`PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`,
`DATABASE_WRITES_ORIGINAL=NONE`, `MIGRACOES_LOCAIS=NONE`,
`FASTAPI_RESTART=NONE`, `PRODUCAO=BLOCKED`. PostgreSQL FR Finance
porta 5433 e FR Caixinha 2.2 em outro cluster permanecem isolados.
