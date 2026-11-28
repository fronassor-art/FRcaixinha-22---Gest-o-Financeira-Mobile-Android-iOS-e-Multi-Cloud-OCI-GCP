"""M27500-M27600: CI-only readback with restricted role and no delivery."""
import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.ci_committed_challenge_reader import (
    CiReadbackBlocked, _parse_readback,
)


ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/staging_migrations/057_email_challenge_readback_staging_only.sql"
CHAIN=ROOT/"backend/scripts/aistudio_staging_chain_ci.sh"


def test_sql_catalog_classifies_readback_as_staging_only():
    manifest=json.loads((ROOT/"backend/migration_catalog_ai_studio.json").read_text())
    entries={x["source_path"]:x for x in manifest["entries"]}
    assert len(entries)==len(manifest["entries"])>=92
    row=entries[str(SQL.relative_to(ROOT))]
    assert row["classification"]=="STAGING_ONLY_NEEDS_PORT"
    assert row["do_not_apply_source_to_termux"] is True
    assert len(row["source_blob_sha"])==40


def test_database_provenance_and_no_privileged_select_or_grants():
    source=SQL.read_text()
    assert source.count("COMMIT;")==1
    assert source.strip().endswith("COMMIT;")
    for required in (
        "session_user <> 'frcaixinha_email_attestor_ci'",
        "session_user <> 'postgres'",
        "frcaixinha.email_attestation_staging_ci",
        "current_database() <> 'frcaixinha_staging'",
        "SECURITY DEFINER",
        "SET search_path=pg_catalog,public,pg_temp",
        "REVOKE ALL ON FUNCTION public.invite_challenge_readback_staging_ci",
        "GRANT EXECUTE ON FUNCTION public.invite_challenge_readback_staging_ci",
        "e.status='SEALED_CI_NOT_SENT'",
        "l.lease_expires_at>clock_timestamp()",
        "i.revoked_at IS NULL AND i.accepted_at IS NULL",
        "d.document_kind='TENANT_MEMBERSHIP'",
        "c.failed_attempts=0",
        "c.consumed_at IS NULL",
        "c.expires_at>clock_timestamp()",
        "NOT EXISTS(",
        "invite_delivery_terminal_gate_staging",
        "AND o.provider_delivery_confirmed=false",
        "AND o.recipient_verified=false",
        "RETURN result;",
    ):
        assert required in source
    assert "CREATE POLICY" not in source
    assert "UPDATE public." not in source
    assert "INSERT INTO public." not in source
    assert "'raw_token'" not in source
    assert "'email_address'" not in source


def test_ci_staging_probe_rejects_wrong_database_and_authenticated_access():
    chain=CHAIN.read_text()
    for required in (
        "057_email_challenge_readback_staging_only.sql",
        "frcaixinha_email_attestor_ci",
        "M27500_WRONG_DATABASE_ROLLBACK=PASS",
        "test_m27600_committed_challenge_postgres_ci.py",
        "M27600_POSTCOMMIT_NO_DELIVERY=PASS",
        "M27600_POSTCONSUME_READBACK_DENIED=PASS",
        "LOCAL_MIGRATIONS=NOT_TOUCHED",
        "REAL_MONEY=OFF",
    ):
        assert required in chain
    for name in ("auth.py","invitations.py","master.py"):
        route=(ROOT/"backend/app/routers"/name).read_text()
        assert "invite_challenge_readback_staging_ci" not in route
        assert "read_committed_ci_challenge" not in route


def _payload(event):
    return {
        "tenant_id":str(uuid4()),"event_id":str(event),
        "document_id":str(uuid4()),"outbox_id":str(uuid4()),
        "challenge_digest":"a"*64,
        "issued_at":1794000000,"expires_at":1794000300,
        "failed_attempts":0,"consumed":False,
        "challenge_status":"CI_CHALLENGE_NOT_DELIVERED",
        "outbox_status":"HELD_CI_NOT_SENT",
        "terminal_quarantine":False,
    }


def test_strict_json_parser_only_accepts_exact_shape_and_scope():
    event=uuid4()
    valid=_payload(event)
    parsed=_parse_readback(json.dumps(valid),event)
    assert parsed.event_id==event
    assert parsed.source=="DISPOSABLE_POSTGRESQL_CI_READBACK"
    for change in (
        {"event_id":str(uuid4())},
        {"consumed":True},
        {"failed_attempts":1},
        {"challenge_status":"CI_TOKEN_CONSUMED_NOT_PROOF"},
        {"outbox_status":"SENT"},
        {"terminal_quarantine":True},
        {"issued_at":True},
        {"expires_at":"1794000300"},
        {"challenge_digest":"not-hash"},
        {"email_address":"secret@example.com"},
    ):
        different=dict(valid,**change)
        with pytest.raises(CiReadbackBlocked):
            _parse_readback(different,event)


def test_duplicate_json_keys_cannot_create_forged_trusted_readback():
    event=uuid4()
    valid=json.dumps(_payload(event))
    poisoned=valid.replace('"failed_attempts": 0','"failed_attempts": 0, "failed_attempts": 0')
    assert valid!=poisoned
    with pytest.raises(CiReadbackBlocked):
        _parse_readback(poisoned,event)


def test_ci_reader_never_exposes_secrets_or_can_send_true():
    source=(ROOT/"backend/app/ci_committed_challenge_reader.py").read_text()
    for forbidden in (
        "smtplib", "oci.config", "SMTP(", "INSERT INTO", "UPDATE public.",
        "can_send_network=True", "get_secret_bundle", "os.getenv('CI_SMTP_PASSWORD'",
    ):
        assert forbidden not in source
    assert 'os.getenv("GITHUB_ACTIONS") != "true"' in source
    assert 'identity["login_role"] != "frcaixinha_email_attestor_ci"' in source
