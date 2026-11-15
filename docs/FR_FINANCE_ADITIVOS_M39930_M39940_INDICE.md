# FR Finance — Índice de aditivos técnicos M39930–M39940

Complementa, sem reescrever,
`docs/FR_FINANCE_ADITIVOS_M39900_M39920_INDICE.md`.

A baseline normativa e o checklist M39100 de 330 requisitos e
2310 etapas continuam selados e **não foram alterados**. Este índice
não representa revisão contratual assinada, aceite jurídico ou
autorização de operação financeira.

## Aditivos do diário e de evidências

- **M39930** —
  `docs/FR_FINANCE_M39930_RLS_DIARIO_IMUTAVEL_CI.md`:
  ensaio descartável em PostgreSQL 18 de diários segregados,
  dupla entrada diferida, bloqueio de atualização e exclusão,
  antirrepetição de referência e RLS com cenários de Master,
  administradores de dois tenants e membro sem acesso.
  **Não existe migração do PostgreSQL original.**
- **M39940** —
  `docs/FR_FINANCE_M39940_PREFLIGHT_EVIDENCIAS_CAIXAS.md`:
  contrato puro de associação documental por evento e escopo,
  conferência estrutural de centavos, revisão distinta proposta,
  prévia matemática de 15% somente para administrador e
  **negação explícita** de prova autenticada, caixa disponível,
  pagamento, postagem no livro-razão ou autorização de saque.

## Pendências antes de qualquer migração original

Provar server-side a identidade do operador, titularidade do tenant,
versão da política e fechamento do ciclo, origem independente e
liquidação dos eventos de Mercado Pago, comprovantes válidos de
despesas, estornos, imutabilidade de documentos, idempotência
transacional, reconciliação e segregação de funções. Aplicar novas
migrações locais somente com autorização específica, auditoria e
backup confirmado. Proteger o PostgreSQL FR Finance (5433) do
FR Caixinha 2.2 independente.

`PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`;
`ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
