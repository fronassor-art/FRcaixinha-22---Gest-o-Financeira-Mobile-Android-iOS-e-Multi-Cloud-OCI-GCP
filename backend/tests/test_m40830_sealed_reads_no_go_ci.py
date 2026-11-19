"""M40830 offline adversarial envelope test; no live data, no SQL, no IO."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.m40830_financial_envelope_prototype import (
    SealedRecordDenied, seal_member_record, open_member_record,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend/app/m40830_financial_envelope_prototype.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m40830-sealed-reads-no-go-ci.yml"
DOC = ROOT / "docs/FR_FINANCE_M40830_SQL_GUC_SEALED_READ_PROTOTYPE_NO_GO.md"
NOW = datetime(2026, 11, 19, 20, 0, tzinfo=timezone.utc)


def fixture():
    tenant, member, record = uuid4(), uuid4(), uuid4()
    key = b"synthetic-test-key-not-real-00000"[:32]
    assert len(key) == 32
    sealed = seal_member_record(
        key=key, tenant_id=tenant, member_id=member,
        record_id=record, revision=1, amount_cents=123456,
    )
    session = SimpleNamespace(
        user_id=str(member), tenant_id=str(tenant),
        role="TENANT_MEMBER", is_master=False,
        verified_session_id=str(uuid4()),
        verified_session_at=NOW-timedelta(seconds=2),
        verified_session_expires_at=NOW+timedelta(minutes=10),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )
    return key, sealed, session


def test_same_member_with_off_db_key_can_read_synthetic_amount():
    key, record, session = fixture()
    assert open_member_record(key=key, record=record, session=session, now=NOW) == 123456
    assert "123456" not in repr(record)
    assert record.ciphertext != (123456).to_bytes(8, "big")
    assert "ciphertext" not in repr(record)


@pytest.mark.parametrize("field", ["tenant_id", "member_id", "record_id", "revision"])
def test_stored_metadata_tampering_fails_authentication(field):
    key, record, session = fixture()
    change = {field: 2 if field=="revision" else uuid4()}
    with pytest.raises(SealedRecordDenied):
        open_member_record(key=key, record=replace(record, **change),
                           session=session, now=NOW)


@pytest.mark.parametrize("field", ["nonce", "ciphertext"])
def test_tampering_with_ciphertext_fails_authentication(field):
    key, record, session = fixture()
    data = bytearray(getattr(record, field))
    data[-1] ^= 1
    with pytest.raises(SealedRecordDenied):
        open_member_record(key=key, record=replace(record, **{field: bytes(data)}),
                           session=session, now=NOW)


def test_wrong_key_and_missing_key_fail_closed():
    key, record, session = fixture()
    for bad in (b"z"*32, b"", b"x"*31, "not-bytes", None):
        with pytest.raises(SealedRecordDenied):
            open_member_record(key=bad, record=record, session=session, now=NOW)


@pytest.mark.parametrize("changed", [
    {"role": "MASTER", "tenant_id": None, "is_master": True},
    {"role": "TENANT_ADMIN"},
    {"user_id": "untrusted-uuid"},
    {"tenant_id": "untrusted-tenant"},
    {"verification_source": "LEGACY_NO_SESSION_BINDING"},
    {"verified_session_expires_at": NOW-timedelta(seconds=1)},
])
def test_bearer_session_wrong_role_tenant_or_provenance_denied(changed):
    key, record, session = fixture()
    for prop, value in changed.items():
        setattr(session, prop, value)
    with pytest.raises(SealedRecordDenied):
        open_member_record(key=key, record=record, session=session, now=NOW)


def test_untrusted_sql_guc_cannot_substitute_for_offdb_key():
    key, record, session = fixture()
    # The attacker can fake a GUC with a UUID and role. The envelope API
    # neither accepts those SQL settings nor reveals plaintext without key.
    sql_guessed_gucs = {
        "app.current_user_id": str(record.member_id),
        "app.current_role": "TENANT_MEMBER",
        "app.current_tenant_id": str(record.tenant_id),
    }
    assert all(sql_guessed_gucs.values())
    with pytest.raises(SealedRecordDenied):
        open_member_record(key=b"x"*32, record=record, session=session, now=NOW)


def test_swapped_ciphertext_between_members_fails():
    key, record, session = fixture()
    other = seal_member_record(
        key=key, tenant_id=record.tenant_id, member_id=uuid4(),
        record_id=record.record_id, revision=record.revision,
        amount_cents=999900,
    )
    swapped = replace(record, nonce=other.nonce, ciphertext=other.ciphertext)
    with pytest.raises(SealedRecordDenied):
        open_member_record(key=key, record=swapped, session=session, now=NOW)


def test_old_snapshot_replay_is_still_possible_no_go():
    key, old, session = fixture()
    newer = seal_member_record(
        key=key, tenant_id=old.tenant_id, member_id=old.member_id,
        record_id=old.record_id, revision=2, amount_cents=765432,
    )
    assert open_member_record(key=key, record=old, session=session, now=NOW) == 123456
    assert open_member_record(key=key, record=newer, session=session, now=NOW) == 765432


def test_stolen_decryption_key_is_full_read_capability_no_go():
    key, record, _ = fixture()
    aad = (b"FRF_M40830_MEMBER_ENTRY_ENVELOPE_V1|"
           + record.tenant_id.bytes + record.member_id.bytes
           + record.record_id.bytes + record.revision.to_bytes(4,"big"))
    assert int.from_bytes(
        AESGCM(key).decrypt(record.nonce,record.ciphertext,aad),"big"
    ) == 123456


@pytest.mark.parametrize("amount", [0, -1, 10**12+1, True, "100"])
def test_invalid_amount_denied_before_encrypt(amount):
    key, record, _ = fixture()
    with pytest.raises(SealedRecordDenied):
        seal_member_record(
            key=key, tenant_id=record.tenant_id, member_id=record.member_id,
            record_id=record.record_id, revision=1, amount_cents=amount,
        )


def test_workflow_doc_and_unwired_status():
    src=SOURCE.read_text(encoding="utf-8")
    yaml=WORKFLOW.read_text(encoding="utf-8")
    doc=DOC.read_text(encoding="utf-8")
    assert "AESGCM" in src and "M40830_RECORD_DENIED" in src
    assert "def open_member_record" in src
    assert "require_verified_rls_session" in src
    for text in ("PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
                 "ATIVACAO_REAL: 'OFF'", "test_m40830_sealed_reads_no_go_ci.py"):
        assert text in yaml
    for text in ("M40570", "M40730", "GUC", "NO-GO", "PRODUCTION=BLOCKED"):
        assert text in doc
    assert "m40830_financial_envelope_prototype" not in (
        ROOT/"backend/app/database.py").read_text()
