"""M24100: sandbox credential staging uses worker consent generation and fake writer."""
from dataclasses import replace
from uuid import UUID
import pytest

from app.mp_connect_http_runtime import OAuthTokens
from app.mp_oauth_connect_preflight import prepare_oauth_draft
from app.mp_oauth_staging_token_sink import (
    PendingTokenRevision,StagingOAuthTokenSink,
)
from app.mp_oauth_staging_credential_store import (
    StagingProtectedCredentialStore,ProtectedStorageUnavailable,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
A=UUID("00000000-0000-4000-8000-0000000000a9")
B=UUID("00000000-0000-4000-8000-0000000000b9")

def draft():
    return prepare_oauth_draft(
        tenant_id=T,initiated_by=A,client_id="123456",
        registered_redirect_uri="https://example.invalid/connect/callback",
        now_epoch=1800000000)

def tokens():
    return OAuthTokens(
        seller_id="2002",scope="read offline_access",expires_in=3600,
        access_token="SYNTHETIC_M24100_ACCESS_TOKEN_123456",
        refresh_token="SYNTHETIC_M24100_REFRESH_TOKEN_123",
        live_mode=False)

class Registry:
    def __init__(self):
        self.generation=3
        self.revoked=False
        self.active="existing-active-revision"
        self.pending=None
        self.invalid_gen=False
        self.calls=[]
        self.activation_blocked=False
        self.lost_ack=False
        self.unconfirmed_pending=False
    async def eligible(self,*,tenant,actor,seller):
        self.calls.append("eligible")
        return (tenant,actor,seller)==(T,A,"2002") and not self.revoked
    async def consent_generation(self,*,tenant,actor,seller):
        self.calls.append("generation")
        if self.invalid_gen:return None
        return self.generation if (tenant,actor,seller)==(T,A,"2002") and not self.revoked else None
    async def stage_pending(self,*,pending):
        self.calls.append("stage_pending")
        if pending.expected_generation!=self.generation or self.revoked:
            return False
        self.pending=pending
        return True
    async def activate_cas(self,*,pending,access_hash,refresh_hash):
        self.calls.append("activate_cas")
        if self.activation_blocked or self.pending!=pending or self.revoked:
            return False
        assert len(access_hash)==len(refresh_hash)==64
        self.active=pending.revision
        self.pending=None
        self.generation+=1
        if self.lost_ack: raise TimeoutError("ack missing")
        return True
    async def mark_failed(self,*,pending):
        self.calls.append("mark_failed")
        if self.unconfirmed_pending:return False
        if self.pending==pending:
            self.pending=None
            return True
        return False

class Writer:
    def __init__(self):
        self.revisions={}
        self.deleted=[]
        self.fail_write=False
        self.fail_delete=False
        self.invalid_ref=False
        self.history=[]
    async def write_encrypted(self,*,tenant,actor,seller,revision,tokens):
        self.history.append(("write",revision,tenant,actor,seller))
        if self.fail_write: raise RuntimeError(tokens.access_token)
        ref=("invalid" if self.invalid_ref else "vault://staging/"+revision)
        self.revisions[revision]=ref
        return ref
    async def discard_confirmed_failed(self,*,tenant,actor,seller,revision,credential_ref):
        self.history.append(("discard",revision,tenant,actor,seller))
        if self.fail_delete: raise RuntimeError("synthetic failure")
        if self.revisions.get(revision)!=credential_ref:return False
        del self.revisions[revision]
        self.deleted.append(revision)
        return True

def create(enabled=True):
    r=Registry();w=Writer()
    store=StagingProtectedCredentialStore(registry=r,writer=w,enabled=enabled)
    sink=StagingOAuthTokenSink(registry=r,store=store,enabled=enabled)
    return r,w,store,sink

@pytest.mark.asyncio
async def test_full_synthetic_staging_registered_then_cas_without_tokens_in_sql():
    r,w,store,sink=create()
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is True
    assert r.calls==["eligible","generation","eligible","stage_pending","activate_cas"]
    assert r.pending is None and len(w.revisions)==1 and not w.deleted
    assert r.active.startswith("m24100-")
    assert tokens().access_token not in repr(w.history)
    assert tokens().refresh_token not in repr(w.history)

@pytest.mark.asyncio
async def test_disabled_by_default_never_calls_writer():
    r,w,store,sink=create(enabled=False)
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert not r.calls and not w.revisions

@pytest.mark.asyncio
async def test_no_consent_does_not_store_any_token():
    r,w,store,sink=create()
    r.invalid_gen=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert w.revisions=={} and w.history==[]

@pytest.mark.asyncio
async def test_cross_tenant_direct_stage_rejected_by_consent_reader():
    r,w,store,sink=create()
    with pytest.raises(ProtectedStorageUnavailable):
        await store.stage(tenant=B,actor=A,tokens=tokens())
    assert w.history==[]

@pytest.mark.asyncio
async def test_expired_or_live_tokens_cannot_be_staged():
    r,w,store,sink=create()
    with pytest.raises(ProtectedStorageUnavailable):
        await store.stage(tenant=T,actor=A,tokens=replace(tokens(),live_mode=True))
    assert not r.calls and not w.history

@pytest.mark.asyncio
async def test_writer_exception_redacts_secret_and_no_cancel_before_revision():
    r,w,store,sink=create()
    w.fail_write=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert not w.revisions and not w.deleted

@pytest.mark.asyncio
async def test_invalid_writer_reference_fails_closed():
    r,w,store,sink=create()
    w.invalid_ref=True
    with pytest.raises(ProtectedStorageUnavailable):
        await store.stage(tenant=T,actor=A,tokens=tokens())
    assert not store._pending
    assert not w.deleted

@pytest.mark.asyncio
async def test_activation_rejection_marks_failed_before_discards():
    r,w,store,sink=create()
    r.activation_blocked=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert r.active=="existing-active-revision"
    assert w.deleted and not w.revisions
    assert r.calls.index("mark_failed")>r.calls.index("activate_cas")

@pytest.mark.asyncio
async def test_lost_ack_after_commit_keeps_active_reference():
    r,w,store,sink=create()
    r.lost_ack=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert r.active.startswith("m24100-") and not w.deleted
    assert len(w.revisions)==1

@pytest.mark.asyncio
async def test_no_failed_proof_keeps_unconfirmed_blob():
    r,w,store,sink=create()
    r.activation_blocked=True
    r.unconfirmed_pending=True
    assert await sink.persist_sandbox_connection(draft=draft(),tokens=tokens()) is False
    assert r.active=="existing-active-revision"
    assert len(w.revisions)==1 and w.deleted==[]

@pytest.mark.asyncio
async def test_cancel_foreign_or_forged_revision_is_rejected():
    r,w,store,sink=create()
    saved=await store.stage(tenant=T,actor=A,tokens=tokens())
    other=PendingTokenRevision(B,A,saved.seller_id,saved.revision,
                               saved.credential_ref,saved.expected_generation)
    assert await store.cancel(pending=other) is False
    assert saved.revision in w.revisions

@pytest.mark.asyncio
async def test_delete_failure_keeps_record_for_reconciliation():
    r,w,store,sink=create()
    item=await store.stage(tenant=T,actor=A,tokens=tokens())
    w.fail_delete=True
    assert await store.cancel(pending=item) is False
    assert item.revision in w.revisions

def test_explicitly_no_vault_or_production_network_runtime():
    from pathlib import Path
    src=(Path(__file__).resolve().parents[1]/
         "app/mp_oauth_staging_credential_store.py").read_text()
    for forbidden in ("oci.vault", "requests.post(", "httpx.post(",
                      "create_secret(", "launch_instance("):
        assert forbidden not in src
    assert "enabled: bool = False" in src
    assert "EncryptedRevisionWriter(Protocol)" in src
