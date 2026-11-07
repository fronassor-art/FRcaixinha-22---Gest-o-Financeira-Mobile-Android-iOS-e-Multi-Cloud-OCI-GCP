"""M26300 — signed mock receipt audit has no route, delivery or consent powers."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/staging_migrations/053_mail_receipt_audit_staging_only.sql"
PROBE=ROOT/"backend/ci_migrations/052_mail_receipt_idempotency_probe_ci_only.sql"
CHAIN=ROOT/"backend/scripts/aistudio_staging_chain_ci.sh"


def test_new_receipt_sql_is_versioned_and_not_termux_applicable():
    manifest=json.loads((ROOT/"backend/migration_catalog_ai_studio.json").read_text())
    entries={e["source_path"]:e for e in manifest["entries"]}
    assert len(entries)==len(manifest["entries"])>=84
    for path in (SQL,PROBE):
        e=entries[str(path.relative_to(ROOT))]
        assert e["do_not_apply_source_to_termux"] is True
        assert len(e["source_blob_sha"])==40
    assert entries[str(SQL.relative_to(ROOT))]["classification"]=="STAGING_ONLY_NEEDS_PORT"
    assert entries[str(PROBE.relative_to(ROOT))]["classification"]=="CI_ONLY_TEST_OR_FIXTURE"


def test_receipt_worker_has_privilege_and_database_barriers():
    code=SQL.read_text()
    for expected in (
        "current_database()<>'frcaixinha_staging'",
        "session_user<>'postgres'",
        "session_user<>'frcaixinha_mail_receipt_ci'",
        "frcaixinha.mail_receipt_staging_ci",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
        "REVOKE ALL ON public.invite_provider_receipts_staging",
        "REVOKE ALL ON FUNCTION public.invite_record_mock_receipt_staging_ci",
        "GRANT EXECUTE ON FUNCTION public.invite_record_mock_receipt_staging_ci",
        "SET search_path=pg_catalog,public,pg_temp",
        "pg_advisory_xact_lock",
        "UNIQUE(lease_id,kind)",
        "WHERE receipt_event_id=p_receipt_event FOR UPDATE",
    ):
        assert expected in code
    assert "CREATE POLICY" not in code
    assert "UPDATE public.invitations" not in code
    assert "UPDATE public.invite_delivery_outbox_staging" not in code


def test_schema_only_knows_ci_accepted_or_bounce_and_never_delivery():
    sql=SQL.read_text()
    for expected in (
        "CI_SMTP_ACCEPTED", "CI_BOUNCE",
        "CI_RECEIPT_ONLY_NO_DELIVERY",
        "CHECK(provider_delivery_confirmed=false)",
        "CHECK(recipient_verified=false)",
        "CHECK(acceptance_recorded=false)",
        "CHECK(account_activated=false)",
        "RETURN 'REPLAY:'",
        "RETURN 'RECORDED:'",
        "RETURN 'DENIED'",
    ):
        assert expected in sql
    assert "CI_DELIVERED" not in sql
    assert "SEND EMAIL" not in sql
    assert "INSERT INTO public.users" not in sql


def test_disposable_pg_worker_executes_hmac_then_db_and_not_public_webhook():
    script=CHAIN.read_text()
    for expected in (
        "053_mail_receipt_audit_staging_only.sql",
        "052_mail_receipt_idempotency_probe_ci_only.sql",
        "test_m26300_signed_receipt_pg_ci.py",
        "M26300_WRONG_DATABASE_ROLLBACK=PASS",
        "M26300_CI_SIGNED_RECEIPT_POSTGRES_NO_DELIVERY=PASS",
        "frcaixinha_mail_receipt_ci",
        "CI_MAIL_RECEIPT_WORKER_URL",
        "LOCAL_MIGRATIONS=NOT_TOUCHED",
        "REAL_MONEY=OFF",
    ):
        assert expected in script
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    source=(root/"backend/app/synthetic_mail_receipt.py").read_text()
    assert "hmac.compare_digest" in source
    assert "object_pairs_hook=_unique_pairs" in source
    for route in ("invitations.py","auth.py","master.py"):
        target=(root/"backend/app/routers"/route).read_text()
        assert "verify_synthetic_mail_receipt" not in target
        assert "invite_record_mock_receipt_staging_ci" not in target
