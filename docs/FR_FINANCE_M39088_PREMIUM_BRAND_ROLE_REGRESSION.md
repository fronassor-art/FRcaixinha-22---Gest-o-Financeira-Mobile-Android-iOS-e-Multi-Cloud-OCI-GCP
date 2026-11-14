# FR Finance M39088 — Marca premium e segregação de oportunidades no frontend

Data de origem: 13/11/2026. PR #2 da branch AI Studio continua draft.

## Resultado do Termux M39087
- Fast-forward confirmado: commit `bd146d649a849aa9a46e3941bb99d5acf51bc63f`.
- Testes Python (backup client wrapper, guardas de CI e catálogo): **11 PASS**.
- Testes TSX Android safe area, isolamento dos papéis e prontidão de ciclo do crédito: **PASS**.
- Sem acesso ao banco original, migrações, Pix ou ativação.

## GitHub Actions na mesma revisão
- Workflow geral `Validação da atualização AI Studio` execução `43543980415`.
- PostgreSQL 16 descartável com backup cifrado age e restauração: **SUCCESS**.
- API sem banco, PostgreSQL 18 preflight, migrações CI e empacotamento: **SUCCESS**.
- Frontend falhou exclusivamente no teste `src/tests/premium_brand_ui.test.ts`, cuja expectativa histórica de menu `TENANT_MEMBER` não incluía `MINHAS_OPORTUNIDADES` introduzida na M39076; o APK dependente foi pulado.

## Mudanças M39088
- Alinhado teste de identidade visual para esperar exatamente as seis abas vigentes de membro, incluindo `MINHAS_OPORTUNIDADES`.
- Negativas explícitas: Master e TENANT_ADMIN não enxergam `MINHAS_OPORTUNIDADES`; Master e TENANT_MEMBER não enxergam `CAMPANHAS_MEMBROS`, que é exclusiva do administrador da caixinha.
- Nenhuma modificação em `src/App.tsx`, `roleScope.ts`, componentes de crédito, código backend, SQL ou banco original.
- Workflow específico `frfinance-m39088-premium-brand-ci.yml` mantém TypeScript 7 oficial no Ubuntu e valida testes históricos de navegação, campanhas, ciclo e safe area.

## Critérios de aceite
- Execução do novo workflow e da CI geral na nova revisão: PASS para o escopo correspondente; não presumir antes do GitHub concluir.
- Termux: `tsx` para testes de marca, navegação, prontidão de ciclo e safe area; árvore Git limpa.
- APK debug somente depois de todas as dependências da CI geral aprovadas, sem atualizar o aplicativo instalado automaticamente. Assinatura persistente e artefatos devem ser avaliados separadamente.
- Produção permanece bloqueada. `FR_FINANCE_PIX_REAL=OFF`, `FR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO`, provedores externos inativos, sem migrações locais.
