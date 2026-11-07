"""M24300: read-only worker-scoped OAuth revision recovery. No external IO."""
from uuid import UUID
import pytest

from app.mp_oauth_staging_cas_registry import StagingSellerCASRegistry
from app.mp_oauth_staging_reconciliation import StagingOAuthRecoveryInspector
from app.mp_oauth_staging_token_sink import PendingTokenRevision


T=UUID("00000000-0000-4000-8000-0000000000a1")
A=UUID("00000000-0000-4000-8000-0000000000a9")
B=UUID("00000000-0000-4000-8000-0000000000b9")
REF="vault://synthetic/m24300-opaque-reference-001"
REV="m24300-synthetic-revision-001"


def pending(tenant=T, actor=A, seller="2002", revision=REV, ref=REF):
    return PendingTokenRevision(tenant,actor,seller,revision,ref,3)


class FakeDatabase:
    def __init__(self):
        self.name="frcaixinha_staging"
        self.role="frcaixinha_mp_oauth_worker"
        self.version=180006
        self.port=5432
        self.state="PENDING"
        self.fail=False
        self.revoked=False
        self.calls=[]

    async def fetchrow(self, query, *args):
        self.calls.append(("identity",query,args))
        if self.fail: raise ConnectionError("synthetic IO failure")
        assert "current_database()" in query
        return dict(db_name=self.name,login_role=self.role,
                    pg_version=self.version,pg_port=self.port)

    async def fetchval(self, query, *args):
        self.calls.append(("revision",query,args))
        if self.fail: raise ConnectionError("synthetic SQL failure")
        assert "public.mp_staging_oauth_revision_state" in query
        if args!=(T,A,"2002",REV,REF):
            return None
        # Revocation does NOT rewrite a historical row's stored status.
        return self.state


@pytest.mark.asyncio
@pytest.mark.parametrize(("state","step"),[
    ("PENDING","RETAIN_AND_RECONCILE_REGISTRATION"),
    ("ACTIVE","RETAIN_AND_RECHECK_CURRENT_CONSENT"),
    ("FAILED","REQUIRE_SEPARATE_FAILED_REF_PROOF_BEFORE_CLEANUP"),
    ("RETIRED","RETAIN_UNTIL_APPROVED_RETENTION_POLICY"),
])
async def test_state_verdict_is_readonly_never_authorizes_live_operations(state,step):
    db=FakeDatabase();db.state=state
    reg=StagingSellerCASRegistry(db=db,enabled=True)
    inspector=StagingOAuthRecoveryInspector(registry=reg,enabled=True)
    v=await inspector.inspect(pending=pending())
    assert v.state==state and v.next_step==step
    assert v.automatic_deletion_allowed is False
    assert v.merchant_connection_authorized is False
    assert v.real_payments_authorized is False
    assert sum(x[0]=="revision" for x in db.calls)==1
    assert "access_token" not in repr(db.calls)
    assert "refresh_token" not in repr(db.calls)


@pytest.mark.asyncio
async def test_disabled_integration_never_opens_db():
    db=FakeDatabase()
    reg=StagingSellerCASRegistry(db=db,enabled=True)
    inspector=StagingOAuthRecoveryInspector(registry=reg)
    v=await inspector.inspect(pending=pending())
    assert v.state=="UNKNOWN" and v.next_step=="RETAIN_FOR_MANUAL_RECONCILIATION"
    assert db.calls==[]


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong",["database","role","version","port"])
async def test_prohibited_database_identity_denies_revision_lookup(wrong):
    db=FakeDatabase()
    if wrong=="database":db.name="frcaixinha_aistudio_dev"
    if wrong=="role":db.role="frc_ai_owner"
    if wrong=="version":db.version=170006
    if wrong=="port":db.port=5433
    reg=StagingSellerCASRegistry(db=db,enabled=True)
    inspector=StagingOAuthRecoveryInspector(registry=reg,enabled=True)
    verdict=await inspector.inspect(pending=pending())
    assert verdict.state=="UNKNOWN"
    assert all(x[0]!="revision" for x in db.calls)


@pytest.mark.asyncio
async def test_cross_tenant_actor_seller_and_ref_do_not_return_status():
    db=FakeDatabase()
    reg=StagingSellerCASRegistry(db=db,enabled=True)
    inspector=StagingOAuthRecoveryInspector(registry=reg,enabled=True)
    for candidate in (
        pending(tenant=B),
        pending(actor=B),
        pending(seller="3003"),
        pending(revision="m24300-another-revision-001"),
        pending(ref="vault://synthetic/m24300-other-secret"),
    ):
        verdict=await inspector.inspect(pending=candidate)
        assert verdict.state=="UNKNOWN"
        assert verdict.real_payments_authorized is False


