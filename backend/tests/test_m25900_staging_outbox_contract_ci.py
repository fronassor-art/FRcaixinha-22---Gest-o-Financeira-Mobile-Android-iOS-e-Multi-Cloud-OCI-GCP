"""M25900 — verify staging-only transactional invite delivery outbox boundaries.

These are static/source policy tests; the live SQL probe runs separately in
the disposable staging-chain CI, NEVER against Termux port 5433.
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "backend/staging_migrations/050_invitation_outbox_staging_only.sql"
FIXTURE = ROOT / "backend/ci_migrations/046_invitation_outbox_fixture_ci_only.sql"
PROBE = ROOT / "backend/ci_migrations/047_invitation_outbox_worker_probe_ci_only.sql"
CHAIN = ROOT / "backend/scripts/aistudio_staging_chain_ci.sh"


def test_migration_and_ci_probe_are_registered_not_termux_eligible():
    catalog=json.loads((ROOT / "backend/migration_catalog_ai_studio.json").read_text())
    entries={e["source_path"]:e for e in catalog["entries"]}
    assert len(entries) == len(catalog["entries"]) and len(entries) >= 82
    for path in (SQL,FIXTURE,PROBE):
        rel=str(path.relative_to(ROOT))
        assert rel in entries
        assert entries[rel]["do_not_apply_source_to_termux"] is True
        assert entries[rel]["source_blob_sha"]
    assert entries[str(SQL.relative_to(ROOT))]["classification"] == "STAGING_ONLY_NEEDS_PORT"
    assert entries[str(FIXTURE.relative_to(ROOT))]["classification"] == "CI_ONLY_TEST_OR_FIXTURE"


def test_migration_has_wrong_database_guard_and_restricted_role():
    source=SQL.read_text()
    assert "current_database()<>'frcaixinha_staging'" in source
    assert "current_setting('frcaixinha.invite_queue_staging_ci',true)" in source
    assert "session_user<>'postgres'" in source
    assert "session_user<>'frcaixinha_invite_queue_ci'" in source
    assert "current_setting('is_superuser')<>'on'" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "REVOKE ALL ON public.invite_delivery_outbox_staging,public.invite_delivery_audit_staging" in source
    assert "GRANT EXECUTE ON FUNCTION public.invite_enqueue_held_staging_ci" in source
    assert "TO frcaixinha_invite_queue_ci" in source
    assert "SET search_path=pg_catalog,public,pg_temp" in source


def test_outbox_guarantees_zero_real_delivery_and_no_raw_token():
    sql=SQL.read_text()
    assert "HELD_CI_NOT_SENT" in sql
    assert "CHECK(status='HELD_CI_NOT_SENT')" in sql
    assert "CHECK(provider_delivery_confirmed=false)" in sql
    assert "CHECK(recipient_verified=false)" in sql
    assert "sealed_payload_ref" in sql
    assert "ci://" in sql
    assert "token_hash" not in sql
    assert "password_hash" not in sql
    assert not re.search(r"CREATE\s+POLICY\s+",sql,re.I)
    assert "pg_advisory_xact_lock" in sql
    assert "UNIQUE REFERENCES public.invitations" in sql
    assert "OR event_id=p_event FOR UPDATE" in sql
    assert "existing.invitation_id<>p_invitation" in sql


def test_queue_checks_published_document_inviter_and_recipient_binding():
    sql=SQL.read_text()
    assert "i.required_document_id" in sql
    assert "d.published_at IS NOT NULL" in sql
    assert "i.delivery_status='PENDING_DELIVERY'" in sql
    assert "i.expires_at>now()" in sql
    assert "i.revoked_at IS NULL" in sql
    assert "u.is_master" in sql
    assert "m.role='TENANT_ADMIN' AND m.status='ATIVA'" in sql
    assert "lower(trim(inv.target_email))" in sql
    assert "CI_INVITE_HELD_NO_DELIVERY" in sql


def test_staging_chain_executes_new_sql_and_restricted_probe():
    source=CHAIN.read_text()
    assert "050_invitation_outbox_staging_only.sql" in source
    assert "046_invitation_outbox_fixture_ci_only.sql" in source
    assert "047_invitation_outbox_worker_probe_ci_only.sql" in source
    assert "frcaixinha_invite_queue_ci" in source
    assert "M25900_STAGING_OUTBOX_IDEMPOTENT_AUDIT=PASS" in source
    assert "LOCAL_MIGRATIONS=NOT_TOUCHED" in source
    assert "REAL_MONEY=OFF" in source
    assert "PGDATABASE:-" in source
    assert "5432" in source
    assert "FRCAIXINHA_CI_ISOLATED" in source


def test_no_public_runtime_imports_staging_sql_or_worker():
    paths=[
        ROOT / "backend/app/routers/invitations.py",
        ROOT / "backend/app/routers/auth.py",
        ROOT / "backend/app/onboarding_mail_transport.py",
    ]
    for path in paths:
        source=path.read_text()
        assert "invite_enqueue_held_staging_ci" not in source
        assert "invitation_outbox_staging" not in source
        assert "FRCAIXINHA_CI_ISOLATED" not in source
    assert "submit_access_message" not in (ROOT / "backend/app/routers/invitations.py").read_text()
