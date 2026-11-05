"""M5500: financial and payout operations stay forbidden at the default runtime."""
from fastapi.testclient import TestClient
from app.main import app


def test_m5600_health_reports_code_but_no_financial_operation():
    with TestClient(app) as client:
        res=client.get("/api/health/features/m5600")
    assert res.status_code==200
    data=res.json()
    assert data["workstream"]=="AI_STUDIO"
    assert data["contract"]=="AI_STUDIO_M5600_ORDERS_RESERVATION_CREDIT_CORRECTION_V1"
    for field in (
        "reservation_contract","settlement_contract",
        "recovery_contract","payout_price_contract",
    ):
        assert data[field].startswith("AI_STUDIO_M")
    for field in (
        "loan_approval_creates_installments",
        "uncertain_pix_repost_allowed",
        "orders_m038_migration_applied",
        "real_bank_statement_reader_connected",
        "atomic_ledger_worker_connected",
        "provider_connected","oci_staging_deployed",
        "real_payments_enabled","real_pix_collection_active",
        "real_pix_payout_active","bank_reconciled","ledger_written",
        "financial_effect_applied","financial_closing_authorized",
        "payout_authorized",
    ):
        assert data[field] is False,field
    for field in (
        "confirmed_payout_requires_tenant_timezone",
        "orders_staging_reservation_code_present",
        "three_source_settlement_preflight_present",
    ):
        assert data[field] is True,field


def test_order_webhook_still_not_public_after_new_modules():
    paths={r.path for r in app.routes}
    assert "/integrations/mercadopago/orders" not in paths
    assert "/integrations/mercadopago/webhook" not in paths
