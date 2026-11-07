"""M23900: trusted consent-generation read, strictly sandbox and fake DB."""
from uuid import UUID

import pytest
from app.mp_oauth_staging_cas_registry import StagingSellerCASRegistry

TENANT=UUID("00000000-0000-4000-8000-0000000000a1")
ACTOR=UUID("00000000-0000-4000-8000-0000000000a9")
FOREIGN=UUID("00000000-0000-4000-8000-0000000000b9")


class FakeWorker:
    def __init__(self):
        self.db="frcaixinha_staging"
        self.role="frcaixinha_mp_oauth_worker"
        self.pg=180006
        self.port=5432
        self.gen=7
        self.revoked=False
        self.calls=[]
        self.fail=False

    async def fetchrow(self,query,*args):
        self.calls.append(("identity",query,args))
        if self.fail:raise ConnectionError("synthetic secret must not escape")
        return dict(db_name=self.db,login_role=self.role,pg_version=self.pg,
                    pg_port=self.port)

    async def fetchval(self,query,*args):
        self.calls.append(("query",query,args))
        if self.fail:raise ConnectionError("synthetic database failure")
        assert "mp_staging_oauth_generation" in query
        tenant,actor,seller=args
        if ((tenant,actor,seller)!=(TENANT,ACTOR,"2002")
                or self.revoked):
            return None
        return self.gen


@pytest.mark.asyncio
async def test_generation_worker_only_success():
    db=FakeWorker()
    adapter=StagingSellerCASRegistry(db=db,enabled=True)
    assert await adapter.consent_generation(
        tenant=TENANT,actor=ACTOR,seller="2002") == 7
    assert len(db.calls)==2
    assert db.calls[1][2]==(TENANT,ACTOR,"2002")
    assert "mp_staging_oauth_generation" in db.calls[1][1]


@pytest.mark.asyncio
async def test_generation_disabled_default_never_calls_db():
    db=FakeWorker()
    adapter=StagingSellerCASRegistry(db=db)
    assert await adapter.consent_generation(
        tenant=TENANT,actor=ACTOR,seller="2002") is None
    assert db.calls==[]


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper",["db","role","pg","port"])
async def test_fail_closed_if_database_identity_mismatches(tamper):
    db=FakeWorker()
    if tamper=="db":db.db="frcaixinha_aistudio_dev"
    if tamper=="role":db.role="frc_ai_owner"
    if tamper=="pg":db.pg=170006
    if tamper=="port":db.port=5433
    adapter=StagingSellerCASRegistry(db=db,enabled=True)
    assert await adapter.consent_generation(
        tenant=TENANT,actor=ACTOR,seller="2002") is None
    assert not any(call[0]=="query" for call in db.calls)


@pytest.mark.asyncio
async def test_cross_tenant_actor_seller_and_revocation_return_no_version():
    db=FakeWorker()
    adapter=StagingSellerCASRegistry(db=db,enabled=True)
    assert await adapter.consent_generation(
        tenant=FOREIGN,actor=ACTOR,seller="2002") is None
    assert await adapter.consent_generation(
        tenant=TENANT,actor=FOREIGN,seller="2002") is None
    assert await adapter.consent_generation(
        tenant=TENANT,actor=ACTOR,seller="3003") is None
    db.revoked=True
    assert await adapter.consent_generation(
        tenant=TENANT,actor=ACTOR,seller="2002") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed",[-1,True,"7",None,2**63])
async def test_invalid_generation_is_not_silently_coerced(malformed):
    db=FakeWorker();db.gen=malformed
    adapter=StagingSellerCASRegistry(db=db,enabled=True)
    assert await adapter.consent_generation(
        tenant=TENANT,actor=ACTOR,seller="2002") is None


@pytest.mark.asyncio
async def test_generation_zero_allowed_and_server_errors_block():
    db=FakeWorker();db.gen=0
    adapter=StagingSellerCASRegistry(db=db,enabled=True)
    assert await adapter.consent_generation(
        tenant=TENANT,actor=ACTOR,seller="2002") == 0
    db.fail=True
    assert await adapter.consent_generation(
        tenant=TENANT,actor=ACTOR,seller="2002") is None


@pytest.mark.asyncio
async def test_reject_non_ascii_seller_before_opening_db():
    db=FakeWorker()
    adapter=StagingSellerCASRegistry(db=db,enabled=True)
    assert await adapter.consent_generation(
        tenant=TENANT,actor=ACTOR,seller="²002") is None
    assert db.calls==[]


def test_sql_staging_guard_and_ci_probe_contracts():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    sql=(root/"staging_migrations/047_mp_oauth_generation_staging_only.sql").read_text()
    probe=(root/"ci_migrations/043_oauth_generation_worker_probe_ci_only.sql").read_text()
    script=(root/"scripts/aistudio_staging_chain_ci.sh").read_text()
    for required in (
        "current_database()<>'frcaixinha_staging'",
        "frcaixinha.mp_oauth_staging_authorized",
        "session_user<>'frcaixinha_mp_oauth_worker'",
        "m.role='TENANT_ADMIN' AND m.status='ATIVA'",
        "c.revoked_at IS NULL",
        "SECURITY DEFINER",
        "GRANT EXECUTE ON FUNCTION",
    ):
        assert required in sql,required
    assert sql.count("\nBEGIN;")==1 and sql.count("\nCOMMIT;")==1
    assert "M23900_GENERATION_WORKER_SCOPE=PASS" in probe
    assert "047_mp_oauth_generation_staging_only.sql" in script
    assert "043_oauth_generation_worker_probe_ci_only.sql" in script
    assert "FRCAIXINHA_CI_ISOLATED" in script
    assert "GITHUB_ACTIONS" in script
    assert 'PGPORT:-}" = "5432"' in script
    assert "LOCAL_MIGRATIONS=NOT_TOUCHED" in script
    assert "REAL_MONEY=OFF" in script
