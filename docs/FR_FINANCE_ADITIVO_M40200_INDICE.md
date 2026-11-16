# FR Finance M40200 — checkpoint de inventário funcional

- Diagnóstico GET-only: `backend/scripts/frfinance_m40200_feature_routes_readonly.py`
- Regressões sintéticas + AST dos routers: `backend/tests/test_m40200_feature_routes_readonly_ci.py`
- GitHub Actions: `.github/workflows/frfinance-m40200-feature-routes-ci.yml`
- Escopo e limitações: `docs/FR_FINANCE_M40200_FEATURE_ROUTES.md`

Sem migração e sem mutação do PostgreSQL original, FR Caixinha 2.2 intocado, PR #2 rascunho, PIX real OFF.
