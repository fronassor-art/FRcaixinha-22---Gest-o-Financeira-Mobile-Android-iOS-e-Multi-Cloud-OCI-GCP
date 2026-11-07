"""M24200: a protected reference may be discarded ONLY after SQL FAILED proof."""
from pathlib import Path
from uuid import UUID

import pytest
from app.mp_oauth_staging_cas_registry import StagingSellerCASRegistry
from app.mp_oauth_staging_token_sink import PendingTokenRevision

T=UUID("00000000-0000-4000-8000-0000000000a1")
A=UUID("00000000-0000-4000-8000-0000000000a9")
B=UUID("00000000-0000-4000-8000-0000000000b9")


def pending(*,tenant=T,actor=A,seller="2002",revision="m24200-synthetic-revision-001",
            ref="vault://synthetic/secret-001"):
    return PendingTokenRevision(tenant,actor,seller,revision,ref,7)


class DB:
    def __init__(self):
        self.name="frcaixinha_staging"
        self.role="frcaixinha_mp_oauth_worker"
        self.pg=180006
        self.port=5432
        self.status="FAILED"
        self.ref="vault://synthetic/secret-001"
        self.calls=[]
        self.fail=False

    async def fetchrow(self,sql,*args):
        self.calls.append(("identity",sql,args))
        if self.fail:raise RuntimeError("test secret: do not expose")
        return {"db_name":self.name,"login_role":self.role,
                "pg_version":self.pg,"pg_port":self.port}

    async def fetchval(self,sql,*args):
        self.calls.append(("sql",sql,args))
        if self.fail:raise RuntimeError("test secret: do not expose")
        assert "mp_staging_oauth_failed_ref" in sql
        if args!=(T,A,"2002","m24200-synthetic-revision-001"):
            return None
        return self.ref if self.status=="FAILED" else None


@pytest.mark.asyncio
async def test_only_failed_revision_returns_opaque_ref():
    db=DB()
    reg=StagingSellerCASRegistry(db=db,enabled=True)
    assert await reg.failed_credential_ref(pending=pending())==db.ref
    assert len(db.calls)==2
    assert db.calls[1][2]==(T,A,"2002","m24200-synthetic-revision-001")


@pytest.mark.asyncio
@pytest.mark.parametrize("status",["ACTIVE","PENDING","RETIRED"])
async def test_non_failed_status_never_authorizes_deletion(status):
    db=DB();db.status=status
    assert await StagingSellerCASRegistry(db=db,enabled=True).failed_credential_ref(
        pending=pending()) is None


@pytest.mark.asyncio
async def test_disabled_registry_never_reads_database():
    db=DB()
    assert await StagingSellerCASRegistry(db=db).failed_credential_ref(
        pending=pending()) is None
    assert db.calls==[]


@pytest.mark.asyncio
@pytest.mark.parametrize("changed",["db","role","pg","port"])
async def test_worker_identity_guard_blocks_wrong_context(changed):
    db=DB()
    if changed=="db":db.name="frcaixinha_aistudio_dev"
    if changed=="role":db.role="frc_ai_owner"
    if changed=="pg":db.pg=170000
    if changed=="port":db.port=5433
    assert await StagingSellerCASRegistry(db=db,enabled=True).failed_credential_ref(
        pending=pending()) is None
    assert all(k!="sql" for k,_,_ in db.calls)


@pytest.mark.asyncio
async def test_tenant_actor_seller_revision_mismatches_are_not_authorized():
    db=DB()
    reg=StagingSellerCASRegistry(db=db,enabled=True)
    for item in (
        pending(tenant=B), pending(actor=B),
        pending(seller="3003"), pending(revision="m24200-wrong-revision-001"),
    ):
        assert await reg.failed_credential_ref(pending=item) is None


@pytest.mark.asyncio
async def test_sql_exception_and_invalid_ref_deny():
    db=DB();reg=StagingSellerCASRegistry(db=db,enabled=True)
    db.fail=True
    assert await reg.failed_credential_ref(pending=pending()) is None
    db.fail=False
    db.ref="not a valid opaque identifier"
    assert await reg.failed_credential_ref(pending=pending()) is None


def test_sql_048_staging_and_worker_contracts():
    root=Path(__file__).resolve().parents[1]
    sql=(root/"staging_migrations/048_mp_oauth_failed_reference_staging_only.sql").read_text()
    probe=(root/"ci_migrations/044_oauth_failed_reference_worker_probe_ci_only.sql").read_text()
    chain=(root/"scripts/aistudio_staging_chain_ci.sh").read_text()
    adapter=(root/"app/mp_oauth_staging_cas_registry.py").read_text()
    store=(root/"app/mp_oauth_staging_credential_store.py").read_text()
    for must in (
        "current_database()<>'frcaixinha_staging'",
        "frcaixinha.mp_oauth_staging_authorized",
        "session_user<>'frcaixinha_mp_oauth_worker'",
        "CREATE UNIQUE INDEX mp_oauth_unique_credential_ref_staging",
        "r.status='FAILED'",
        "c.active_revision=r.revision",
        "SECURITY DEFINER",
        "GRANT EXECUTE ON FUNCTION public.mp_staging_oauth_failed_ref",
    ):
        assert must in sql,must
    assert "M24200_FAILED_REFERENCE_WORKER_SCOPE=PASS" in probe
    assert "M24200 DIRECT READ FORBIDDEN" in probe
    assert chain.index("048_mp_oauth_failed_reference_staging_only.sql") < chain.index(
        "044_oauth_failed_reference_worker_probe_ci_only.sql")
    assert chain.index("044_oauth_failed_reference_worker_probe_ci_only.sql") < chain.index(
        "042_oauth_revocation_probe_ci_only.sql")
    assert 'PGPORT:-}" = "5432"' in chain
    assert "FRCAIXINHA_CI_ISOLATED" in chain
    assert "GITHUB_ACTIONS" in chain
    assert "public.mp_staging_oauth_failed_ref(" in adapter
    assert "await self._registry.failed_credential_ref(" in store
    assert "compare_digest(verified_ref,pending.credential_ref)" in store
    assert "if can_discard" not in store


def test_staging_migration_catalog_never_authorizes_termux_apply():
    import json
    root=Path(__file__).resolve().parents[2]
    catalog=json.loads((root/"backend/migration_catalog_ai_studio.json").read_text())
    assert len(catalog["entries"])==len({entry["source_path"] for entry in catalog["entries"]})
    for name in ("048_mp_oauth_failed_reference_staging_only.sql",
                 "044_oauth_failed_reference_worker_probe_ci_only.sql"):
        found=[r for r in catalog["entries"] if r["source_path"].endswith(name)]
        assert len(found)==1
        assert found[0]["do_not_apply_source_to_termux"] is True
