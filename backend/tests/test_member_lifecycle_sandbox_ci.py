"""M761+: isolamento e fluxos de solicitação, sem gravação real no CI unitário."""
from datetime import datetime,timezone
from uuid import UUID
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies import AuthenticatedSession
from app.routers.member_lifecycle_sandbox import (
 LifecycleSandboxRequest, my_member_lifecycle_requests,
 administrative_member_lifecycle_queue,
 request_voluntary_exit_sandbox,
 request_delinquency_review_sandbox,
)

T=UUID(int=1001)
B=UUID(int=2002)
CID=UUID(int=3003)
MEM=UUID(int=4004)
U=UUID(int=5005)
R=UUID(int=6006)
WHEN=datetime(2027,5,1,tzinfo=timezone.utc)


def session(role="TENANT_MEMBER",tenant=T):
    return AuthenticatedSession(str(U),role,
        str(tenant) if tenant else None,
        "test@example.invalid","Synthetic",role=="MASTER")


def body(ident=R):
    return LifecycleSandboxRequest(
        idempotency_key=ident,policy_reference="CI-REVISION-2027"
    )


def request_row(kind="VOLUNTARY_EXIT"):
    return dict(id=R,tenant_id=T,cycle_id=CID,membership_id=MEM,
        requested_by_user_id=U,request_kind=kind,
        policy_reference="CI-REVISION-2027",
        status="PENDING_REVIEW",requested_at=WHEN)


class FakeDB:
    def __init__(self,rows=()):
        self.rows=list(rows)
        self.calls=[]
        self.lastkind='VOLUNTARY_EXIT'
    async def fetchrow(self,sql,*args):
        self.calls.append(("fetchrow",sql,args))
        if "FROM public.cycles" in sql:
            return {"id":CID,"status":"ABERTO"}
        if "FROM public.memberships" in sql:
            return {"id":MEM}
        if "FROM public.member_lifecycle_requests" in sql:
            return request_row(self.lastkind)
        raise AssertionError(sql)
    async def fetch(self,sql,*args):
        self.calls.append(("fetch",sql,args))
        return self.rows
    async def fetchval(self,sql,*args):
        self.calls.append(("fetchval",sql,args))
        assert "lifecycle_submit_request_sandbox" in sql
        assert args[0]==T and args[1]==CID
        self.lastkind=args[3]
        return R
    async def execute(self,*args):
        raise AssertionError("A API não usa escrita direta na tabela")


@pytest.mark.asyncio
async def test_member_gets_only_own_requests():
    db=FakeDB([request_row()])
    r=await my_member_lifecycle_requests(T,2027,session(),db)
    assert r.scope=="SELF_READ_ONLY"
    assert len(r.items)==1
    assert r.items[0].status=="PENDING_REVIEW"
    assert r.items[0].sandbox_only
    assert not r.items[0].financial_effect_applied
    assert not r.items[0].payment_authorized
    assert "requested_by_user_id=$3" in db.calls[-1][1]


@pytest.mark.asyncio
async def test_admin_queue_scope():
    db=FakeDB([request_row("DELINQUENCY_REVIEW")])
    r=await administrative_member_lifecycle_queue(
        T,2027,session("TENANT_ADMIN"),db)
    assert r.scope=="TENANT_ADMIN_READ_ONLY"
    assert len(r.items)==1
    assert r.items[0].request_kind=="DELINQUENCY_REVIEW"


@pytest.mark.asyncio
async def test_member_cannot_view_admin_queue_and_admin_cannot_impersonate_member():
    for fn,actor in (
        (administrative_member_lifecycle_queue,session()),
        (my_member_lifecycle_requests,session("TENANT_ADMIN")),
    ):
        db=FakeDB()
        with pytest.raises(HTTPException) as err:
            await fn(T,2027,actor,db)
        assert err.value.status_code==403
        assert db.calls==[]


@pytest.mark.asyncio
async def test_master_and_cross_tenant_not_allowed_for_any_lifecycle_read():
    for actor in (session("MASTER",None),session("TENANT_MEMBER",B),
                  session("TENANT_ADMIN",B)):
        db=FakeDB()
        with pytest.raises(HTTPException) as err:
            await my_member_lifecycle_requests(T,2027,actor,db)
        assert err.value.status_code==403
        assert db.calls==[]


@pytest.mark.asyncio
async def test_default_sandbox_write_protection(monkeypatch):
    monkeypatch.delenv("FRCAIXINHA_LIFECYCLE_SANDBOX",raising=False)
    db=FakeDB()
    with pytest.raises(HTTPException) as err:
        await request_voluntary_exit_sandbox(T,2027,body(),session(),db)
    assert err.value.status_code==503
    assert db.calls==[]


