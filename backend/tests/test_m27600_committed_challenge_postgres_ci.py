"""M27600: independently read committed synthetic SQL challenge, never send.

Runs only against the isolated frcaixinha_staging PostgreSQL:5432 under
GitHub Actions. Uses a fixed 384-bit-format CI token, never a real inbox.
"""
import os
import time
from dataclasses import replace
from hashlib import sha256
from uuid import UUID

import asyncpg
import pytest

from app.ci_committed_challenge_reader import (
    CiReadbackBlocked, read_committed_ci_challenge,
)
from app.committed_challenge_handoff import (
    ChallengeHandoffBlocked, check_committed_challenge,
)
from app.email_challenge_material import PreparedCiEmailChallenge


EVENT=UUID("eeeeeeee-0000-4000-8000-000000000015")
LEASE=UUID("eeeeeeee-0000-4000-8000-000000000033")
TOKEN="T"*64
DSN="postgresql://frcaixinha_email_attestor_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging"


def approved_ci():
    if (os.environ.get("GITHUB_ACTIONS")!="true"
            or os.environ.get("FRCAIXINHA_CI_ISOLATED")!="1"
            or os.environ.get("CI_EMAIL_ATTESTOR_URL")!=DSN):
        pytest.skip("M27600 isolated PostgreSQL CI-only attestor required")


@pytest.mark.asyncio
async def test_committed_db_challenge_readback_without_token_or_table_access():
    approved_ci()
    # The queue-role fixture has already committed its synthetic challenge in
    # a separate psql process; this is a fresh attestor connection.
    conn=await asyncpg.connect(DSN)
    try:
        await conn.execute(
            "SELECT set_config('frcaixinha.email_attestation_staging_ci','1',false)"
        )
        snapshot=await read_committed_ci_challenge(
            connection=conn,event_id=EVENT,lease_id=LEASE,
        )
        assert snapshot.event_id==EVENT
        assert snapshot.source=="DISPOSABLE_POSTGRESQL_CI_READBACK"
        assert snapshot.challenge_digest==sha256(TOKEN.encode()).hexdigest()
        assert not snapshot.consumed
        assert snapshot.failed_attempts==0
        assert "T"*64 not in repr(snapshot)
        assert snapshot.challenge_digest not in repr(snapshot)
        prepared=PreparedCiEmailChallenge(
            event_id=snapshot.event_id,tenant_id=snapshot.tenant_id,
            document_id=snapshot.document_id,
            challenge_digest=sha256(TOKEN.encode()).hexdigest(),
            ttl_seconds=305,expires_at=snapshot.expires_at,
            raw_token_for_trusted_worker=TOKEN,
        )
        decision=check_committed_challenge(
            prepared=prepared,readback=snapshot,now=int(time.time()),
        )
        assert decision.status=="CI_CHALLENGE_READBACK_MATCHED_NO_SEND"
        assert decision.can_send_network is False
        assert decision.recipient_verified is False
        assert decision.provider_delivery_confirmed is False
        assert decision.contract_accepted is False
        assert decision.account_activated is False
        with pytest.raises(ChallengeHandoffBlocked):
            check_committed_challenge(
                prepared=replace(prepared,raw_token_for_trusted_worker="Z"*64),
                readback=snapshot,now=int(time.time()),
            )
        with pytest.raises(CiReadbackBlocked):
            await read_committed_ci_challenge(
                connection=conn,event_id=EVENT,lease_id=UUID(int=1),
            )
        with pytest.raises(CiReadbackBlocked):
            await read_committed_ci_challenge(
                connection=conn,event_id=UUID(int=1),lease_id=LEASE,
            )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetchval(
                "SELECT count(*) FROM public.invite_email_challenges_staging"
            )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetchval(
                "SELECT count(*) FROM public.invite_encrypted_envelopes_staging"
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_attestor_cannot_read_without_scoped_session_setting():
    approved_ci()
    conn=await asyncpg.connect(DSN)
    try:
        with pytest.raises(CiReadbackBlocked):
            await read_committed_ci_challenge(
                connection=conn,event_id=EVENT,lease_id=LEASE,
            )
    finally:
        await conn.close()
