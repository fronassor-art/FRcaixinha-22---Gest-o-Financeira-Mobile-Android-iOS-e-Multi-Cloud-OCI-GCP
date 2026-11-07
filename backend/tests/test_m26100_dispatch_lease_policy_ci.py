"""M26100: schema / CI worker lease regression, never connect to Termux."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "backend/staging_migrations/052_invite_dispatch_lease_staging_only.sql"
FIRST = ROOT / "backend/ci_migrations/050_invite_dispatch_first_probe_ci_only.sql"
RETRY = ROOT / "backend/ci_migrations/051_invite_dispatch_retry_probe_ci_only.sql"
CHAIN = ROOT / "backend/scripts/aistudio_staging_chain_ci.sh"


def test_lease_files_registered_and_never_local_apply():
    catalog=json.loads((ROOT/"backend/migration_catalog_ai_studio.json").read_text())
    entries={item["source_path"]:item for item in catalog["entries"]}
    assert len(entries)==len(catalog["entries"])>=82
    for path in (MIG,FIRST,RETRY):
        entry=entries[str(path.relative_to(ROOT))]
        assert entry["do_not_apply_source_to_termux"] is True
        assert len(entry["source_blob_sha"])==40
    assert entries[str(MIG.relative_to(ROOT))]["classification"]=="STAGING_ONLY_NEEDS_PORT"
    assert entries[str(FIRST.relative_to(ROOT))]["classification"]=="CI_ONLY_TEST_OR_FIXTURE"


def test_claims_enforce_identity_and_bounded_atomic_retries():
    sql=MIG.read_text()
    for term in (
        "current_database()<>'frcaixinha_staging'",
        "session_user<>'postgres'",
        "session_user<>'frcaixinha_invite_dispatch_ci'",
        "frcaixinha.invite_dispatch_staging_ci",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
        "REVOKE ALL ON public.invite_dispatch_leases_staging",
        "REVOKE ALL ON FUNCTION public.invite_dispatch_lease_staging_ci",
        "GRANT EXECUTE ON FUNCTION public.invite_dispatch_lease_staging_ci",
        "FOR UPDATE OF o",
        "FOR UPDATE",
        "pg_advisory_xact_lock",
        "attempts BETWEEN 1 AND 3",
        "next_attempt:=existing.attempts+1",
        "RETURN 'EXHAUSTED'",
        "RETURN 'DENIED'",
        "RETURN 'REPLAY:'",
        "RETURN 'HELD:'",
    ):
        assert term in sql
    assert "CREATE POLICY" not in sql
    assert "SEND MAIL" not in sql
    assert "INSERT INTO public.invitations" not in sql


def test_lease_requires_real_invitation_document_and_scope_guards():
    sql=MIG.read_text()
    for term in (
        "i.accepted_at IS NULL AND i.revoked_at IS NULL",
        "i.expires_at>clock_timestamp()",
        "i.delivery_status='PENDING_DELIVERY'",
        "t.status='ATIVO'",
        "d.published_at IS NOT NULL",
        "i.target_role='TENANT_ADMIN' AND u.is_master",
        "m.role='TENANT_ADMIN' AND m.status='ATIVA'",
        "o.provider_delivery_confirmed=false",
        "o.recipient_verified=false",
        "CHECK (status='HELD_CI_NO_NETWORK')",
        "CHECK(action='CI_DISPATCH_HELD_WITHOUT_NETWORK')",
        "UNIQUE(outbox_id,attempt_number)",
    ):
        assert term in sql


def test_ci_chain_executes_real_disposable_transaction_and_non_delivery():
    chain=CHAIN.read_text()
    for term in (
        "052_invite_dispatch_lease_staging_only.sql",
        "050_invite_dispatch_first_probe_ci_only.sql",
        "051_invite_dispatch_retry_probe_ci_only.sql",
        "frcaixinha_invite_dispatch_ci",
        "M26100_WRONG_DATABASE_ROLLBACK=PASS",
        "M26100_CI_DISPATCH_LEASE_BOUNDED_RETRIES=PASS",
        "HELD:3",
        "EXHAUSTED",
        "REAL_MONEY=OFF",
        "LOCAL_MIGRATIONS=NOT_TOUCHED",
    ):
        assert term in chain
    first, retry=FIRST.read_text(),RETRY.read_text()
    assert "HELD:1" in first and "REPLAY:1" in first
    assert "HELD:2" in retry and "REPLAY:2" in retry
    assert "'DENIED'" in first and "'DENIED'" in retry


def test_never_expose_staging_claims_to_public_api_or_master():
    for p in (
        ROOT/"backend/app/routers/auth.py",
        ROOT/"backend/app/routers/invitations.py",
        ROOT/"backend/app/routers/master.py",
        ROOT/"backend/app/onboarding_mail_transport.py",
    ):
        source=p.read_text()
        assert "invite_dispatch_lease_staging_ci" not in source
        assert "frcaixinha_invite_dispatch_ci" not in source
    sql=MIG.read_text()
    assert "CREATE TRIGGER" not in sql
    assert "SMTP" not in sql
