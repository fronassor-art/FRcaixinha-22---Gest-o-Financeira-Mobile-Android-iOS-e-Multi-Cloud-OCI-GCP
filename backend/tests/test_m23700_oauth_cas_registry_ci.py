"""M23700: the OAuth CAS registry only uses worker-scoped PostgreSQL 18."""
from uuid import UUID
import pytest
from app.mp_oauth_staging_cas_registry import StagingSellerCASRegistry
from app.mp_oauth_staging_token_sink import PendingTokenRevision

T=UUID("00000000-0000-4000-8000-0000000000a1")
A=UUID("00000000-0000-4000-8000-0000000000a9")
B=UUID("00000000-0000-4000-8000-0000000000b9")
SHA1="a"*64
SHA2="b"*64

def pending(tenant=T,actor=A,seller="2002",revision="m23700-synthetic-revision-001"):
    return PendingTokenRevision(tenant,actor,seller,revision,"kms://synthetic/secret-001")

class DB:
    def __init__(self):
        self.name="frcaixinha_staging"
        self.role="frcaixinha_mp_oauth_worker"
        self.version=180006
        self.port=5432
        self.revoked=False
        self.can_activate=True
        self.active="old-version-active"
        self.pending=True
        self.calls=[]
        self.fail=False
    async def fetchrow(self,query,*args):
        assert "current_database()" in query
        self.calls.append(("identity",query,args))
        if self.fail:raise RuntimeError("fake postgres network fault")
        return dict(db_name=self.name,login_role=self.role,
                    pg_version=self.version,pg_port=self.port)
    async def fetchval(self,query,*args):
        self.calls.append(("sql",query,args))
        if self.fail:raise RuntimeError("fake postgres rejected")
        if "mp_staging_oauth_eligible" in query:
            tenant,actor,seller=args
            return tenant==T and actor==A and seller=="2002" and not self.revoked
        if "mp_staging_oauth_activate" in query:
            tenant,actor,seller,revision,access,refresh=args
            if (tenant!=T or actor!=A or seller!="2002"
                or self.revoked or not self.pending or not self.can_activate):
                return False
            self.active=revision
            self.pending=False
            return True
        if "mp_staging_oauth_fail_pending" in query:
            tenant,actor,seller,revision=args
            if tenant!=T or actor!=A or seller!="2002" or not self.pending:
                return False
            self.pending=False
            return True
        if "mp_staging_oauth_active_ref" in query:
            tenant,actor,seller=args
            return ("kms://synthetic/secret-001" if
                    tenant==T and actor==A and seller=="2002" and not self.revoked
                    else None)
        raise AssertionError("unexpected SQL")

@pytest.mark.asyncio
async def test_disabled_by_default_never_opens_db():
    db=DB();r=StagingSellerCASRegistry(db=db)
    assert await r.eligible(tenant=T,actor=A,seller="2002") is False
    assert await r.activate_cas(pending=pending(),access_hash=SHA1,refresh_hash=SHA2) is False
    assert await r.mark_failed(pending=pending()) is False
    assert await r.active_credential_ref(tenant=T,actor=A,seller="2002") is None
    assert not db.calls

@pytest.mark.asyncio
@pytest.mark.parametrize("invalid",["db","role","version","port","null_port"])
async def test_identity_mismatch_blocks_every_financial_identity_method(invalid):
    db=DB()
    if invalid=="db":db.name="frcaixinha_aistudio_dev"
    if invalid=="role":db.role="frc_ai_owner"
    if invalid=="version":db.version=170000
    if invalid=="port":db.port=5433
    if invalid=="null_port":db.port=None
    r=StagingSellerCASRegistry(db=db,enabled=True)
    assert await r.eligible(tenant=T,actor=A,seller="2002") is False
    assert await r.activate_cas(pending=pending(),access_hash=SHA1,refresh_hash=SHA2) is False
    assert await r.mark_failed(pending=pending()) is False
    assert await r.active_credential_ref(tenant=T,actor=A,seller="2002") is None
    assert not any(x[0]=="sql" for x in db.calls)

@pytest.mark.asyncio
async def test_valid_worker_can_eligible_activate_and_read_reference():
    db=DB();r=StagingSellerCASRegistry(db=db,enabled=True)
    assert await r.eligible(tenant=T,actor=A,seller="2002") is True
    assert await r.activate_cas(pending=pending(),access_hash=SHA1,refresh_hash=SHA2) is True
    assert db.active=="m23700-synthetic-revision-001"
    assert await r.active_credential_ref(tenant=T,actor=A,seller="2002")=="kms://synthetic/secret-001"
    assert sum(x[0]=="sql" for x in db.calls)==3
    assert all("TEST_REFRESH_TOKEN" not in repr(x) for x in db.calls)

@pytest.mark.asyncio
async def test_revocation_and_cross_tenant_denied():
    db=DB();r=StagingSellerCASRegistry(db=db,enabled=True)
    assert await r.eligible(tenant=B,actor=A,seller="2002") is False
    db.revoked=True
    assert await r.activate_cas(pending=pending(),access_hash=SHA1,refresh_hash=SHA2) is False
    assert await r.active_credential_ref(tenant=T,actor=A,seller="2002") is None
    assert db.active=="old-version-active"

@pytest.mark.asyncio
async def test_revision_conflict_and_failure_keep_existing_active():
    db=DB();db.can_activate=False
    r=StagingSellerCASRegistry(db=db,enabled=True)
    assert await r.activate_cas(pending=pending(),access_hash=SHA1,refresh_hash=SHA2) is False
    assert db.active=="old-version-active"
    assert await r.mark_failed(pending=pending()) is True
    assert db.active=="old-version-active"
    assert await r.activate_cas(pending=pending(),access_hash=SHA1,refresh_hash=SHA2) is False

@pytest.mark.asyncio
@pytest.mark.parametrize("bad",[
    "00","a"*63,"G"*64,"a"*65,"TEST_REFRESH_TOKEN_MUST_NOT_LEAK",
])
async def test_malformed_token_fingerprint_never_reaches_sql(bad):
    db=DB();r=StagingSellerCASRegistry(db=db,enabled=True)
    assert await r.activate_cas(pending=pending(),access_hash=SHA1,refresh_hash=bad) is False
    assert not db.calls

@pytest.mark.asyncio
async def test_seller_and_revision_require_ascii_tenant_scope():
    db=DB();r=StagingSellerCASRegistry(db=db,enabled=True)
    assert await r.eligible(tenant=T,actor=A,seller="²002") is False
    assert await r.activate_cas(
        pending=pending(seller="²002"),access_hash=SHA1,refresh_hash=SHA2
    ) is False
    assert await r.mark_failed(pending=pending(revision="../" )) is False
    assert not db.calls

@pytest.mark.asyncio
async def test_worker_database_exception_fail_closed_without_token_logs():
    db=DB();db.fail=True;r=StagingSellerCASRegistry(db=db,enabled=True)
    assert await r.eligible(tenant=T,actor=A,seller="2002") is False
    assert await r.activate_cas(pending=pending(),access_hash=SHA1,refresh_hash=SHA2) is False
    assert await r.mark_failed(pending=pending()) is False
