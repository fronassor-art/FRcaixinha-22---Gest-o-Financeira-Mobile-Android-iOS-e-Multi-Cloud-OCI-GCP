# Aditivo técnico M40160 — recuperação offline PG18

- Diagnóstico: `backend/scripts/frfinance_m40160_original_pg_control_offline_readonly.py`
- Testes: `backend/tests/test_m40160_original_pg_control_offline_ci.py`
- CI: `.github/workflows/frfinance-m40160-pg-control-offline-ci.yml`
- Documento de escopo e restrições: `docs/FR_FINANCE_M40160_OFFLINE_PG_CONTROL_RECOVERY.md`

Restrições herdadas do M40150 preservadas: FR Finance somente, PostgreSQL 18 original, FR 2.2 fora do escopo, PR #2 em rascunho, produção e pagamentos reais OFF, nenhum início/reinício de processo, nenhuma mutação em banco.
