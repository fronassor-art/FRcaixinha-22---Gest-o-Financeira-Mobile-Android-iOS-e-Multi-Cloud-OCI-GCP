"""M26700 — CI-only encrypted outbox database contract with least privilege."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/staging_migrations/055_invite_encrypted_envelope_staging_only.sql"
CHAIN=ROOT/"backend/scripts/aistudio_staging_chain_ci.sh"


def test_registered_staging_only_and_migration_hash_checked():
    entries=json.loads((ROOT/"backend/migration_catalog_ai_studio.json").read_text())["entries"]
    paths={e["source_path"]:e for e in entries}
    assert len(paths)==len(entries)>=87
    row=paths[str(SQL.relative_to(ROOT))]
    assert row["classification"]=="STAGING_ONLY_NEEDS_PORT"
    assert row["do_not_apply_source_to_termux"] is True
    assert row["requires_local_equivalent_before_use"] is True
    assert len(row["source_blob_sha"])==40


def test_restricted_write_scope_and_immutable_ciphertext():
    sql=SQL.read_text()
    for term in (
        "current_database()<>'frcaixinha_staging'",
        "session_user<>'postgres'",
        "session_user<>'frcaixinha_envelope_producer_ci'",
        "session_user<>'frcaixinha_invite_dispatch_ci'",
        "frcaixinha.envelope_staging_ci",
        "SET search_path=pg_catalog,public,pg_temp",
        "FORCE ROW LEVEL SECURITY",
        "ENABLE ROW LEVEL SECURITY",
        "REVOKE ALL ON public.invite_encrypted_envelopes_staging",
        "GRANT EXECUTE ON FUNCTION public.invite_store_encrypted_envelope_staging_ci",
        "GRANT EXECUTE ON FUNCTION public.invite_read_encrypted_envelope_staging_ci",
        "UNIQUE", "p_nonce",
        "pg_advisory_xact_lock",
        "FOR UPDATE OF o",
        "p_expires-p_issued>86400",
        "d.document_kind='TENANT_MEMBERSHIP'",
        "d.published_at IS NOT NULL",
        "i.revoked_at IS NULL AND i.accepted_at IS NULL",
        "i.delivery_status='PENDING_DELIVERY'",
        "RETURN 'QUARANTINED'",
        "RETURN 'REPLAY:'",
        "RETURN 'SEALED:'",
        "ciphertext_digest",
        "status='SEALED_CI_NOT_SENT'",
        "l.lease_expires_at>clock_timestamp()",
        "NOT EXISTS(",
        "invite_delivery_terminal_gate_staging",
    ):
        assert term in sql
    assert "CREATE POLICY" not in sql
    assert "UPDATE public.invitations" not in sql
    assert "UPDATE public.users" not in sql
    assert "SMTP(" not in sql


def test_neither_direct_access_nor_plaintext_fields_are_created():
    sql=SQL.read_text()
    table=sql.split("CREATE TABLE public.invite_encrypted_envelopes_staging (",1)[1].split(");",1)[0]
    for forbidden in ("recipient_email", "target_email", "password_hash", "token_hash",
                      "token_plain", "secret_plain", "plaintext"):
        assert forbidden not in table
    assert "ciphertext_b64" in table
    assert "nonce_b64" in table
    assert "key_id" in table
    assert "CHECK(purpose='INVITATION')" in table
    assert "CHECK(status='SEALED_CI_NOT_SENT')" in table
    for role in ("frcaixinha_envelope_producer_ci","frcaixinha_invite_dispatch_ci"):
        assert role in sql


def test_staging_chain_proves_wrong_database_replay_and_quarantine_boundary():
    chain=CHAIN.read_text()
    for term in (
        "055_invite_encrypted_envelope_staging_only.sql",
        "test_m26700_sealed_outbox_postgres_ci.py",
        "M26700_WRONG_DATABASE_ROLLBACK=PASS",
        "M26700_POSTGRES_AES_GCM_PERSISTENCE=PASS",
        "M26700_QUARANTINED_ENVELOPE_NOT_RETRIEVABLE=PASS",
        "FRCAIXINHA_CI_ISOLATED=1",
        "LOCAL_MIGRATIONS=NOT_TOUCHED",
        "REAL_MONEY=OFF",
    ):
        assert term in chain


def test_public_routers_do_not_access_envelopes_or_keys():
    for name in ("invitations.py","auth.py","master.py"):
        source=(ROOT/"backend/app/routers"/name).read_text()
        for identifier in (
            "invite_store_encrypted_envelope_staging_ci",
            "invite_read_encrypted_envelope_staging_ci",
            "SyntheticKeyProvider",
            "SealedDelivery",
        ):
            assert identifier not in source
