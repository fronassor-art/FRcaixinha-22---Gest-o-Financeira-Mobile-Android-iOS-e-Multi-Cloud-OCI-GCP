"""M3700 — staging-only SQL is opt-in and not a Termux migration."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

ROOT=Path(__file__).resolve().parents[1]


def test_035_is_exclusive_staging_not_local_migration_or_ci():
    path=ROOT/"staging_migrations/035_pix_payment_automation_staging_only.sql"
    assert path.exists()
    assert not (ROOT/"migrations"/path.name).exists()
    assert not (ROOT/"ci_migrations"/path.name).exists()
    sql=path.read_text()
    assert "frcaixinha_staging" in sql
    assert "frcaixinha.mp_pix_automation_staging_authorized" in sql
    assert "current_setting('is_superuser')" in sql
    assert "NOT rolsuper AND NOT rolbypassrls" in sql
    assert sql.startswith("-- FR CAIXINHA AI STUDIO ONLY")
    assert "BEGIN;" in sql and "COMMIT;" in sql


def test_normalized_three_source_finance_tables_and_idempotent_payouts():
    text=(ROOT/"staging_migrations/035_pix_payment_automation_staging_only.sql").read_text()
    for table in (
        "mp_pix_member_destinations_staging",
        "mp_pix_collection_operations_staging",
        "mp_pix_settlement_evidence_staging",
        "mp_pix_receipts_staging",
        "mp_pix_payout_operations_staging",
    ):
        assert f"CREATE TABLE public.{table}" in text
        assert "FORCE ROW LEVEL SECURITY" in text
    assert "loan_id uuid NOT NULL UNIQUE" in text
    assert "idempotency_key varchar(64) NOT NULL UNIQUE" in text
    assert "statement_reference varchar(128) NOT NULL UNIQUE" in text
    assert "ledger_transaction_id uuid NOT NULL UNIQUE" in text
    assert "CHECK(provider_read_verified=true)" in text
    assert "CHECK(independent_settlement_verified=true)" in text
    assert "secret_ocid text NOT NULL" in text
    assert "pix_key text" not in text.lower()
    assert "FROM PUBLIC" in text
    assert "No INSERT/UPDATE/DELETE policies" in text


def test_termux_main_health_is_dormant():
    with TestClient(app) as c:
        r=c.get("/api/health/features/m3700")
    assert r.status_code==200
    d=r.json()
    assert d["contract"]=="AI_STUDIO_M3700_PIX_STAGING_PERSISTENCE_GUARD_V1"
    assert d["staging_migration_applied"] is False
    assert d["real_payment_execution_active"] is False
    assert d["financial_closing_authorized"] is False
