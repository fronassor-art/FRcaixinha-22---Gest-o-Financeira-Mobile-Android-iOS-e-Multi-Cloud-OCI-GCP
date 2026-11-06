"""M23300: data/identity and ephemeral PKCE Vault bridge, only fakes."""
from datetime import datetime,timezone
from hashlib import sha256
from urllib.parse import parse_qs,urlsplit
from uuid import UUID,uuid4
import httpx
import pytest
from app.dependencies import AuthenticatedSession
from app.mp_oauth_staging_repository import StagingOAuthAttemptRepository
from app.mp_oauth_sandbox_coordinator import (
    OAuthSandboxCoordinator,SandboxConnectBlocked
)
from test_m2800_oci_mp_connectors_ci import PAYLOAD,APP_SECRET

T=UUID("00000000-0000-4000-8000-0000000000a1")
U=UUID("00000000-0000-4000-8000-0000000000a9")
OTHER=UUID("00000000-0000-4000-8000-0000000000a2")
NOW=1800000000
REDIRECT="https://app.example.invalid/connect/callback"
OCID="ocid1.secret.oc1.m23300-synthetic-only-ref-1234567"

class FakeDB:
    def __init__(self):
        self.name="frcaixinha_staging"
        self.role="frcaixinha_mp_oauth_worker"
        self.version=180006
        self.rows={}
        self.queries=[]
        self.error=False
        self.unsafe_challenge=False
    async def fetchrow(self,query,*args):
        self.queries.append(query)
        if "current_database()" in query:
            return dict(db_name=self.name,login_role=self.role,pg_version=self.version)
        if "mp_staging_oauth_consume" in query:
            if self.error:raise RuntimeError("mock db outage")
            tenant,actor,state_hash,redirect_hash=args
            record=self.rows.get(state_hash)
            if (record is None or record["tenant"]!=tenant or
                record["actor"]!=actor or record["redirect_hash"]!=redirect_hash
                or record["used"]):
                return None
            record["used"]=True
            return dict(
                client_id=record["draft"].client_id,
                redirect_uri=record["draft"].redirect_uri,
                pkce_verifier_secret_ocid=OCID,
                pkce_challenge=("Z"*43 if self.unsafe_challenge
                                else record["draft"].pkce_challenge),
                created_at=datetime.fromtimestamp(NOW,timezone.utc))
        raise AssertionError("unexpected query")
    async def fetchval(self,query,*args):
        self.queries.append(query)
        if self.error:raise RuntimeError("mock write refused")
        if "mp_staging_oauth_begin" not in query:raise AssertionError("query")
        tenant,actor,state_hash,redirect_hash,challenge,ref,cid,uri,ttl=args
        if state_hash in self.rows:return None
        self.rows[state_hash]=dict(tenant=tenant,actor=actor,
             redirect_hash=redirect_hash,draft=self.pending,used=False)
        return uuid4()

class FakeVault:
    def __init__(self):self.value=None;self.deleted=0;self.failed=False
    async def store_verifier(self,*,tenant_id,actor_id,verifier,ttl_seconds):
        if self.failed:raise RuntimeError("vault denied")
        assert ttl_seconds==600
        self.value=verifier
        return OCID
    async def read_verifier(self,*,secret_ocid):
        assert secret_ocid==OCID
        if self.failed:raise RuntimeError("vault denied")
        return self.value
    async def revoke_verifier(self,*,secret_ocid):
        assert secret_ocid==OCID
        self.deleted+=1
        if self.failed:return False
        return True

class FakeSellers:
    async def expected_seller(self,*,tenant_id,actor_id):
        return "2002" if tenant_id==T and actor_id==U else None

def session():
    return AuthenticatedSession(str(U),"TENANT_ADMIN",str(T),
                                "ci@example.invalid","CI",False)

def make(enabled=True):
    db=FakeDB()
    vault=FakeVault()
    repo=StagingOAuthAttemptRepository(
        db=db,vault=vault,sellers=FakeSellers(),enabled=enabled)
    calls=[]
    def transport(request):
        calls.append(request)
        return httpx.Response(200,json=PAYLOAD)
    service=OAuthSandboxCoordinator(attempts=repo,vault=FakeTokenSink(),
        client_secret=APP_SECRET,transport=httpx.MockTransport(transport))
    return service,db,vault,calls,repo

