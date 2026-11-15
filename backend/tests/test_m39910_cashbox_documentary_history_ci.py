"""M39910: GET-only documentary cashbox history; synthetic SQL (NO PG I/O)."""
from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import AuthenticatedSession, get_current_session, require_master
from app.database import get_rls_db_connection

MASTER_ID=UUID("11111111-1111-4111-8111-111111111111")
ADMIN_ID=UUID("22222222-2222-4222-8222-222222222222")
OTHER_ID=UUID("33333333-3333-4333-8333-333333333333")
TENANT_A=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_B=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
TIMESTAMP=datetime(2026,11,14,17,30,tzinfo=timezone.utc)
MASTER_PATH="/api/v1/master/exclusive-cashbox/history"
ADMIN_PATH=f"/api/v1/tenants/{TENANT_A}/admin-exclusive-cashbox/history"


def session(role="TENANT_ADMIN", tenant=TENANT_A, actor=ADMIN_ID):
    return AuthenticatedSession(
        str(MASTER_ID if role=="MASTER" else actor),role,
        str(tenant) if tenant else None,
        "synthetic@example.invalid","Synthetic",role=="MASTER",
    )


class SyntheticDB:
    def __init__(self, owner=ADMIN_ID, payment_state="APPROVED", clock=TIMESTAMP,
                 extra_entries=0):
        self.owner=owner
        self.payment_state=payment_state
        self.clock=clock
        self.extra_entries=extra_entries
        self.statements=[]
    async def fetchval(self,sql,*args):
        self.statements.append((sql,args))
        assert sql.startswith("SELECT ")
        assert sql.startswith("SELECT admin_user_id FROM public.tenants")
        assert args==(TENANT_A,)
        return self.owner
    async def fetch(self,sql,*args):
        self.statements.append((sql,args))
        assert sql.startswith("SELECT ") and "LIMIT 10" in sql
        assert "FOR UPDATE" not in sql
        assert not any(w in sql.lower() for w in ("insert ","update ","delete ",
            "cpf","password","external_reference","amount_cents","collector_id"))
        if "saas_payment_intents" in sql:
            assert args==()
            rows=[{"id":UUID("a0000000-0000-4000-8000-000000000001"),
                   "created_at":self.clock,"status":self.payment_state}]
            return rows+[rows[0]]*self.extra_entries
        if "saas_subscription_preparations" in sql:
            assert args==()
            return [{"id":UUID("a0000000-0000-4000-8000-000000000002"),
                     "created_at":self.clock-timedelta(minutes=1),
                     "status":"PENDING_PAYMENT"}]
        if "public.ledger_transactions" in sql:
            assert args==(TENANT_A,)
            return [{"id":UUID("a0000000-0000-4000-8000-000000000003"),
                     "created_at":self.clock}]
        raise AssertionError(sql)


def use(db,role="TENANT_ADMIN",tenant=TENANT_A,actor=ADMIN_ID,allow_master=False):
    app.dependency_overrides[get_rls_db_connection]=lambda:db
    app.dependency_overrides[get_current_session]=lambda:session(role,tenant,actor)
    if allow_master:
        app.dependency_overrides[require_master]=lambda:session("MASTER",None,MASTER_ID)
    else:
        def deny():
            raise HTTPException(403,"Master only")
        app.dependency_overrides[require_master]=deny


def clear():
    app.dependency_overrides.clear()


