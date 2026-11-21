"""M2040: segurança das rotas de leitura CI sem banco, sem rede, sem Pix."""
from datetime import datetime, timezone
from uuid import UUID
import pytest

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.dependencies import AuthenticatedSession
from app.main import app
from app.routers.sandbox_evidence_ci import (
    read_my_sandbox_evidence, read_admin_sandbox_evidence, MAX_PAGE,
)

A=UUID("00000000-0000-4000-8000-0000000000a1")
B=UUID("00000000-0000-4000-8000-0000000000b1")
U=UUID("00000000-0000-4000-8000-000000000001")
M=UUID("00000000-0000-4000-8000-000000000002")


def identity(role="TENANT_MEMBER",tenant=A):
    return AuthenticatedSession(str(U),role,
        str(tenant) if tenant else None,"ci@example.invalid",
        "Pessoa Sintetica",role=="MASTER")


def event(n):
    return dict(
        event_id=UUID(int=100+n),event_seq=n,membership_id=M,
        provider_payment_id="98765",collector_id="2002",
        external_reference=f"tenant:{A}:contribution-1",
        event_kind="APPROVED_FIXTURE",amount_cents=15000,
        recorded_at=datetime(2027,1,10,12,tzinfo=timezone.utc))


class FakeDB:
    def __init__(self,enabled=True,rows=None,member=M):
        self.enabled=enabled
        self.rows=rows if rows is not None else [event(3),event(2),event(1)]
        self.member=member
        self.calls=[]
    async def fetchval(self,sql,*args):
        self.calls.append("fetchval")
        assert "current_database()" in sql
        return self.enabled
    async def fetchrow(self,sql,*args):
        self.calls.append("fetchrow")
        assert "public.memberships" in sql
        return {"id":self.member} if self.member else None
    async def fetch(self,sql,*args):
        self.calls.append("fetch")
        assert "public.mp_sandbox_evidence_events" in sql
        assert "event_seq<$3::bigint" in sql
        assert args[-1] <= MAX_PAGE + 1
        before=args[2]
        data=[r for r in self.rows if before is None or r["event_seq"] < before]
        return data[:args[-1]]
    async def execute(self,*args):
        raise AssertionError("Endpoint de leitura nao pode fazer DML")


@pytest.mark.asyncio
async def test_admin_and_member_page_without_financial_effects():
    db=FakeDB()
    first=await read_my_sandbox_evidence(
        A,2,None,identity(),db)
    assert first.has_more and first.next_before_seq==2
    assert [x.event_seq for x in first.events]==[3,2]
    later=await read_my_sandbox_evidence(
        A,2,first.next_before_seq,identity(),db)
    assert [x.event_seq for x in later.events]==[1]
    assert not later.has_more
    assert first.synthetic_only is True
    assert first.bank_reconciled is False
    assert first.real_payments_enabled is False
    assert first.payout_authorized is False
    a=await read_admin_sandbox_evidence(
        A,M,2,None,identity("TENANT_ADMIN"),FakeDB())
    assert a.scope=="TENANT_ADMIN_READ_ONLY_SYNTHETIC"
    assert len(a.events)==2
    assert all(row.bank_reconciled is False for row in a.events)


@pytest.mark.asyncio
@pytest.mark.parametrize("role,tenant",[
    ("MASTER",None),
    ("TENANT_ADMIN",A),
    ("TENANT_MEMBER",B),
    ("TENANT_ADMIN",B),
])
async def test_self_endpoint_denies_wrong_role_or_tenant_before_sql(role,tenant):
    db=FakeDB()
    with pytest.raises(HTTPException) as x:
        await read_my_sandbox_evidence(A,25,None,identity(role,tenant),db)
    assert x.value.status_code==403
    assert not db.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("role,tenant",[
    ("MASTER",None),
    ("TENANT_MEMBER",A),
    ("TENANT_MEMBER",B),
    ("TENANT_ADMIN",B),
])
async def test_admin_endpoint_denies_wrong_role_or_tenant_before_sql(role,tenant):
    db=FakeDB()
    with pytest.raises(HTTPException) as x:
        await read_admin_sandbox_evidence(
            A,M,25,None,identity(role,tenant),db)
    assert x.value.status_code==403
    assert not db.calls


@pytest.mark.asyncio
async def test_unavailable_ci_db_fails_closed():
    for fn,params in (
        (read_my_sandbox_evidence,(A,25,None,identity(),FakeDB(False))),
        (read_admin_sandbox_evidence,(A,M,25,None,
                                     identity("TENANT_ADMIN"),FakeDB(False))),
    ):
        with pytest.raises(HTTPException) as x:
            await fn(*params)
        assert x.value.status_code==503


def test_m2040_health_flags_and_default_routes_are_disabled():
    client=TestClient(app)
    r=client.get("/api/health/features/m2040")
    assert r.status_code==200
    assert r.headers["Cache-Control"]=="no-store"
    payload=r.json()
    assert payload["contract"]=="AI_STUDIO_M2040_CI_SANDBOX_PERSISTENCE_V1"
    assert payload["workstream"]=="AI_STUDIO"
    assert payload["synthetic_read_routes_registered"] is False
    for key in ("provider_get_connected","oauth_connect_active","real_webhooks_active",
                "bank_reconciled","financial_effect_applied","ledger_written",
                "financial_closing_authorized","payout_authorized",
                "real_payments_enabled","runtime_git_sha_verified"):
        assert payload[key] is False
    assert all("/sandbox-evidence/" not in path for path in client.get("/openapi.json").json()["paths"])


@pytest.mark.parametrize("page_size",range(1,101))
def test_100_page_values_preserve_limit_and_immutable_contract(page_size):
    from app.routers.sandbox_evidence_ci import SandboxEvidencePage
    p=SandboxEvidencePage(
        tenant_id=A,membership_id=M,scope="SELF_READ_ONLY_SYNTHETIC",
        events=[],page_size=page_size,has_more=False,next_before_seq=None)
    assert p.bank_reconciled is False
    assert p.financial_effect_applied is False
    assert p.closing_authorized is False
    assert p.payout_authorized is False
