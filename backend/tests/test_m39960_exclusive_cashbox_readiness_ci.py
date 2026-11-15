"""M39960 — session-bound financial VIEW only; no API writes or payouts."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_rls_db_connection
from app.dependencies import (
    AuthenticatedSession, get_current_session, require_master,
)
from app.exclusive_cashbox_review_readiness import (
    ReviewReadinessDenied, verify_review_readiness,
)
from app.exclusive_cashbox_provenance import (
    PLATFORM_MASTER, TENANT_ADMIN_OWN, TENANT_COLLECTIVE,
)

MASTER_ID=UUID("11111111-1111-4111-8111-111111111111")
ADMIN_ID=UUID("22222222-2222-4222-8222-222222222222")
OTHER_ID=UUID("33333333-3333-4333-8333-333333333333")
TENANT_A=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_B=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SESSION_ID=UUID("77777777-7777-4777-8777-777777777777")
MASTER_PATH="/api/v1/master/exclusive-cashbox/review-readiness"
ADMIN_PATH=f"/api/v1/tenants/{TENANT_A}/admin-exclusive-cashbox/review-readiness"
AT=datetime.now(timezone.utc)
_UNSET=object()


def session(role="TENANT_ADMIN", tenant=TENANT_A, actor=ADMIN_ID,
            *, origin="POSTGRES_TOKEN_HASH_REFRESH",
            refreshed_at=_UNSET, expires_at=_UNSET,
            sid=SESSION_ID, is_master=None):
    now=datetime.now(timezone.utc)
    if refreshed_at is _UNSET:
        refreshed_at=now
    if expires_at is _UNSET:
        expires_at=now+timedelta(minutes=15)
    if is_master is None:
        is_master=(role=="MASTER")
    return AuthenticatedSession(
        str(actor),role,str(tenant) if tenant is not None else None,
        "ci.invalid@example.test","CI test name",is_master,
        verified_session_id=str(sid) if sid is not None else None,
        verified_session_at=refreshed_at,
        verified_session_expires_at=expires_at,
        verification_source=origin,
    )


class SyntheticDB:
    def __init__(self,owner=ADMIN_ID):
        self.owner=owner
        self.queries=[]
    async def fetchval(self,sql,*args):
        self.queries.append((sql,args))
        assert sql=="SELECT admin_user_id FROM public.tenants WHERE id=$1 AND status='ATIVO'"
        assert args==(TENANT_A,)
        return self.owner


def setup(db=None,*,role="TENANT_ADMIN",tenant=TENANT_A,actor=ADMIN_ID,
          master_override=False,**sess_kwargs):
    db=db or SyntheticDB()
    obj=session(role,tenant,actor,**sess_kwargs)
    app.dependency_overrides[get_current_session]=lambda: obj
    app.dependency_overrides[get_rls_db_connection]=lambda: db
    if master_override:
        app.dependency_overrides[require_master]=lambda:obj
    else:
        def forbidden_master():
            raise HTTPException(status_code=403,detail="MASTER required")
        app.dependency_overrides[require_master]=forbidden_master
    return db


def teardown():
    app.dependency_overrides.clear()


def _assert_view_only(response, scope, tenant=None):
    assert response.status_code==200,response.text
    assert response.headers.get("cache-control")=="no-store"
    assert response.headers.get("pragma")=="no-cache"
    assert response.headers.get("vary")=="Authorization"
    p=response.json()
    assert set(p)=={
        "source","scope","tenant_id","state","session_bound",
        "owner_verified_for_view","document_authenticated",
        "independent_reviewers_verified","documentary_review_authorized",
        "bank_reconciled","journal_posted","payment_enabled","payout_enabled",
        "available_balance_cents",
    }
    assert p["source"]=="POSTGRES_TOKEN_HASH_REFRESH"
    assert p["scope"]==scope
    assert p["tenant_id"]==(str(tenant) if tenant else None)
    assert p["state"]=="SESSION_BOUND_VIEW_ONLY"
    assert p["session_bound"] is True
    assert p["owner_verified_for_view"] is bool(tenant)
    for key in ("document_authenticated","independent_reviewers_verified",
                "documentary_review_authorized","bank_reconciled",
                "journal_posted","payment_enabled","payout_enabled"):
        assert p[key] is False
    assert p["available_balance_cents"] is None
    assert not any(word in str(p).lower() for word in (
        "ci.invalid@example.test","77777777-7777",
        "password","token_hash","bearer","reviewer_id","user_id",
    ))


def test_verified_master_session_produces_metadata_without_ledger_query():
    db=SyntheticDB()
    setup(db,role="MASTER",tenant=None,actor=MASTER_ID,master_override=True)
    try:
        with TestClient(app) as client:
            resp=client.get(MASTER_PATH)
            post=client.post(MASTER_PATH)
        _assert_view_only(resp,"MASTER_PLATFORM_SAAS_ONLY")
        assert post.status_code==405
        assert db.queries==[]
    finally:
        teardown()


def test_verified_tenant_owner_only_one_select_and_no_synthetic_payment():
    db=SyntheticDB()
    setup(db)
    try:
        with TestClient(app) as client:
            resp=client.get(ADMIN_PATH)
            post=client.post(ADMIN_PATH)
        _assert_view_only(resp,"TENANT_ADMIN_OWN_REMUNERATION_ONLY",TENANT_A)
        assert post.status_code==405
        assert len(db.queries)==1
    finally:
        teardown()


@pytest.mark.parametrize("origin,sid,at,exp",[
    ("LEGACY_NO_SESSION_BINDING",SESSION_ID,AT,AT+timedelta(minutes=15)),
    ("FORGED_SOURCE",SESSION_ID,AT,AT+timedelta(minutes=15)),
    ("POSTGRES_TOKEN_HASH_REFRESH",None,AT,AT+timedelta(minutes=15)),
    ("POSTGRES_TOKEN_HASH_REFRESH",UUID(int=0),AT,AT+timedelta(minutes=15)),
    ("POSTGRES_TOKEN_HASH_REFRESH",SESSION_ID,None,AT+timedelta(minutes=15)),
    ("POSTGRES_TOKEN_HASH_REFRESH",SESSION_ID,AT,None),
    ("POSTGRES_TOKEN_HASH_REFRESH",SESSION_ID,AT-timedelta(minutes=6),AT+timedelta(minutes=10)),
    ("POSTGRES_TOKEN_HASH_REFRESH",SESSION_ID,AT+timedelta(days=1),AT+timedelta(days=1,minutes=15)),
    ("POSTGRES_TOKEN_HASH_REFRESH",SESSION_ID,AT,AT),
    ("POSTGRES_TOKEN_HASH_REFRESH",SESSION_ID,AT,AT+timedelta(minutes=31)),
    ("POSTGRES_TOKEN_HASH_REFRESH",SESSION_ID,AT.replace(tzinfo=None),AT+timedelta(minutes=15)),
])
def test_weak_expired_or_future_sessions_denied_without_owner_query(origin,sid,at,exp):
    db=SyntheticDB()
    setup(db,origin=origin,sid=sid,refreshed_at=at,expires_at=exp)
    try:
        with TestClient(app) as client:
            r=client.get(ADMIN_PATH)
        assert r.status_code==403,(origin,r.text)
        assert db.queries==[]
    finally:
        teardown()


@pytest.mark.parametrize("role,tenant,actor,is_master",[
    ("TENANT_ADMIN",TENANT_B,ADMIN_ID,False),
    ("TENANT_MEMBER",TENANT_A,ADMIN_ID,False),
    ("MASTER",None,MASTER_ID,True),
    ("TENANT_ADMIN",TENANT_A,ADMIN_ID,True),
    ("TENANT_ADMIN",None,ADMIN_ID,False),
    ("TENANT_ADMIN",UUID(int=0),ADMIN_ID,False),
])
def test_wrong_tenant_or_role_never_reaches_owner_sql(role,tenant,actor,is_master):
    db=SyntheticDB()
    setup(db,role=role,tenant=tenant,actor=actor,is_master=is_master)
    try:
        with TestClient(app) as client:
            r=client.get(ADMIN_PATH)
        assert r.status_code==403,(role,tenant,r.text)
        assert db.queries==[]
    finally:
        teardown()


def test_non_owner_denied_after_one_read_only_ownership_check():
    db=SyntheticDB(owner=OTHER_ID)
    setup(db)
    try:
        with TestClient(app) as client:
            r=client.get(ADMIN_PATH)
        assert r.status_code==403
        assert len(db.queries)==1
    finally:
        teardown()


def test_master_boundary_cannot_be_forged_by_tenant_or_legacy():
    for viewer in (
        dict(role="TENANT_MEMBER",tenant=TENANT_A,actor=ADMIN_ID),
        dict(role="TENANT_ADMIN",tenant=TENANT_A,actor=ADMIN_ID),
        dict(role="MASTER",tenant=TENANT_A,actor=MASTER_ID),
        dict(role="MASTER",tenant=None,actor=MASTER_ID,
             origin="LEGACY_NO_SESSION_BINDING"),
    ):
        db=SyntheticDB()
        setup(db,master_override=True,**viewer)
        try:
            with TestClient(app) as client:
                r=client.get(MASTER_PATH)
            assert r.status_code==403,viewer
            assert db.queries==[]
        finally:
            teardown()


def test_pure_gate_rejects_tenant_collective_and_stale_observation():
    now=datetime.now(timezone.utc)
    m=session("MASTER",None,MASTER_ID,refreshed_at=now,
              expires_at=now+timedelta(minutes=15))
    with pytest.raises(ReviewReadinessDenied):
        verify_review_readiness(m,requested_scope=TENANT_COLLECTIVE,
                                requested_tenant_id=None,observed_at=now)
    with pytest.raises(ReviewReadinessDenied):
        verify_review_readiness(m,requested_scope=PLATFORM_MASTER,
            requested_tenant_id=None,observed_at=now+timedelta(minutes=6))
    with pytest.raises(ReviewReadinessDenied):
        verify_review_readiness(m,requested_scope=PLATFORM_MASTER,
            requested_tenant_id=None,observed_at=datetime(2026,11,15,13,0))
    result=verify_review_readiness(m,requested_scope=PLATFORM_MASTER,
                                  requested_tenant_id=None,observed_at=now)
    assert result.session_bound is True
    assert result.independent_reviewer_verified is False
    assert result.documentary_review_authorized is False
    assert result.payment_enabled is False


def test_six_no_store_routes_and_no_mutations_or_untrusted_payload():
    routes={r.path:r.methods for r in app.routes if hasattr(r,"methods")}
    assert routes[MASTER_PATH]=={"GET"}
    assert routes["/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox/review-readiness"]=={"GET"}
    source=(Path(__file__).resolve().parents[1]/
            "app/routers/exclusive_cashboxes.py").read_text()
    assert source.count("_disallow_financial_caching(response)")==6
    assert "owner != UUID(session.user_id)" in source
    assert "get_rls_db_connection" in source
    assert "POSTGRES_TOKEN_HASH_REFRESH" in source
    for forbidden in ("INSERT INTO","UPDATE public.","DELETE FROM",
                      "asyncpg.connect(","pg_ctl","os.kill("):
        assert forbidden not in source
