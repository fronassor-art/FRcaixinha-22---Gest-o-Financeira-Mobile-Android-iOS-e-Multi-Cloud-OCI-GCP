# FR Finance M40880 — Android status bar + inventário SQL113 (NO-GO)

**Base:** M40850 `3694134`, sincronizado no Termux conforme resultado do operador. Nenhum processo FastAPI foi recarregado.

## M40860 — Android: remover safe-area superior duplicada

A janela `#root` já aplica `--fr-safe-top`. O `main.fr-page` aplicava novamente `max(1.5rem, var(--fr-safe-top))`, aumentando o espaço no topo e podendo deslocar a marca e o login sob a barra de status ou após logout/teclado. Agora o inset superior pertence apenas ao `#root`; o login recebe padding interno fixo `1.5rem`, `box-sizing:border-box`, `min-h-0 h-full` e continua com scroll/altura em função do viewport visual.

A CI exercita SSR, estrutura de tela, top reset e cálculo de teclado. **Somente o teste físico Android poderá confirmar** o posicionamento no aparelho com barras do sistema, teclado, logout e rotação. Não houve instalação de APK ou reinício do FastAPI.

## M40870 — SQL113 permanece com dependência GUC

Uma auditoria somente leitura registra explicitamente as políticas RLS Master de `platform_saas_promotion_revisions` com `current_setting('app.current_*')`, a função `SECURITY DEFINER` que confia nos GUCs, o grant EXECUTE à role app e o endpoint que chama a função. Este é inventário de código, **não inspeção do catálogo PostgreSQL original**, nem comprovação de aplicação SQL113. M40570 (GUC spoof sob SQL arbitrário) e M40730 (emissor SQL roubado contornando PoP) **permanecem NO-GO**. A trava M40840 de pool financeira em produção continua obrigatória. Não há migração segura ou revogação de ACLs disponível neste pacote.

O futuro redesenho exige funções SQL sem GUC como autoridade, verificador independente de sessão, revisão de todas as grants/rotas e prova no PostgreSQL 18 descartável antes de uma migração explícita com backup, rollback e autorização.

`MIGRATIONS=NONE`; `DB_CONNECTIONS=NONE`; `DB_WRITES=NONE`; `SERVICE_RESTARTS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`. PR #2 Draft; main, FR Caixinha 2.2, banco original e Termux preservados.