@pytest.mark.asyncio
async def test_bad_uuid_and_bad_revision_fail_before_db():
    db=FakeDatabase()
    reg=StagingSellerCASRegistry(db=db,enabled=True)
    inspector=StagingOAuthRecoveryInspector(registry=reg,enabled=True)
    for candidate in (pending(seller="²002"),pending(revision="../bad"),
                      pending(ref="token with spaces")):
        verdict=await inspector.inspect(pending=candidate)
        assert verdict.state=="UNKNOWN"
    assert db.calls==[]


@pytest.mark.asyncio
async def test_database_exception_and_unknown_status_preserve_revision():
    db=FakeDatabase()
    reg=StagingSellerCASRegistry(db=db,enabled=True)
    inspector=StagingOAuthRecoveryInspector(registry=reg,enabled=True)
    db.fail=True
    verdict=await inspector.inspect(pending=pending())
    assert verdict.state=="UNKNOWN" and not verdict.automatic_deletion_allowed
    db.fail=False
    db.state="CONNECTED"  # Not a valid status in contract.
    verdict=await inspector.inspect(pending=pending())
    assert verdict.state=="UNKNOWN"


@pytest.mark.asyncio
async def test_revoked_consent_does_not_reauthorize_historical_active_state():
    db=FakeDatabase();db.revoked=True;db.state="ACTIVE"
    reg=StagingSellerCASRegistry(db=db,enabled=True)
    verdict=await StagingOAuthRecoveryInspector(
        registry=reg,enabled=True
    ).inspect(pending=pending())
    assert verdict.state=="ACTIVE"
    assert verdict.next_step=="RETAIN_AND_RECHECK_CURRENT_CONSENT"
    assert verdict.merchant_connection_authorized is False


def test_sql_049_disposable_identity_and_read_only_contract():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    sql=(root/"staging_migrations/049_mp_oauth_revision_state_staging_only.sql").read_text()
    probe=(root/"ci_migrations/045_oauth_revision_state_worker_probe_ci_only.sql").read_text()
    chain=(root/"scripts/aistudio_staging_chain_ci.sh").read_text()
    adapter=(root/"app/mp_oauth_staging_cas_registry.py").read_text()
    recovery=(root/"app/mp_oauth_staging_reconciliation.py").read_text()
    for required in (
        "current_database()<>'frcaixinha_staging'",
        "frcaixinha.mp_oauth_staging_authorized",
        "session_user<>'frcaixinha_mp_oauth_worker'",
        "SECURITY DEFINER",
        "GRANT EXECUTE ON FUNCTION",
        "r.credential_ref=p_ref",
        "r.tenant_id=p_tenant",
        "r.actor_user_id=p_actor",
        "r.revision=p_revision",
    ):
        assert required in sql,required
    assert "M24300_OAUTH_REVISION_RECOVERY_SCOPE=PASS" in probe
    assert "M24300 DIRECT TABLE READ FORBIDDEN" in probe
    assert chain.index("049_mp_oauth_revision_state_staging_only.sql") < chain.index(
        "045_oauth_revision_state_worker_probe_ci_only.sql")
    assert chain.index("045_oauth_revision_state_worker_probe_ci_only.sql") < chain.index(
        "042_oauth_revocation_probe_ci_only.sql")
    assert "GITHUB_ACTIONS" in chain and "FRCAIXINHA_CI_ISOLATED" in chain
    assert 'PGPORT:-}" = "5432"' in chain
    assert "public.mp_staging_oauth_revision_state" in adapter
    assert "await self._registry.revision_status" in recovery
    assert "await self._registry.mark_failed" not in recovery
    assert ".cancel(" not in recovery and "delete" not in recovery.split("class StagingOAuthRecoveryInspector",1)[1].lower()


def test_migration_inventory_count_73_never_authorizes_termux_apply():
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    data=json.loads((root/"backend/migration_catalog_ai_studio.json").read_text())
    assert len(data["entries"])==73
    for filename in ("049_mp_oauth_revision_state_staging_only.sql",
                     "045_oauth_revision_state_worker_probe_ci_only.sql"):
        rows=[x for x in data["entries"] if x["source_path"].endswith(filename)]
        assert len(rows)==1
        assert rows[0]["do_not_apply_source_to_termux"] is True
