"""FR Finance M39090: exclusive cashboxes are role-scoped read-only evidence.

TestClient overrides all DB/auth dependencies. No connection, writes,
migration, real finance, Pix, webhook or identity operation is performed.
"""
from uuid import UUID
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_rls_db_connection
from app.dependencies import AuthenticatedSession, get_current_session, require_master

MASTER_ID = UUID("11111111-1111-4111-8111-111111111111")
ADMIN_ID = UUID("22222222-2222-4222-8222-222222222222")
TENANT_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
MASTER_PATH = "/api/v1/master/exclusive-cashbox"
TENANT_PATH = f"/api/v1/tenants/{TENANT_A}/admin-exclusive-cashbox"


class SyntheticDB:
    def __init__(self, owner=ADMIN_ID):
        self.owner=owner
        self.statements=[]
    async def fetchval(self, sql, *args):
        self.statements.append((sql,args))
        assert sql.startswith("SELECT "), "No mutating SQL permitted"
        assert "FOR UPDATE" not in sql
        assert not any(token in sql.lower() for token in (
            "insert ", "update ", "delete ", "public.users",
            "public.memberships", "cpf", "password_hash", "pg_notify",
        ))
        if "public.saas_payment_intents" in sql:
            assert args==()
            return 3
        if "public.saas_subscription_preparations" in sql:
            assert args==()
            return 2
        if "SELECT admin_user_id FROM public.tenants" in sql:
            assert args==(TENANT_A,)
            return self.owner
        if "public.ledger_transactions" in sql:
            assert args==(TENANT_A,)
            return 7
        raise AssertionError("Unexpected SQL: "+sql)


def _session(role, tenant):
    return AuthenticatedSession(
        str(MASTER_ID if role=="MASTER" else ADMIN_ID),
        role, str(tenant) if tenant else None,
        "synthetic@example.invalid", "Synthetic", role=="MASTER",
    )


def _use(db, role="TENANT_ADMIN", tenant=TENANT_A, master_allowed=False):
    app.dependency_overrides[get_rls_db_connection]=lambda:db
    app.dependency_overrides[get_current_session]=lambda:_session(role,tenant)
    if master_allowed:
        app.dependency_overrides[require_master]=lambda:_session("MASTER",None)
    else:
        def deny_master():
            raise HTTPException(403, "Master only")
        app.dependency_overrides[require_master]=deny_master


def _clear():
    app.dependency_overrides.clear()


def test_cashbox_routes_registered_are_get_only():
    paths={r.path:{m for m in r.methods} for r in app.routes if hasattr(r,"methods")}
    assert paths[MASTER_PATH]=={"GET"}
    assert paths["/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox"]=={"GET"}


def test_master_sees_only_saas_evidence_not_tenant_balance():
    db=SyntheticDB()
    _use(db,master_allowed=True)
    try:
        with TestClient(app) as c:
            response=c.get(MASTER_PATH)
        assert response.status_code==200,response.text
        v=response.json()
        assert v["scope"]=="MASTER_PLATFORM_SAAS_ONLY"
        assert v["source"]=="POSTGRESQL_RLS"
        assert v["tenant_id"] is None
        assert v["payment_intents_count"]==3
        assert v["subscription_preparations_count"]==2
        assert v["settled_balance_cents"] is None
        assert v["transfer_enabled"] is False
        assert v["real_payments_enabled"] is False
        assert v["bank_reconciled"] is False
        assert len(db.statements)==2
        assert all("ledger" not in sql and "contributions" not in sql
                   for sql,_ in db.statements)
        assert not any(x in v for x in ("balance", "cash_balance", "members", "admin_share"))
    finally:
        _clear()


def test_tenant_owner_sees_only_own_evidence_not_imaginary_share():
    db=SyntheticDB()
    _use(db)
    try:
        with TestClient(app) as c:
            response=c.get(TENANT_PATH)
        assert response.status_code==200,response.text
        v=response.json()
        assert v["scope"]=="TENANT_ADMIN_OWN_REMUNERATION_ONLY"
        assert v["tenant_id"]==str(TENANT_A)
        assert v["administrator_profit_share_pct"]=="15.00"
        assert v["members_profit_share_pct"]=="85.00"
        assert v["ledger_transactions_count"]==7
        assert v["settled_balance_cents"] is None
        assert v["bank_reconciled"] is False
        assert v["closing_authorized"] is False
        assert v["transfer_enabled"] is False
        assert db.statements[1][1]==(TENANT_A,)
        assert all("saas" not in sql for sql,_ in db.statements)
    finally:
        _clear()


def test_cross_tenant_member_master_and_nonowner_denied_before_ledger():
    for role,tenant,owner in (
        ("TENANT_ADMIN",TENANT_B,ADMIN_ID),
        ("TENANT_MEMBER",TENANT_A,ADMIN_ID),
        ("MASTER",None,ADMIN_ID),
        ("TENANT_ADMIN",TENANT_A,MASTER_ID),
    ):
        db=SyntheticDB(owner=owner)
        _use(db,role,tenant)
        try:
            with TestClient(app) as c:
                result=c.get(TENANT_PATH)
            assert result.status_code==403,(role,tenant,result.text)
            assert all("ledger_transactions" not in sql for sql,_ in db.statements)
        finally:
            _clear()


def test_member_cannot_query_master_and_unknown_tenant_is_invalid():
    db=SyntheticDB()
    _use(db,role="TENANT_MEMBER")
    try:
        with TestClient(app) as c:
            response=c.get(MASTER_PATH)
            bad_uuid=c.get("/api/v1/tenants/not-a-uuid/admin-exclusive-cashbox")
            unsupported=c.post(TENANT_PATH)
        assert response.status_code==403
        assert bad_uuid.status_code==422
        assert unsupported.status_code==405
        assert db.statements==[]
    finally:
        _clear()


def test_invalid_counts_fail_closed_without_claiming_balance():
    for value in (-1,1.2,None,True,1000000001):
        db=SyntheticDB()
        async def invalid_count(sql,*args):
            db.statements.append((sql,args))
            return value
        db.fetchval=invalid_count
        _use(db,master_allowed=True)
        try:
            with TestClient(app) as c:
                result=c.get(MASTER_PATH)
            assert result.status_code==503
        finally:
            _clear()
