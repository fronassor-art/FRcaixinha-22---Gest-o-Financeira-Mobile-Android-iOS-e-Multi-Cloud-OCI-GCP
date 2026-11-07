"""M6400: runtime acknowledges only PREPARED code, not connected money."""
from fastapi.testclient import TestClient
from app.main import app


def test_backend_m6400_fails_closed_even_after_code_present():
    with TestClient(app) as client:
        resp=client.get("/api/health/features/m6400")
    assert resp.status_code==200
    d=resp.json()
    assert d["workstream"]=="AI_STUDIO"
    assert d["contract"]=="AI_STUDIO_M6400_STAGING_SQL_LEDGER_LIQUIDITY_PREFLIGHT_V1"
    assert d["ledger_plan_contract"]=="AI_STUDIO_M6000_ORDERS_BALANCED_LEDGER_PLAN_V1"
    assert d["reversal_plan_contract"]=="AI_STUDIO_M6100_NONDESTRUCTIVE_REVERSAL_PLAN_V1"
    assert d["liquidity_contract"]=="AI_STUDIO_M6200_TENANT_LOAN_LIQUIDITY_PREFLIGHT_V1"
    assert d["staging_chain_ci_contract"]=="CI_PG16_PG18_M034_M038_V1"
    for key in (
        "ledger_plan_code_present",
        "reversal_preview_code_present",
        "credit_liquidity_preflight_code_present",
    ):
        assert d[key] is True,key
    for key in (
        "staging_migrations_applied",
        "staging_sql_chain_executed_in_termux",
        "oci_staging_deployed",
        "oci_apply_authorized",
        "real_bank_balance_reader_connected",
        "real_bank_statement_reader_connected",
        "provider_connected",
        "real_payments_enabled",
        "bank_reconciled","ledger_written","financial_effect_applied",
        "financial_closing_authorized","payout_authorized",
    ):
        assert d[key] is False,key


def test_orders_webhook_is_still_not_exposed_to_termux():
    paths={r.path for r in app.routes}
    assert "/integrations/mercadopago/orders" not in paths
