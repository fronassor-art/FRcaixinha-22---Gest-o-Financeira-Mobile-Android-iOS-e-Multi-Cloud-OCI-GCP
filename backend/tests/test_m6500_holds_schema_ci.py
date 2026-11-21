"""M6500-6600: staging holds append-only, no settlement/ledger authority."""
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
SQL=BASE/"staging_migrations/039_orders_reconciliation_holds_staging_only.sql"


def test_staging_only_migration_guard():
    assert SQL.exists()
    assert not list((BASE/"migrations").glob("039_*.sql"))
    s=SQL.read_text()
    assert s.count("BEGIN;")==1 and s.count("COMMIT;")==1
    for anchor in (
        "current_database()<>'frcaixinha_staging'",
        "frcaixinha.orders_staging_authorized",
        "current_setting('is_superuser') <> 'on'",
        "frcaixinha_mp_financial_worker",
        "NOT rolsuper AND NOT rolbypassrls",
        "mp_orders_staging_reserve",
        "mp_orders_reconciliation_holds_staging",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
        "PRIMARY KEY(tenant_id,operation_id,reason_code)",
        "FOREIGN KEY(tenant_id,operation_id)",
        "ON DELETE RESTRICT",
        "REVOKE ALL ON TABLE",
        "REVOKE ALL ON FUNCTION",
        "GRANT EXECUTE ON FUNCTION",
    ):
        assert anchor in s,anchor


def test_append_only_incident_never_marks_paid():
    s=SQL.read_text()
    function=s.split(
        "CREATE OR REPLACE FUNCTION public.mp_orders_staging_record_hold",1)[1]
    assert "session_user<>'frcaixinha_mp_financial_worker'" in function
    assert "c.tenant_id=p_tenant AND c.operation_id=p_operation" in function
    assert "c.environment='HOMOLOGACAO'" in function
    assert "EXISTS" in function
    assert "pg_advisory_xact_lock" in function
    assert "FOR UPDATE" in function
    assert "RETURN 'REPLAY'" in function
    assert "RETURN 'NEW'" in function
    for disallowed in (
        "UPDATE public.mp_pix_collection_operations_staging",
        "UPDATE public.ledger_transactions",
        "INSERT INTO public.ledger_entries",
        "INSERT INTO public.mp_pix_receipts_staging",
        "GRANT INSERT ON",
        "GRANT UPDATE ON",
        "CREATE TRIGGER",
    ):
        assert disallowed not in function


def test_only_worker_executes_and_no_master_financial_access():
    s=SQL.read_text()
    assert "TO frcaixinha_mp_financial_worker" in s
    assert "FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role" in s
    assert "financial_effect_applied=false" in s
    assert "ledger_written=false" in s
    assert "bank_reconciled=false" in s
    assert "payout_authorized=false" in s
