"""M27100: synthetic proof cannot grant email ownership, identity or account."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
STAGING=ROOT/"backend/staging_migrations/056_email_ownership_challenge_staging_only.sql"
ISSUE=ROOT/"backend/ci_migrations/054_email_challenge_issue_probe_ci_only.sql"
CONSUME=ROOT/"backend/ci_migrations/055_email_challenge_consume_probe_ci_only.sql"
LOCKOUT=ROOT/"backend/ci_migrations/056_email_challenge_lockout_probe_ci_only.sql"
CHAIN=ROOT/"backend/scripts/aistudio_staging_chain_ci.sh"


def test_every_challenge_sql_is_hash_registered_and_banned_from_termux():
    entries=json.loads((ROOT/"backend/migration_catalog_ai_studio.json").read_text())["entries"]
    bypath={x["source_path"]:x for x in entries}
    assert len(entries)==len(bypath)>=91
    for f in (STAGING,ISSUE,CONSUME,LOCKOUT):
        row=bypath[str(f.relative_to(ROOT))]
        assert row["do_not_apply_source_to_termux"] is True
        assert len(row["source_blob_sha"])==40
    assert bypath[str(STAGING.relative_to(ROOT))]["classification"]=="STAGING_ONLY_NEEDS_PORT"
    assert bypath[str(ISSUE.relative_to(ROOT))]["classification"]=="CI_ONLY_TEST_OR_FIXTURE"
    assert bypath[str(CONSUME.relative_to(ROOT))]["classification"]=="CI_ONLY_TEST_OR_FIXTURE"
    assert bypath[str(LOCKOUT.relative_to(ROOT))]["classification"]=="CI_ONLY_TEST_OR_FIXTURE"


def test_challenge_requires_disposable_db_and_restricted_workers():
    sql=STAGING.read_text()
    assert sql.strip().endswith("COMMIT;")
    assert sql.count("COMMIT;")==1
    assert sql.count("CREATE FUNCTION public.invite_")==2
    assert "p_raw_token !~ '^[A-Za-z0-9_-]+$'" in sql
    for token in (
        "current_database()<>'frcaixinha_staging'",
        "session_user<>'postgres'",
        "session_user<>'frcaixinha_invite_queue_ci'",
        "session_user<>'frcaixinha_email_proof_ci'",
        "frcaixinha.email_proof_staging_ci",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
        "REVOKE ALL ON public.invite_email_challenges_staging",
        "GRANT EXECUTE ON FUNCTION public.invite_issue_ci_email_challenge",
        "GRANT EXECUTE ON FUNCTION public.invite_consume_ci_email_challenge",
        "SET search_path=pg_catalog,public,pg_temp",
        "pg_advisory_xact_lock",
        "p_expiry_seconds NOT BETWEEN 60 AND 900",
        "length(p_raw_token) NOT BETWEEN 32 AND 256",
        "p_raw_token !~ '^[A-Za-z0-9_-]+$'",
        "failed_attempts=failed_attempts+1",
        "consumed_at=clock_timestamp()",
        "i.revoked_at IS NULL AND i.accepted_at IS NULL",
        "i.delivery_status='PENDING_DELIVERY'",
        "t.status='ATIVO'",
        "d.document_kind='TENANT_MEMBERSHIP'",
        "d.published_at IS NOT NULL",
    ):
        assert token in sql
    assert "CREATE POLICY" not in sql


def test_challenge_cannot_claim_sent_delivered_verified_accepted_or_activated():
    sql=STAGING.read_text()
    for token in (
        "CI_CHALLENGE_NOT_DELIVERED",
        "CI_TOKEN_CONSUMED_NOT_PROOF",
        "CHECK(recipient_verified=false)",
        "CHECK(user_activated=false)",
        "CHECK(contract_accepted=false)",
        "RETURN 'DENIED'",
    ):
        assert token in sql
    for forbidden in (
        "UPDATE public.users",
        "UPDATE public.memberships",
        "UPDATE public.invitations",
        "UPDATE public.invite_delivery_outbox_staging",
        "INSERT INTO public.sessions",
        "SMTP(",
    ):
        assert forbidden not in sql


def test_disposable_ci_proves_issue_wrong_digest_one_use_and_denied_read():
    chain=CHAIN.read_text()
    for term in (
        "056_email_ownership_challenge_staging_only.sql",
        "054_email_challenge_issue_probe_ci_only.sql",
        "055_email_challenge_consume_probe_ci_only.sql",
        "M27100_WRONG_DATABASE_ROLLBACK=PASS",
        "M27100_CI_EMAIL_TOKEN_CONSUMED_NO_IDENTITY_GRANT=PASS",
        "056_email_challenge_lockout_probe_ci_only.sql",
        "M27101_CI_LOCKOUT_EXPIRY_NO_ACTIVATION=PASS",
        "frcaixinha_email_proof_ci",
        "FRCAIXINHA_CI_ISOLATED",
        "LOCAL_MIGRATIONS=NOT_TOUCHED",
        "REAL_MONEY=OFF",
    ):
        assert term in chain
    issue=ISSUE.read_text()
    consume=CONSUME.read_text()
    assert "ISSUED_CI_NOT_DELIVERED" in issue
    assert "REPLAY_CI_NOT_DELIVERED" in issue
    assert "repeat('U',48)" in consume
    assert "CI_TOKEN_CONSUMED_NOT_PROOF" in consume
    assert "consumed token replay accepted" in consume
    lockout=LOCKOUT.read_text()
    assert "FOR attempt IN 1..3 LOOP" in lockout
    assert "valid token bypassed exhausted attempts" in lockout


def test_proof_functions_are_never_published_in_http_routes():
    for name in ("auth.py","invitations.py","master.py"):
        source=(ROOT/"backend/app/routers"/name).read_text()
        assert "invite_issue_ci_email_challenge" not in source
        assert "invite_consume_ci_email_challenge" not in source
