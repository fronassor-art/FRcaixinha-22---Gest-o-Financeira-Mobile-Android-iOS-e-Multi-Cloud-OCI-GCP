# FR Finance M40230 — índice de isolamento de perfis

- `backend/scripts/frfinance_m40230_role_rls_source_readonly.py`: limites de sessão, tenant e transação (somente AST local)
- `backend/tests/test_m40230_role_tenant_boundaries_ci.py`: casos negativos sintéticos para Master, administrador, membro, titularidade e crédito especial
- `.github/workflows/frfinance-m40230-role-tenant-isolation-ci.yml`: regressões no GitHub Actions
- `docs/FR_FINANCE_M40230_ROLE_TENANT_ISOLATION.md`: evidências e limitações

FR Finance original preservado; FR Caixinha 2.2 fora do escopo. Não executar SQL, migrações, reinícios ou operações reais. PR #2 segue rascunho.
