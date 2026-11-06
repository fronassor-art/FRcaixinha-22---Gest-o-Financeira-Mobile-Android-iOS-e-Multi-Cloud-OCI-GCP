"""M23500: synthetic token storage boundary; NO OCI, PostgreSQL, or money."""
from dataclasses import replace
from uuid import UUID
import pytest
from app.mp_oauth_connect_preflight import prepare_oauth_draft
from app.mp_connect_http_runtime import OAuthTokens
from app.mp_oauth_staging_token_sink import PendingTokenRevision,StagingOAuthTokenSink

T=UUID("00000000-0000-4000-8000-0000000000a1")
U=UUID("00000000-0000-4000-8000-0000000000a9")
OTHER=UUID("00000000-0000-4000-8000-0000000000b9")

def draft():
    return prepare_oauth_draft(tenant_id=T,initiated_by=U,client_id="123456",
        registered_redirect_uri="https://app.example.invalid/connect/callback",
        now_epoch=1800000000)

def tokens():
    return OAuthTokens(seller_id="2002",scope="read offline_access",expires_in=3600,
        access_token="TEST_ACCESS_TOKEN_M23500_SECRET",
        refresh_token="TEST_REFRESH_TOKEN_M23500_SECRET",live_mode=False)

class Registry:
    def __init__(self):
        self.allowed=True
        self.revoke_after_first=False
        self.calls=0
        self.active="existing-active-revision"
        self.activate_allowed=True
        self.stage_allowed=True
        self.staged=[]
        self.raise_on_activate=False
        self.failures=[]
        self.received=[]
    async def eligible(self,*,tenant,actor,seller):
        self.calls+=1
        if self.revoke_after_first and self.calls==2:self.allowed=False
        return self.allowed and tenant==T and actor==U and seller=="2002"
    async def stage_pending(self,*,pending):
        if not self.stage_allowed:return False
        self.staged.append(pending.revision)
        return True
    async def activate_cas(self,*,pending,access_hash,refresh_hash):
        if self.raise_on_activate:raise RuntimeError(tokens().refresh_token)
        self.received.append((access_hash,refresh_hash))
        assert len(access_hash)==len(refresh_hash)==64
        if not self.allowed or not self.activate_allowed:return False
        self.active=pending.revision
        return True
    async def mark_failed(self,*,pending):
        self.failures.append(pending.revision)
        return True

class Store:
    def __init__(self):
        self.staged=[]
        self.cancelled=[]
        self.error=False
        self.foreign=False
        self.bad_ref=False
    async def stage(self,*,tenant,actor,tokens):
        if self.error:raise RuntimeError(tokens.access_token)
        p=PendingTokenRevision(
            tenant_id=OTHER if self.foreign else tenant,actor_id=actor,
            seller_id=tokens.seller_id,revision="synthetic-revision-23500",
            credential_ref="x" if self.bad_ref else "synthetic-versioned-ref-23500",
            expected_generation=0)
        self.staged.append(p)
        return p
    async def cancel(self,*,pending):
        self.cancelled.append(pending.revision)
        return True

def make(*,enabled=True):
    registry=Registry();store=Store()
    return StagingOAuthTokenSink(registry=registry,store=store,enabled=enabled),registry,store

@pytest.mark.asyncio
async def test_authorized_revisions_require_two_checks_and_cas():
    sink,db,vault=make()
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is True
    assert db.calls==2 and db.active=="synthetic-revision-23500"
    assert len(db.received)==1 and not vault.cancelled
    assert tokens().access_token not in repr(vault.staged[0])

@pytest.mark.asyncio
async def test_disabled_never_calls_registry_or_vault():
    sink,db,vault=make(enabled=False)
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert db.calls==0 and not vault.staged

@pytest.mark.asyncio
async def test_revocation_before_stage_is_denied():
    sink,db,vault=make()
    db.allowed=False
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert not vault.staged and db.active=="existing-active-revision"

@pytest.mark.asyncio
async def test_revocation_after_staging_cancels_only_new_revision():
    sink,db,vault=make()
    db.revoke_after_first=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert db.active=="existing-active-revision"
    assert len(vault.cancelled)==len(db.failures)==1

@pytest.mark.asyncio
async def test_failed_cas_preserves_previous_active_revision():
    sink,db,vault=make()
    db.activate_allowed=False
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert db.active=="existing-active-revision"
    assert len(vault.cancelled)==1

@pytest.mark.asyncio
async def test_store_exception_returns_safe_failure():
    sink,db,vault=make()
    vault.error=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert db.active=="existing-active-revision" and not vault.staged

@pytest.mark.asyncio
async def test_activation_exception_keeps_existing_account_and_cancels():
    sink,db,vault=make()
    db.raise_on_activate=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert db.active=="existing-active-revision"
    assert len(db.failures)==1 and len(vault.cancelled)==1

@pytest.mark.asyncio
async def test_foreign_pending_identity_is_never_cancelled_under_our_context():
    sink,db,vault=make()
    vault.foreign=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert not vault.cancelled and not db.failures

@pytest.mark.asyncio
async def test_invalid_reference_fails_closed_and_compensates():
    sink,db,vault=make()
    vault.bad_ref=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert len(vault.cancelled)==1 and db.active=="existing-active-revision"

@pytest.mark.parametrize("bad",[
    {"live_mode":True},{"scope":"read"},{"seller_id":"3003"},
    {"access_token":"short"},{"refresh_token":"short"},
    {"expires_in":0},{"seller_id":"²002"},
])
@pytest.mark.asyncio
async def test_malformed_token_never_reaches_secret_store(bad):
    sink,db,vault=make()
    assert await sink.persist_sandbox_connection(
        draft=draft(),tokens=replace(tokens(),**bad)) is False
    assert vault.staged==[]

@pytest.mark.asyncio
async def test_sql_stage_failure_cancels_new_secret_preserves_old():
    sink,db,vault=make()
    db.stage_allowed=False
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert db.active=="existing-active-revision"
    assert len(db.received)==0
    assert len(db.failures)==len(vault.cancelled)==1
