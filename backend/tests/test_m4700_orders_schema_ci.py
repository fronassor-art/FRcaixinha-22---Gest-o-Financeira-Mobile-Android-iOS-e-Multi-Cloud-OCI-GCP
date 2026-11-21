"""M4700 Orders schema staging guard and real-payment reservation boundaries."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT/"staging_migrations/037_orders_payment_link_staging_only.sql"


def test_order_schema_037_only_in_staging_and_requires_all_prerequisites():
    assert SQL.is_file()
    assert not (ROOT/"migrations"/SQL.name).exists()
    data=SQL.read_text()
    for expected in (
        "frcaixinha_staging","frcaixinha.orders_staging_authorized",
        "current_setting('is_superuser')<>'on'",
        "mp_pix_collection_operations_staging",
        "mp_pix_receipts_staging","mp_signed_order_inbox_staging",
        "provider_order_id varchar(80)",
        "mp_orders_provider_reads_staging",
        "order_id varchar(80)",
        "payment_id varchar(80)",
        "get_checked_at",
        "CHECK(bank_reconciled=false)",
        "CHECK(ledger_written=false)",
        "FORCE ROW LEVEL SECURITY",
        "REVOKE ALL",
    ):
        assert expected in data
    assert "COMMIT;" in data


def test_orders_new_contract_keeps_real_money_disabled_in_default_backend():
    with TestClient(app) as client:
        r=client.get("/api/health/features/m4800")
    assert r.status_code==200
    payload=r.json()
    assert payload["workstream"]=="AI_STUDIO"
    assert payload["contract"]=="AI_STUDIO_M4800_MLB_ORDERS_CONNECT_MONEYOUT_MACRO_V1"
    assert payload["orders_gateway_code_present"] is True
    assert payload["money_out_unsigned_production_blocked"] is True
    assert payload["orders_staging_migrations_applied"] is False
    assert payload["real_payments_enabled"] is False
    assert payload["bank_reconciled"] is False
    assert payload["ledger_written"] is False
    assert payload["oci_staging_deployed"] is False
