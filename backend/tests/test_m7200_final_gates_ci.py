"""M7200: local feature health NEVER activates economic effects."""
from fastapi.testclient import TestClient
from app.main import app


def test_m7200_capabilities_are_readonly_and_honest():
    with TestClient(app) as cli:
        r=cli.get("/api/health/features/m7200")
    assert r.status_code==200
    d=r.json()
    assert d["workstream"]=="AI_STUDIO"
    assert d["contract"]=="AI_STUDIO_M7200_RECONCILIATION_HOLDS_DISPOSABLE_LEDGER_V1"
    assert d["reconciliation_holds_contract"]==(
        "AI_STUDIO_M6600_DURABLE_ORDERS_RECONCILIATION_HOLDS_V1")
    assert d["partial_refund_contract"]==(
        "AI_STUDIO_M6800_PARTIAL_REFUND_PREVIEW_V1")
    for key in (
        "staging_reconciliation_hold_schema_prepared",
        "disposable_pg16_pg18_ledger_test_present",
        "orders_persisted_checkout_binding_hardened",
        "partial_refund_preview_present",
    ):
        assert d[key] is True,key
    for key in (
        "reconciliation_incident_logged_to_real_bank",
        "staging_m039_applied_locally",
        "oci_staging_deployed","real_provider_connected",
        "real_bank_statement_reader_connected",
        "real_bank_balance_reader_connected",
        "real_payments_enabled","real_pix_payout_active",
        "bank_reconciled","ledger_written",
        "financial_effect_applied",
        "financial_closing_authorized","payout_authorized",
    ):
        assert d[key] is False,key


def test_no_webhook_or_real_settlement_exposed_publicly():
    paths={r.path for r in app.routes}
    for forbidden in (
        "/integrations/mercadopago/orders",
        "/integrations/mercadopago/webhook",
        "/api/v1/staging/ledger/post",
        "/api/v1/financial/settle",
        "/api/v1/financial/money-out",
    ):
        assert forbidden not in paths
