"""M26300 — real disposable PG integration with offline signed CI fixture."""
import json
import os
import time
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg
import pytest

from app.synthetic_mail_receipt import (
    ReceiptVerificationBlocked, receipt_signature, verify_synthetic_mail_receipt,
)

INVITATION_EVENT=UUID("eeeeeeee-0000-4000-8000-000000000015")
LEASE=UUID("eeeeeeee-0000-4000-8000-000000000032")
RECEIPT=UUID("eeeeeeee-0000-4000-8000-000000000043")
SECRET=b"ci-only-hmac-receipt-test-secret-never-deploy-to-production"


def ci_dsn():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("FRCAIXINHA_CI_ISOLATED") != "1":
        pytest.skip("M26300 disposable CI environment required")
    value=os.environ.get("CI_MAIL_RECEIPT_WORKER_URL","")
    parsed=urlsplit(value)
    if (parsed.scheme != "postgresql" or parsed.hostname != "127.0.0.1"
        or parsed.port != 5432 or parsed.path != "/frcaixinha_staging"
        or parsed.username != "frcaixinha_mail_receipt_ci"
    ):
        pytest.skip("M26300 isolated worker DSN not supplied")
    return value


@pytest.mark.asyncio
async def test_synthetic_hmac_proved_before_restricted_db_receipt_audit():
    dsn=ci_dsn()
    now=int(time.time())
    message={
        "event_id":str(RECEIPT),
        "invitation_event_id":str(INVITATION_EVENT),
        "kind":"CI_BOUNCE",
        "occurred_at":now,
    }
    raw=json.dumps(message,separators=(",",":")).encode("utf-8")
    signature=receipt_signature(SECRET,now,raw)
    verified=verify_synthetic_mail_receipt(
        body=raw, signature=signature, timestamp=str(now), secret=SECRET, now=now,
    )
    assert verified.signature_authenticated_in_ci
    assert not verified.provider_delivery_confirmed
    assert not verified.recipient_verified
    assert not verified.consent_recorded
    assert not verified.user_activated

    with pytest.raises(ReceiptVerificationBlocked):
        verify_synthetic_mail_receipt(
            body=raw+b" ",signature=signature,timestamp=str(now),secret=SECRET,now=now,
        )
    conn=await asyncpg.connect(dsn=dsn)
    try:
        await conn.execute("SELECT set_config('frcaixinha.mail_receipt_staging_ci','1',false)")
        call=("SELECT public.invite_record_mock_receipt_staging_ci("
              "$1::uuid,$2::uuid,$3::uuid,$4::varchar,$5::varchar)")
        args=(verified.invitation_event_id,LEASE,verified.event_id,verified.kind,verified.body_sha256)
        first=await conn.fetchval(call,*args)
        assert first.startswith("RECORDED:")
        second=await conn.fetchval(call,*args)
        assert second==first.replace("RECORDED:","REPLAY:")
        with pytest.raises(asyncpg.PostgresError):
            await conn.fetchval(call,verified.invitation_event_id,LEASE,
                                verified.event_id,"CI_SMTP_ACCEPTED",verified.body_sha256)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetchval("SELECT count(*) FROM public.invite_provider_receipts_staging")
    finally:
        await conn.close()
