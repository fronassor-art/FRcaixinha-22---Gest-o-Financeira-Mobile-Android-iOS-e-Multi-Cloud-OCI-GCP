"""M26600 — persistent staging-only uncertainty suppresses any resend."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/staging_migrations/054_invite_delivery_terminal_gate_staging_only.sql"
PROBE=ROOT/"backend/ci_migrations/053_delivery_terminal_gate_probe_ci_only.sql"
CHAIN=ROOT/"backend/scripts/aistudio_staging_chain_ci.sh"


def test_terminal_gate_registered_with_exact_sql_hash_and_no_termux_apply():
    data=json.loads((ROOT/"backend/migration_catalog_ai_studio.json").read_text())
    entries={e["source_path"]:e for e in data["entries"]}
    assert len(entries)==len(data["entries"])>=86
    for p in (SQL,PROBE):
        row=entries[str(p.relative_to(ROOT))]
        assert row["do_not_apply_source_to_termux"] is True
        assert len(row["source_blob_sha"])==40
    assert entries[str(SQL.relative_to(ROOT))]["classification"]=="STAGING_ONLY_NEEDS_PORT"
    assert entries[str(PROBE.relative_to(ROOT))]["classification"]=="CI_ONLY_TEST_OR_FIXTURE"


def test_gate_enforces_role_db_rls_and_revokes_legacy_bypass():
    code=SQL.read_text()
    for item in (
        "current_database()<>'frcaixinha_staging'",
        "session_user<>'postgres'",
        "session_user<>'frcaixinha_invite_dispatch_ci'",
        "frcaixinha.delivery_gate_staging_ci",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
        "REVOKE ALL ON public.invite_delivery_terminal_gate_staging",
        "REVOKE EXECUTE ON FUNCTION public.invite_dispatch_lease_staging_ci",
        "GRANT EXECUTE ON FUNCTION public.invite_dispatch_guarded_staging_ci",
        "GRANT EXECUTE ON FUNCTION public.invite_dispatch_mark_terminal_staging_ci",
        "SET search_path=pg_catalog,public,pg_temp",
        "pg_advisory_xact_lock(hashtextextended('M26100|'||p_event::text,0))",
        "RETURN public.invite_dispatch_lease_staging_ci(p_event,p_lease)",
    ):
        assert item in code
    assert "CREATE POLICY" not in code


def test_gate_never_fabricates_delivery_or_recipient_consent():
    code=SQL.read_text()
    for term in (
        "CI_UNKNOWN_TIMEOUT_QUARANTINE",
        "CI_SMTP_ACCEPTED_UNVERIFIED",
        "CI_BOUNCED_REQUIRES_REVIEW",
        "CHECK(provider_delivery_confirmed=false)",
        "CHECK(recipient_verified=false)",
        "CHECK(consent_recorded=false)",
        "CHECK(user_activated=false)",
        "r.kind=p_result",
        "RETURN 'QUARANTINED'",
        "RETURN 'REPLAY'",
        "RETURN 'DENIED'",
    ):
        assert term in code
    for forbidden in (
        "UPDATE public.invitations",
        "UPDATE public.users",
        "INSERT INTO public.sessions",
        "SEND MAIL",
    ):
        assert forbidden not in code


def test_real_disposable_pg_probes_unknown_ack_and_signed_receipt_dry_run():
    chain=CHAIN.read_text()
    probe=PROBE.read_text()
    for term in (
        "054_invite_delivery_terminal_gate_staging_only.sql",
        "053_delivery_terminal_gate_probe_ci_only.sql",
        "M26600_WRONG_DATABASE_ROLLBACK=PASS",
        "M26600_CI_TERMINAL_DELIVERY_QUARANTINE=PASS",
        "state='CI_UNKNOWN_TIMEOUT_QUARANTINE'",
        "FRCAIXINHA_CI_ISOLATED",
        "LOCAL_MIGRATIONS=NOT_TOUCHED",
        "REAL_MONEY=OFF",
    ):
        assert term in chain
    for term in (
        "BEGIN;",
        "ROLLBACK;",
        "'CI_SMTP_ACCEPTED'",
        "'UNKNOWN_TIMEOUT'",
        "'QUARANTINED'",
        "'REPLAY'",
        "legacy claim bypass still granted",
        "conflicting terminal update allowed",
    ):
        assert term in probe


def test_no_public_routes_enable_terminal_claim_or_dispatch():
    for path in ("auth.py","invitations.py","master.py"):
        content=(ROOT/"backend/app/routers"/path).read_text()
        assert "invite_dispatch_guarded_staging_ci" not in content
        assert "invite_dispatch_mark_terminal_staging_ci" not in content
        assert "SealedDelivery" not in content