def test_routes_are_get_only_and_no_cache():
    routes={r.path:r.methods for r in app.routes if hasattr(r,"methods")}
    assert routes[MASTER_PATH]=={"GET"}
    assert routes["/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox/history"]=={"GET"}
    db=SyntheticDB()
    use(db,allow_master=True)
    try:
        with TestClient(app) as client:
            resp=client.get(MASTER_PATH)
        assert resp.status_code==200,resp.text
        assert resp.headers["cache-control"]=="private, no-store, max-age=0"
        assert resp.headers["vary"]=="Authorization"
        assert resp.headers["pragma"]=="no-cache"
        val=resp.json()
        assert val["scope"]=="MASTER_PLATFORM_SAAS_ONLY"
        assert val["tenant_id"] is None
        assert val["source"]=="POSTGRESQL_RLS"
        assert val["available_balance_cents"] is None
        assert val["cash_movement_verified"] is False
        assert val["transfer_enabled"] is False
        assert val["status"]=="DOCUMENTARY_ONLY_NOT_RECONCILED"
        assert [r["category"] for r in val["entries"]]==["SAAS_INTENT","SAAS_PREPARATION"]
        assert val["entries"][0]["state"]=="APPROVED"
        assert val["entries"][0]["settlement_verified"] is False
        assert all(r["amount_cents"] is None for r in val["entries"])
        assert all("tenant_id" not in r and "expected_amount_cents" not in r
                   for r in val["entries"])
        assert len(db.statements)==2
        assert all("ledger" not in sql for sql,_ in db.statements)
    finally:
        clear()


def test_admin_only_collective_reference_no_own_salary():
    db=SyntheticDB()
    use(db)
    try:
        with TestClient(app) as client:
            resp=client.get(ADMIN_PATH)
        assert resp.status_code==200,resp.text
        val=resp.json()
        assert val["scope"]=="TENANT_ADMIN_COLLECTIVE_REFERENCE_ONLY"
        assert val["tenant_id"]==str(TENANT_A)
        assert [r["category"] for r in val["entries"]]==["TENANT_COLLECTIVE_LEDGER"]
        assert val["entries"][0]["state"]=="RECORDED_NOT_REMUNERATION"
        assert val["entries"][0]["amount_cents"] is None
        assert val["entries"][0]["settlement_verified"] is False
        assert val["available_balance_cents"] is None
        assert val["cash_movement_verified"] is False
        assert val["transfer_enabled"] is False
        assert len(db.statements)==2
        assert db.statements[1][1]==(TENANT_A,)
        assert all("saas" not in sql for sql,_ in db.statements)
    finally:
        clear()


def test_wrong_role_or_tenant_denied_before_financial_event_query():
    for role,tenant,actor,owner in (
        ("TENANT_ADMIN",TENANT_B,ADMIN_ID,ADMIN_ID),
        ("TENANT_MEMBER",TENANT_A,ADMIN_ID,ADMIN_ID),
        ("MASTER",None,MASTER_ID,ADMIN_ID),
        ("TENANT_ADMIN",TENANT_A,ADMIN_ID,OTHER_ID),
    ):
        db=SyntheticDB(owner=owner)
        use(db,role,tenant,actor)
        try:
            with TestClient(app) as client:
                resp=client.get(ADMIN_PATH)
            assert resp.status_code==403,(role,tenant,resp.text)
            assert not any("ledger_transactions" in sql for sql,_ in db.statements)
        finally:
            clear()


def test_member_never_receives_master_history():
    db=SyntheticDB()
    use(db,role="TENANT_MEMBER")
    try:
        with TestClient(app) as client:
            resp=client.get(MASTER_PATH)
        assert resp.status_code==403
        assert db.statements==[]
    finally:
        clear()


def test_invalid_or_naive_status_clock_and_excess_records_fail_closed():
    for params in (
        {"payment_state":"UNKNOWN"},
        {"clock":datetime(2026,11,14,17,30)},
        {"extra_entries":10},
    ):
        db=SyntheticDB(**params)
        use(db,allow_master=True)
        try:
            with TestClient(app) as client:
                resp=client.get(MASTER_PATH)
            assert resp.status_code==503,(params,resp.text)
        finally:
            clear()


def test_get_not_post_and_no_database_mutation_source():
    from pathlib import Path
    code=(Path(__file__).resolve().parents[1]/"app/routers/exclusive_cashboxes.py").read_text()
    assert "@master_router.get(\"/exclusive-cashbox/history\")" in code
    assert "@tenant_router.get(\"/admin-exclusive-cashbox/history\")" in code
    assert "LIMIT 10" in code and "_disallow_financial_caching(response)" in code
    assert "cash_movement_verified\": False" in code
    assert "available_balance_cents\": None" in code
    assert not any(s in code for s in ("INSERT INTO","UPDATE public.","DELETE FROM",
                                     "asyncpg.connect(","pg_ctl","os.kill("))
