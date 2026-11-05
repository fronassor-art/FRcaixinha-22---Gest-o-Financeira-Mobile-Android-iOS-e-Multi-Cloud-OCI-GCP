"""M13100-M14000: ensure staging-only DDL never weakens financial gates."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

BASE=Path(__file__).resolve().parents[1]
SQL=BASE/"staging_migrations/040_orders_incident_audit_staging_only.sql"
SCRIPT=BASE/"scripts/aistudio_staging_chain_ci.sh"


def test_m14000_strict_staging_migration_gate():
    assert SQL.is_file()
    assert not list((BASE/"migrations").glob("040_*.sql"))
    content=SQL.read_text()
    for needle in (
        "BEGIN;", "COMMIT;", "current_database() <> 'frcaixinha_staging'",
        "frcaixinha.orders_staging_authorized",
        "session_user <> 'postgres'",
        "session_user<>'frcaixinha_mp_financial_worker'",
        "ENABLE ROW LEVEL SECURITY", "FORCE ROW LEVEL SECURITY",
        "ON DELETE RESTRICT", "PRIMARY KEY(tenant_id,operation_id,reason_code,sequence)",
        "sha256(convert_to", "pg_advisory_xact_lock",
        "BEFORE UPDATE OR DELETE", "BEFORE TRUNCATE",
        "M040 DENIED: invalid genesis", "M040 DENIED: stale or forged predecessor",
        "M040 DENIED: sequence limit", "M040 DENIED: unauthenticated or unscoped incident append",
        "REVOKE ALL ON TABLE", "REVOKE ALL ON FUNCTION",
        "GRANT EXECUTE ON FUNCTION",
        "hold_active boolean NOT NULL DEFAULT true",
        "financial_effect_applied boolean NOT NULL DEFAULT false",
        "bank_reconciled boolean NOT NULL DEFAULT false",
        "ledger_written boolean NOT NULL DEFAULT false",
        "payout_authorized boolean NOT NULL DEFAULT false",
    ):
        assert needle in content, needle
    assert content.count("BEGIN;") == 1
    assert content.count("COMMIT;") == 1


def test_m14000_function_only_audit_write_without_money():
    code=SQL.read_text().split(
        "CREATE OR REPLACE FUNCTION public.mp_orders_staging_append_incident_audit",1
    )[1]
    for forbidden in (
        "UPDATE public.mp_pix_collection_operations_staging",
        "INSERT INTO public.ledger_entries",
        "INSERT INTO public.mp_pix_receipts_staging",
        "UPDATE public.ledger_transactions",
        "DELETE FROM public.mp_orders_reconciliation_holds_staging",
        "GRANT INSERT ON TABLE",
        "GRANT UPDATE ON TABLE",
        "CREATE POLICY",
    ):
        assert forbidden not in code
    assert "INSERT INTO public.mp_orders_incident_audit_staging" in code
    assert "operator_authenticated boolean NOT NULL DEFAULT true" not in SQL.read_text()


def test_m14000_runner_is_explicitly_disposable_and_isolated():
    script=SCRIPT.read_text()
    for needle in (
        'FRCAIXINHA_CI_ISOLATED', 'GITHUB_ACTIONS',
        'frcaixinha_staging', 'PGPORT:-', 'ci-test-only',
        '040_orders_incident_audit_staging_only.sql',
        '037_staging_incident_audit_probe_ci_only.sql',
        'test_m14000_staging_audit_persistence_ci.py',
    ):
        assert needle in script, needle


def test_m14000_api_only_reports_features_not_payment_permission():
    with TestClient(app) as client:
        resp=client.get("/api/health/features/m14000")
    assert resp.status_code==200
    d=resp.json()
    assert d["workstream"]=="AI_STUDIO"
    assert d["contract"]=="AI_STUDIO_M14000_STAGING_INCIDENT_AUDIT_DISPOSABLE_V1"
    assert d["staging_sql_prepared"] is True
    assert d["ci_only_pg16_pg18_exercised"] is True
    for key in (
        "local_migration_applied","oci_staging_deployed",
        "real_audit_history_connected","operator_authenticated",
        "bank_reconciled","real_payments_enabled",
        "financial_effect_applied","ledger_written","payout_authorized",
        "financial_closing_authorized","real_provider_get_active",
    ):
        assert d[key] is False, key
    assert "/api/v1/orders/mark-paid" not in {route.path for route in app.routes}
