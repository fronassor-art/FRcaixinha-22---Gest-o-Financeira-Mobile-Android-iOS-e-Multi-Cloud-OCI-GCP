# FR Finance M40240 — índice do catálogo PostgreSQL

- `backend/scripts/frfinance_m40240_pg18_rls_catalog_readonly.sql`: SQL transacional READ ONLY e quatro guardas reais
- `backend/scripts/frfinance_m40240_pg18_rls_catalog_readonly.sh`: entrada de senha oculta, identidade original e conexão fixa sem configurações herdadas
- `backend/tests/test_m40240_pg18_rls_catalog_ci.py`: regressões sintéticas e verificação de catálogo SQL versus migração 110
- `.github/workflows/frfinance-m40240-pg18-rls-catalog-ci.yml`: testes GitHub Actions
- `docs/FR_FINANCE_M40240_RLS_CATALOG.md`: escopo e limitações

PR #2 permanece em rascunho. FR Caixinha 2.2 excluído. Nenhuma migração ou alteração de servidor.
