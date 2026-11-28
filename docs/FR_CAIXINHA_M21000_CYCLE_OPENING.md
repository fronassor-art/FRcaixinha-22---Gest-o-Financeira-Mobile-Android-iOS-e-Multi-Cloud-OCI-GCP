# M21000 — abertura de ciclo com escolha explícita (SQL preparado)

A migração LOCAL 044 é incremental e adiciona tabela imutável de auditoria de abertura e função transacional cycle_open_create. Exige M042, M043 e PostgreSQL exclusivo AI Studio.

O ADMIN da própria caixinha escolhe ano futuro, valor ≥ R$150 por cota e justificativa. A autenticação depende de sessão validada pelo PostgreSQL; o ciclo anterior deve estar LIQUIDADO. O bloqueio por tenant impede concorrência; reenvio idêntico usa a mesma idempotency_key. O ciclo e a política são criados juntos, ou nenhum.

NÃO cria obrigações, contribuições, pagamentos, Pix, ledger, rateios ou qualquer movimento financeiro. A auditoria é append-only com RLS.

**Ainda NÃO foi aplicada no Termux**; 45 tabelas e 043 permanecem último estado comprovado. Até revisão e aplicação 044, painel M20900 é apenas prévia, nenhum endpoint real permite abertura. Backups AGE, instalador e rota do backend continuam pendentes de pacote posterior.

Os testes CI são descartáveis e não aprovam automaticamente o banco local. A correção das 12 competências de R$100 permanece pendente de autorização e procedimento auditado.
