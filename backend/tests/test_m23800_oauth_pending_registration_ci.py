"""M23800 — PENDING registration and OAuth CAS, synthetic only."""
from uuid import UUID
import pytest
from app.mp_oauth_connect_preflight import prepare_oauth_draft
from app.mp_connect_http_runtime import OAuthTokens
from app.mp_oauth_staging_cas_registry import StagingSellerCASRegistry
from app.mp_oauth_staging_token_sink import PendingTokenRevision, StagingOAuthTokenSink

T=UUID("00000000-0000-4000-8000-0000000000a1")
A=UUID("00000000-0000-4000-8000-0000000000a9")
B=UUID("00000000-0000-4000-8000-0000000000b9")

def draft():
    return prepare_oauth_draft(tenant_id=T,initiated_by=A,client_id="123456",
        registered_redirect_uri="https://example.invalid/connect/callback",now_epoch=1800000000)

def tokens():
    return OAuthTokens(seller_id="2002",scope="read offline_access",expires_in=3600,
        access_token="TEST_ACCESS_M23800_SYNTHETIC_1234",
        refresh_token="TEST_REFRESH_M23800_SYNTHETIC_1234",live_mode=False)

class DB:
    def __init__(self):
        self.generation=3
        self.active="old-active-revision"
        self.pending=None
        self.revoked=False
        self.revoke_on_second=False
        self.eligibility_calls=0
        self.activate_ok=True
        self.stage_error=False
        self.calls=[]
    async def fetchrow(self,query,*args):
        assert "current_database()" in query
        return dict(db_name="frcaixinha_staging",login_role="frcaixinha_mp_oauth_worker",
                    pg_version=180006,pg_port=5432)
    async def fetchval(self,query,*args):
        self.calls.append((query,args))
        if "mp_staging_oauth_eligible" in query:
            self.eligibility_calls+=1
            if self.revoke_on_second and self.eligibility_calls==2:self.revoked=True
            return args==(T,A,"2002") and not self.revoked
        if "mp_staging_oauth_stage" in query:
            if self.stage_error:raise RuntimeError("synthetic SQL failure")
            tenant,actor,seller,revision,ref,generation=args
            if ((tenant,actor,seller)!=(T,A,"2002") or generation!=self.generation
                    or self.revoked or self.pending is not None):return False
            self.pending=revision
            return True
        if "mp_staging_oauth_activate" in query:
            tenant,actor,seller,revision,access_hash,refresh_hash=args
            if ((tenant,actor,seller)!=(T,A,"2002") or self.pending!=revision
                    or self.revoked or not self.activate_ok
                    or len(access_hash)!=64 or len(refresh_hash)!=64):return False
            self.active=revision
            self.generation+=1
            self.pending=None
            return True
        if "mp_staging_oauth_fail_pending" in query:
            tenant,actor,seller,revision=args
            if ((tenant,actor,seller)!=(T,A,"2002") or self.pending!=revision):return False
            self.pending=None
            return True
        raise AssertionError("unexpected SQL")
class Store:
    def __init__(self,generation=3):
        self.generation=generation
        self.cancelled=[]
        self.staged=[]
    async def stage(self,*,tenant,actor,tokens):
        p=PendingTokenRevision(tenant,actor,tokens.seller_id,
            "m23800-synthetic-revision-003","vault://synthetic/opaque-ref-003",
            self.generation)
        self.staged.append(p)
        return p
    async def cancel(self,*,pending):
        self.cancelled.append(pending.revision)
        return True
def setup(generation=3,enabled=True):
    db=DB()
    store=Store(generation)
    registry=StagingSellerCASRegistry(db=db,enabled=enabled)
    sink=StagingOAuthTokenSink(registry=registry,store=store,enabled=enabled)
    return sink,registry,db,store

@pytest.mark.asyncio
async def test_ordered_stage_before_cas_and_no_raw_tokens_in_sql():
    sink,registry,db,store=setup()
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is True
    calls=[q for q,_ in db.calls]
    assert len(calls)==4
    assert "eligible" in calls[0] and "eligible" in calls[1]
    assert "stage" in calls[2] and "activate" in calls[3]
    assert db.active=="m23800-synthetic-revision-003"
    assert db.generation==4 and db.pending is None and not store.cancelled
    assert tokens().access_token not in repr(db.calls)
    assert tokens().refresh_token not in repr(db.calls)

@pytest.mark.asyncio
async def test_stale_generation_fails_and_preserves_active():
    sink,registry,db,store=setup(generation=2)
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert db.active=="old-active-revision" and db.pending is None
    assert not any("mp_staging_oauth_activate" in q for q,_ in db.calls)
    # SQL rejected a PENDING attempt but the API cannot prove rollback;
    # retain the reference until a definitive reconciliation.
    assert store.cancelled==[]

@pytest.mark.asyncio
async def test_revocation_between_checks_denies_stage():
    sink,registry,db,store=setup()
    db.revoke_on_second=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert db.active=="old-active-revision"
    assert not any("mp_staging_oauth_stage" in q for q,_ in db.calls)
    assert len(store.cancelled)==1

@pytest.mark.asyncio
async def test_failed_activation_compensates_without_retiring_old():
    sink,registry,db,store=setup()
    db.activate_ok=False
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert db.pending is None and db.active=="old-active-revision"
    assert len(store.cancelled)==1
    assert any("mp_staging_oauth_fail_pending" in q for q,_ in db.calls)

@pytest.mark.asyncio
async def test_sql_stage_exception_fails_closed():
    sink,registry,db,store=setup()
    db.stage_error=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    # SQL stage attempted; False or exception cannot prove rollback.
    # Retain the opaque ref until reconciliation if no FAILED ack.
    assert db.active=="old-active-revision" and not store.cancelled

@pytest.mark.asyncio
async def test_disabled_never_touches_db_or_store():
    sink,registry,db,store=setup(enabled=False)
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert not db.calls and not store.staged

@pytest.mark.asyncio
@pytest.mark.parametrize("generation",[-1,None,True,2**63,"3"])
async def test_invalid_generation_cannot_be_registered(generation):
    sink,registry,db,store=setup(generation=generation)
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert db.active=="old-active-revision"
    assert not any("mp_staging_oauth_stage" in q for q,_ in db.calls)
    assert len(store.cancelled)==1

@pytest.mark.asyncio
async def test_cross_tenant_registration_is_rejected():
    sink,registry,db,store=setup()
    p=PendingTokenRevision(B,A,"2002","m23800-synthetic-revision-003",
        "vault://synthetic/opaque-ref-003",3)
    assert await registry.stage_pending(pending=p) is False
    assert db.active=="old-active-revision" and db.pending is None