class FakeTokenSink:
    def __init__(self):self.tokens=[]
    async def persist_sandbox_connection(self,*,draft,tokens):
        self.tokens.append(tokens.seller_id)
        return True

async def open_one(service,db):
    # Store records only mock metadata; real repository stores no draft in PG.
    from app.mp_oauth_connect_preflight import prepare_oauth_draft
    # Wrapper to capture the otherwise internal preflight generated draft.
    orig=db.fetchval
    async def capture(query,*args):
        # Derive the generated verifier from our FakeVault? The authentic
        # draft is not public; emulate PG storing only params + Vault.
        db.pending=type("DraftMeta",(),dict(
            client_id=args[6],redirect_uri=args[7],pkce_challenge=args[4]))()
        return await orig(query,*args)
    db.fetchval=capture
    url=await service.begin(session=session(),tenant_id=T,
       client_id="123456",registered_redirect_uri=REDIRECT,now_epoch=NOW)
    return parse_qs(urlsplit(url).query)["state"][0]

@pytest.mark.asyncio
async def test_complete_uses_one_time_postgres_and_vault_reference():
    service,db,vault,calls,repo=make()
    state=await open_one(service,db)
    result=await service.complete(
        session=session(),tenant_id=T,state=state,
        authorization_code="TG-M23300-CODE",redirect_uri=REDIRECT,
        now_epoch=NOW+7)
    assert result.seller_id=="2002" and result.real_payments_enabled is False
    assert len(calls)==1
    assert vault.deleted==1
    assert len(db.rows)==1 and next(iter(db.rows.values()))["used"]
    with pytest.raises(SandboxConnectBlocked):
        await service.complete(session=session(),tenant_id=T,state=state,
            authorization_code="TG-M23300-CODE",redirect_uri=REDIRECT,
            now_epoch=NOW+8)
    assert len(calls)==1

@pytest.mark.asyncio
async def test_disabled_by_default_and_wrong_database_or_role():
    for bad in ("disabled","db","role","version"):
        service,db,vault,calls,repo=make(enabled=bad!="disabled")
        if bad=="db":db.name="frcaixinha_aistudio_dev"
        if bad=="role":db.role="frc_ai_owner"
        if bad=="version":db.version=170000
        with pytest.raises(SandboxConnectBlocked):
            await service.begin(session=session(),tenant_id=T,
               client_id="123456",registered_redirect_uri=REDIRECT,now_epoch=NOW)
        assert not db.rows and not calls

@pytest.mark.asyncio
async def test_other_tenant_cannot_consume_and_replay_fail_closed():
    service,db,vault,calls,repo=make()
    state=await open_one(service,db)
    other=await repo.consume_once(tenant_id=OTHER,actor_id=U,
        state_sha256=sha256(state.encode()).hexdigest(),
        redirect_sha256=sha256(REDIRECT.encode()).hexdigest(),
        provided_state=state,now_epoch=NOW+4)
    assert other is None
    assert next(iter(db.rows.values()))["used"] is False
    assert not calls

@pytest.mark.asyncio
async def test_challenge_or_vault_failure_blocks_token_exchange():
    for kind in ("challenge","vault"):
        service,db,vault,calls,repo=make()
        state=await open_one(service,db)
        if kind=="challenge":db.unsafe_challenge=True
        if kind=="vault":vault.failed=True
        with pytest.raises(SandboxConnectBlocked):
            await service.complete(session=session(),tenant_id=T,state=state,
                authorization_code="TG-M23300-CODE",
                redirect_uri=REDIRECT,now_epoch=NOW+5)
        assert not calls

@pytest.mark.asyncio
async def test_db_write_failure_compensates_vault_secret_without_reporting_success():
    service,db,vault,calls,repo=make()
    db.error=True
    with pytest.raises(SandboxConnectBlocked):
        await service.begin(session=session(),tenant_id=T,
            client_id="123456",registered_redirect_uri=REDIRECT,now_epoch=NOW)
    assert vault.deleted==1 and not db.rows and not calls

@pytest.mark.asyncio
async def test_no_plaintext_pkce_sent_to_postgres():
    service,db,vault,calls,repo=make()
    await open_one(service,db)
    assert vault.value
    assert vault.value not in str(db.queries)
    assert all("code_verifier" not in query for query in db.queries)