@pytest.mark.asyncio
async def test_production_write_always_blocked_even_with_flag(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT","production")
    monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1")
    db=FakeDB()
    with pytest.raises(HTTPException) as err:
        await request_delinquency_review_sandbox(
            T,2027,MEM,body(),session("TENANT_ADMIN"),db)
    assert err.value.status_code==503
    assert db.calls==[]


@pytest.mark.asyncio
async def test_valid_sandbox_member_self_exit_request(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT","development")
    monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1")
    db=FakeDB()
    r=await request_voluntary_exit_sandbox(T,2027,body(),session(),db)
    assert r.request_kind=="VOLUNTARY_EXIT"
    assert r.status=="PENDING_REVIEW"
    assert not r.member_status_changed and not r.profit_rights_modified
    assert not r.bank_reconciled and not r.payment_authorized
    vals=[x for x in db.calls if x[0]=="fetchval"]
    assert len(vals)==1
    assert vals[0][2][2]==MEM and vals[0][2][3]=="VOLUNTARY_EXIT"


@pytest.mark.asyncio
async def test_valid_sandbox_admin_reviewer(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT","development")
    monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1")
    db=FakeDB()
    r=await request_delinquency_review_sandbox(
        T,2027,MEM,body(),session("TENANT_ADMIN"),db)
    assert r.request_kind=="DELINQUENCY_REVIEW"
    assert db.calls[1][2][3]=="DELINQUENCY_REVIEW"
    assert not r.financial_effect_applied


@pytest.mark.asyncio
async def test_member_cannot_create_admin_review_and_admin_cannot_create_member_exit(monkeypatch):
    monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1")
    monkeypatch.setenv("ENVIRONMENT","development")
    for fn,actor in (
        (lambda db:request_delinquency_review_sandbox(
            T,2027,MEM,body(),session(),db),session()),
        (lambda db:request_voluntary_exit_sandbox(
            T,2027,body(),session("TENANT_ADMIN"),db),session("TENANT_ADMIN")),
    ):
        db=FakeDB()
        with pytest.raises(HTTPException) as err:
            await fn(db)
        assert err.value.status_code==403 and db.calls==[]


@pytest.mark.parametrize("ref",["","12345","a" * 121,"é"*10,"unsafe path","../../../../../../"])
def test_invalid_policy_reference_rejected(ref):
    with pytest.raises(ValidationError):
        LifecycleSandboxRequest(idempotency_key=R,policy_reference=ref)


@pytest.mark.parametrize("kind",range(121))
def test_121_unique_idempotency_keys_do_not_create_financial_authorization(kind):
    request=LifecycleSandboxRequest(
       idempotency_key=UUID(int=kind+1),
       policy_reference="CI-REVISION-2027",
    )
    assert request.idempotency_key.int==kind+1
    assert not hasattr(request,"amount_to_refund")
    assert not hasattr(request,"admin_override")




@pytest.mark.asyncio
async def test_unmigrated_database_get_returns_explicit_503():
    import asyncpg
    class NoMigration(FakeDB):
        async def fetch(self,sql,*args):
            raise asyncpg.UndefinedTableError("relation not found")
    with pytest.raises(HTTPException) as exc:
        await my_member_lifecycle_requests(T,2027,session(),NoMigration())
    assert exc.value.status_code==503
    assert "migration 028" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_unmigrated_database_write_returns_explicit_503(monkeypatch):
    import asyncpg
    monkeypatch.setenv("ENVIRONMENT","homologation")
    monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1")
    class NoFunction(FakeDB):
        async def fetchval(self,sql,*args):
            raise asyncpg.UndefinedFunctionError("function missing")
    with pytest.raises(HTTPException) as exc:
        await request_voluntary_exit_sandbox(
            T,2027,body(),session(),NoFunction()
        )
    assert exc.value.status_code==503
    assert "banco" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_sql_conflicting_policy_is_409_not_production_approval(monkeypatch):
    import asyncpg
    monkeypatch.setenv("ENVIRONMENT","homologation")
    monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1")
    class Conflict(FakeDB):
        async def fetchval(self,sql,*args):
            raise asyncpg.UniqueViolationError("conflicting policy")
    with pytest.raises(HTTPException) as exc:
        await request_delinquency_review_sandbox(
            T,2027,MEM,body(),session("TENANT_ADMIN"),Conflict()
        )
    assert exc.value.status_code==409


def test_route_methods_cannot_update_member_status_or_cash():
    from app.main import app
    routes=[r for r in app.routes if "/member-lifecycle/" in getattr(r,"path","")]
    assert len(routes)==4
    methods=set().union(*(r.methods for r in routes))
    assert methods=={"GET","POST"}
    assert not any("PATCH" in r.methods or "DELETE" in r.methods for r in routes)
