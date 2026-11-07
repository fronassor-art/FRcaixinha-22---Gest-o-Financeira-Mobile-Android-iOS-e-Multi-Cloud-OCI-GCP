"""M26700 — encrypt once, persist and read only with an active CI lease.

The PostgreSQL test is restricted to the disposable GitHub Actions database.
Only synthetic addresses, tokens and a non-production in-process key are used.
"""
import os
import time
from uuid import UUID

import asyncpg
import pytest

from app.delivery_envelope import (
    DeliveryScope, DeliverySecret, SealedDelivery, EnvelopeBlocked,
    seal_delivery, open_delivery,
)

EVENT = UUID("eeeeeeee-0000-4000-8000-000000000015")
TENANT = UUID("eeeeeeee-0000-4000-8000-000000000012")
DOCUMENT = UUID("eeeeeeee-0000-4000-8000-000000000013")
LEASE = UUID("eeeeeeee-0000-4000-8000-000000000033")
KEY_ID = "ci-vault-test-key-2026"
TOKEN = "Z" * 48


class SyntheticKeyProvider:
    def load_key(self, key_id):
        if key_id != KEY_ID:
            raise LookupError("synthetic key not available")
        return b"K" * 32


def isolated_dsn(name, user):
    if os.getenv("GITHUB_ACTIONS") != "true" or os.getenv("FRCAIXINHA_CI_ISOLATED") != "1":
        pytest.skip("CI-only disposable PostgreSQL required")
    value = os.getenv(name)
    expected = f"postgresql://{user}:ci-test-only@127.0.0.1:5432/frcaixinha_staging"
    if value != expected:
        pytest.skip("synthetic worker connection unavailable")
    return value


@pytest.mark.asyncio
async def test_encrypted_outbox_is_idempotent_restricted_and_bound_to_lease():
    producer_dsn = isolated_dsn("CI_SEALED_ENVELOPE_PRODUCER_URL","frcaixinha_envelope_producer_ci")
    dispatcher_dsn = isolated_dsn("CI_SEALED_ENVELOPE_DISPATCH_URL","frcaixinha_invite_dispatch_ci")
    now = int(time.time())
    scope = DeliveryScope(
        tenant_id=TENANT,event_id=EVENT,document_id=DOCUMENT,
        target_role="TENANT_ADMIN",purpose="INVITATION",
        issued_at=now,expires_at=now+600,
    )
    synthetic = DeliverySecret(recipient="future-admin-m25900@example.com",token=TOKEN)
    encrypted = seal_delivery(scope=scope,secret=synthetic,
                              provider=SyntheticKeyProvider(),key_id=KEY_ID,now=now)
    assert TOKEN not in encrypted.ciphertext_b64
    assert synthetic.recipient not in encrypted.ciphertext_b64
    writer = await asyncpg.connect(producer_dsn)
    reader = await asyncpg.connect(dispatcher_dsn)
    try:
        await writer.execute("SELECT set_config('frcaixinha.envelope_staging_ci','1',false)")
        await reader.execute("SELECT set_config('frcaixinha.envelope_staging_ci','1',false)")
        insert = ("SELECT public.invite_store_encrypted_envelope_staging_ci("
                  "$1::uuid,$2::uuid,$3::uuid,$4::varchar,$5::varchar,"
                  "$6::varchar,$7::varchar,$8::bigint,$9::bigint)")
        params=(EVENT,TENANT,DOCUMENT,scope.target_role,encrypted.key_id,
                encrypted.nonce_b64,encrypted.ciphertext_b64,scope.issued_at,
                scope.expires_at)
        first=await writer.fetchval(insert,*params)
        assert first.startswith("SEALED:")
        assert await writer.fetchval(insert,*params) == first.replace("SEALED:","REPLAY:")
        assert await writer.fetchval(insert,EVENT,UUID(int=1),*params[2:]) == "DENIED"
        with pytest.raises(asyncpg.PostgresError):
            await writer.fetchval(
                insert,EVENT,TENANT,DOCUMENT,scope.target_role,encrypted.key_id,
                encrypted.nonce_b64,encrypted.ciphertext_b64+"A",
                scope.issued_at,scope.expires_at,
            )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await writer.fetchval("SELECT count(*) FROM public.invite_encrypted_envelopes_staging")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await reader.fetchval("SELECT count(*) FROM public.invite_encrypted_envelopes_staging")
        assert await reader.fetchval(
            "SELECT public.invite_read_encrypted_envelope_staging_ci($1::uuid,$2::uuid)",
            EVENT,UUID(int=1),
        ) is None
        result=await reader.fetchval(
            "SELECT public.invite_read_encrypted_envelope_staging_ci($1::uuid,$2::uuid)",
            EVENT,LEASE,
        )
        assert result is not None
        assert result["purpose"] == "INVITATION"
        assert result["tenant_id"] == str(TENANT)
        assert result["event_id"] == str(EVENT)
        assert result["document_id"] == str(DOCUMENT)
        assert "token" not in result
        assert "recipient" not in result
        retrieved = SealedDelivery(
            version=1,key_id=result["key_id"],
            nonce_b64=result["nonce_b64"],ciphertext_b64=result["ciphertext_b64"],
        )
        recovered_scope=DeliveryScope(
            tenant_id=UUID(result["tenant_id"]),event_id=UUID(result["event_id"]),
            document_id=UUID(result["document_id"]),
            target_role=result["target_role"],purpose=result["purpose"],
            issued_at=result["issued_at"],expires_at=result["expires_at"],
        )
        assert open_delivery(envelope=retrieved,scope=recovered_scope,
                             provider=SyntheticKeyProvider(),now=now+2)==synthetic
        with pytest.raises(EnvelopeBlocked):
            open_delivery(envelope=retrieved,
                          scope=DeliveryScope(**{**vars(recovered_scope),
                                                "tenant_id":UUID(int=2)}),
                          provider=SyntheticKeyProvider(),now=now+2)
    finally:
        await writer.close()
        await reader.close()
