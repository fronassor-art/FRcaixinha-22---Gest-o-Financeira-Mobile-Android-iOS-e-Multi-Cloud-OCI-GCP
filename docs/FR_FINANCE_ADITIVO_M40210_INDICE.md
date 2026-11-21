# FR Finance M40210 — índice do inventário público versus oculto

- `backend/scripts/frfinance_m40210_hidden_route_openapi_correction.py`: 33 rotas públicas mais duas ocultas verificadas apenas na fonte
- `backend/tests/test_m40210_hidden_route_openapi_ci.py`: testes AST/HTTP sintéticos contra falsos positivos
- `.github/workflows/frfinance-m40210-hidden-route-openapi-ci.yml`: CI
- `docs/FR_FINANCE_M40210_HIDDEN_ROUTES.md`: causa, evidências e limitações

Preserva a configuração `include_in_schema=False`; nenhuma rota alterada, exposição adicional, reinício, migração ou escrita de banco. FR Caixinha 2.2 fora do escopo. PR #2 em rascunho.
