"""M26000 — static guardrails for isolated recovery rotation and audit SQL.

Live SQL tests execute in disposable staging through the staging CI chain.
No local Termux DB or real user is touched here.
"""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/staging_migrations/051_password_reset_staging_only.sql"
FIX=ROOT/"backend/ci_migrations/048_password_reset_fixture_ci_only.sql"
PROBE=ROOT/"backend/ci_migrations/049_password_reset_worker_probe_ci_only.sql"
CHAIN=ROOT/"backend/scripts/aistudio_staging_chain_ci.sh"


def test_recovery_migration_registration_and_isolation():
    cat=json.loads((ROOT/"backend/migration_catalog_ai_studio.json").read_text())
    assert len(cat["entries"])>=82
    by_path={e["source_path"]:e for e in cat["entries"]}
    assert len(by_path)==len(cat["entries"])
    for item in (SQL,FIX,PROBE):
        e=by_path[str(item.relative_to(ROOT))]
        assert e["do_not_apply_source_to_termux"] is True
        assert e["source_blob_sha"]
    assert by_path[str(SQL.relative_to(ROOT))]["classification"]=="STAGING_ONLY_NEEDS_PORT"
    assert by_path[str(FIX.relative_to(ROOT))]["classification"]=="CI_ONLY_TEST_OR_FIXTURE"


def test_reset_requires_disposable_database_and_separate_role():
    content=SQL.read_text()
    assert "current_database()<>'frcaixinha_staging'" in content
    assert "session_user<>'frcaixinha_account_recovery_ci'" in content
    assert "session_user<>'postgres'" in content
    assert "current_setting('frcaixinha.recovery_staging_ci',true)" in content
    assert "current_setting('is_superuser')<>'on'" in content
    assert "ENABLE ROW LEVEL SECURITY" in content
    assert "FORCE ROW LEVEL SECURITY" in content
    assert "REVOKE ALL ON public.password_recovery_audit_staging" in content
    assert "REVOKE ALL ON FUNCTION" in content
    assert "GRANT EXECUTE ON FUNCTION" in content
    assert "TO frcaixinha_account_recovery_ci" in content
    assert "SET search_path=pg_catalog,public,pg_temp" in content


def test_reset_is_single_use_and_revokes_all_sessions_and_pending_tokens():
    text=SQL.read_text()
    for term in (
        "FOR UPDATE OF r",
        "r.expires_at>now()",
        "r.consumed_at IS NULL AND r.revoked_at IS NULL",
        "r.delivery_status='DELIVERED'",
        "u.status='ACTIVE'",
        "UPDATE public.credentials c",
        "password_changed_at=now()",
        "UPDATE public.password_reset_tokens SET consumed_at=now()",
        "UPDATE public.password_reset_tokens SET revoked_at=now()",
        "UPDATE public.sessions SET revoked_at=now()",
        "CI_PASSWORD_ROTATED_SESSIONS_REVOKED",
        "RETURN 'ROTATED'",
        "RETURN 'DENIED'",
    ):
        assert term in text
    assert "CREATE POLICY" not in text
    assert "SMTP_HOST" not in text
    assert "INSERT INTO public.users" not in text
    assert "INSERT INTO public.memberships" not in text


def test_disposable_probe_checks_replay_expiration_and_delivery_status():
    fixture=FIX.read_text()
    probe=PROBE.read_text()
    chain=CHAIN.read_text()
    assert "PENDING_DELIVERY" in fixture
    assert "DELIVERED" in fixture
    assert "now()-interval '5 minutes'" in fixture
    assert "repeat('c',64)" in probe
    assert "repeat('e',64)" in probe
    assert "repeat('f',64)" in probe
    assert "'ROTATED'" in probe
    assert "'DENIED'" in probe
    assert "051_password_reset_staging_only.sql" in chain
    assert "048_password_reset_fixture_ci_only.sql" in chain
    assert "049_password_reset_worker_probe_ci_only.sql" in chain
    assert "M26000_WRONG_DATABASE_ROLLBACK=PASS" in chain
    assert "M26000_STAGING_PASSWORD_ROTATION_SESSIONS_REVOKED=PASS" in chain
    assert "frcaixinha_account_recovery_ci" in chain


def test_no_public_password_reset_implementation_claimed():
    auth=(ROOT/"backend/app/routers/auth.py").read_text()
    email=(ROOT/"backend/app/onboarding_mail_transport.py").read_text()
    assert "Recuperação de senha por e-mail ainda não implementada" in auth
    assert "password_reset_rotate_staging_ci" not in auth
    assert "password_reset_rotate_staging_ci" not in email
    assert "submit_access_message" not in auth
    assert "submit_access_message" not in (ROOT/"backend/app/routers/invitations.py").read_text()
