"""M24000 — OAuth PENDING/ACTIVE uncertain-ack safety, synthetic only.

A lost PostgreSQL reply must NEVER cause deletion of a possibly ACTIVE ref.
This test never touches OCI, Termux PG5433, real secrets or provider APIs.
"""
from uuid import UUID

import pytest
from app.mp_connect_http_runtime import OAuthTokens
from app.mp_oauth_connect_preflight import prepare_oauth_draft
from app.mp_oauth_staging_token_sink import (
    PendingTokenRevision, StagingOAuthTokenSink,
)

TENANT=UUID("00000000-0000-4000-8000-0000000000a1")
ACTOR=UUID("00000000-0000-4000-8000-0000000000a9")


def draft():
    return prepare_oauth_draft(
        tenant_id=TENANT, initiated_by=ACTOR, client_id="123456",
        registered_redirect_uri="https://example.invalid/callback",
        now_epoch=1800000000,
    )


def tokens():
    return OAuthTokens(
        seller_id="2002", scope="read offline_access", expires_in=3600,
        access_token="SYNTHETIC_M24000_ACCESS_TOKEN_000001",
        refresh_token="SYNTHETIC_M24000_REFRESH_TOKEN_00001",
        live_mode=False,
    )


class FakeRegistry:
    def __init__(self):
        self.pending=False
        self.active="old-active-revision"
        self.eligible_enabled=True
        self.stage_response="accepted"
        self.activate_response="accepted"
        self.fail_result=True
        self.fail_calls=0
        self.stage_calls=0

    async def eligible(self, *, tenant, actor, seller):
        return self.eligible_enabled and (tenant, actor, seller) == (
            TENANT, ACTOR, "2002")

    async def stage_pending(self, *, pending):
        self.stage_calls+=1
        if self.stage_response=="rejected":
            return False
        self.pending=True
        if self.stage_response=="ack_lost":
            raise TimeoutError("database response lost after PENDING commit")
        return True

    async def activate_cas(self, *, pending, access_hash, refresh_hash):
        assert len(access_hash)==len(refresh_hash)==64
        if self.activate_response=="rejected":
            return False
        assert self.pending
        self.pending=False
        self.active=pending.revision
        if self.activate_response=="ack_lost":
            raise TimeoutError("database response lost after ACTIVE commit")
        return True

    async def mark_failed(self, *, pending):
        self.fail_calls+=1
        if not self.fail_result or not self.pending:
            return False
        self.pending=False
        return True


class FakeStore:
    def __init__(self):
        self.staged=[]
        self.deleted=[]

    async def stage(self, *, tenant, actor, tokens):
        pending=PendingTokenRevision(
            tenant,actor,tokens.seller_id,
            "m24000-synthetic-revision-001",
            "vault://synthetic/opaque-ref-001",0,
        )
        self.staged.append(pending)
        return pending

    async def cancel(self, *, pending):
        self.deleted.append(pending.revision)
        return True


def setup():
    registry=FakeRegistry()
    store=FakeStore()
    sink=StagingOAuthTokenSink(registry=registry,store=store,enabled=True)
    return registry,store,sink


@pytest.mark.asyncio
async def test_success_only_new_revision_becomes_active():
    r,s,sink=setup()
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens())
    assert r.active=="m24000-synthetic-revision-001"
    assert not r.pending and not s.deleted


@pytest.mark.asyncio
async def test_lost_ack_after_activation_cannot_delete_active_credential():
    r,s,sink=setup()
    r.activate_response="ack_lost"
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert r.active=="m24000-synthetic-revision-001"
    assert not r.pending and r.fail_calls==1
    assert s.deleted==[]


@pytest.mark.asyncio
async def test_lost_ack_after_pending_insert_can_mark_failed_then_discard():
    r,s,sink=setup()
    r.stage_response="ack_lost"
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert r.active=="old-active-revision"
    assert r.pending is False and len(s.deleted)==1
    assert r.fail_calls==1


@pytest.mark.asyncio
async def test_unconfirmed_pending_failure_does_not_discard_blob():
    r,s,sink=setup()
    r.stage_response="ack_lost"
    r.fail_result=False
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert r.pending is True
    assert r.active=="old-active-revision" and s.deleted==[]


@pytest.mark.asyncio
async def test_explicit_stage_false_is_conservatively_reconciled():
    r,s,sink=setup()
    r.stage_response="rejected"
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert r.active=="old-active-revision"
    assert r.fail_calls==1 and s.deleted==[]


@pytest.mark.asyncio
async def test_negative_activation_with_confirmed_pending_failed_can_discard():
    r,s,sink=setup()
    r.activate_response="rejected"
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert r.active=="old-active-revision"
    assert r.pending is False and len(s.deleted)==1


@pytest.mark.asyncio
async def test_revocation_before_pending_attempt_cancels_unreferenced_blob():
    r,s,sink=setup()
    calls=0
    async def eligible(*, tenant,actor,seller):
        nonlocal calls
        calls+=1
        return calls==1
    r.eligible=eligible
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert r.stage_calls==0 and r.fail_calls==0
    assert len(s.deleted)==1 and r.active=="old-active-revision"


@pytest.mark.asyncio
async def test_disabled_does_not_even_stage():
    r,s,sink=setup()
    sink=StagingOAuthTokenSink(registry=r,store=s)
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert not s.staged and not s.deleted


def test_no_real_cloud_or_payment_configuration_in_sandbox():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    code=(root/"app/mp_oauth_staging_token_sink.py").read_text()
    assert "registration_attempted = True" in code
    assert "can_discard = not registration_attempted" in code
    assert "await self._registry.mark_failed(pending=pending)" in code
    assert "if can_discard:" in code
    assert "await self._store.cancel(pending=pending)" in code
    assert "httpx.post(" not in code and "oci." not in code
