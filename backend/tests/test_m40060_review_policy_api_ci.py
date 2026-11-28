"""M40060: ONLY read-only authentication and policy-gap API contract.

All sessions and DB results in these tests are synthetic dependency overrides.
No original PostgreSQL, external providers, migrations, writes or human
reviewer-signatures are accessed or attested.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from app.main import app
from app.database import get_rls_db_connection
from app.dependencies import AuthenticatedSession, get_current_session
from app.exclusive_cashbox_provenance import EVENT_SCOPE, PLATFORM_MASTER, TENANT_ADMIN_OWN

MASTER=UUID("11111111-1111-4111-8111-111111111111")
ADMIN=UUID("22222222-2222-4222-8222-222222222222")
OTHER=UUID("33333333-3333-4333-8333-333333333333")
SID=UUID("77777777-7777-4777-8777-777777777777")
A=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
B=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
MASTER_PATH="/api/v1/master/exclusive-cashbox/review-policy-gaps"
TENANT_PATH=f"/api/v1/tenants/{A}/admin-exclusive-cashbox/review-policy-gaps"


def session(role="TENANT_ADMIN", tenant=A, actor=ADMIN, *,
            source="POSTGRES_TOKEN_HASH_REFRESH", at=None, expiry=None,
            is_master=None):
    now=datetime.now(timezone.utc)
    if at is None:
        at=now
    if expiry is None:
        expiry=now+timedelta(minutes=15)
    if is_master is None:
        is_master=(role=="MASTER")
    return AuthenticatedSession(
        str(actor),role,str(tenant) if tenant is not None else None,
        "synthetic@example.invalid","Synthetic",is_master,
        verified_session_id=str(SID),
        verified_session_at=at,
        verified_session_expires_at=expiry,
        verification_source=source,
    )


class ReadOnlyOwnerDB:
    def __init__(self, owner=ADMIN):
        self.owner=owner
        self.queries=[]
    async def fetchval(self, sql, *args):
        self.queries.append((sql,args))
        assert sql=="SELECT admin_user_id FROM public.tenants WHERE id=$1 AND status='ATIVO'"
        assert args==(A,)
        return self.owner


def _use(principal, db):
    app.dependency_overrides[get_current_session]=lambda:principal
    app.dependency_overrides[get_rls_db_connection]=lambda:db


def _clear():
    app.dependency_overrides.clear()


def _assert_blocked(response, scope, tenant):
    assert response.status_code==200,response.text
    assert "no-store" in response.headers.get("cache-control","")
    assert response.headers.get("pragma")=="no-cache"
    assert response.headers.get("vary")=="Authorization"
    body=response.json()
    assert body["source"]=="SERVER_SESSION_READONLY_SCOPE"
    assert body["scope"]==scope
    assert body["tenant_id"]==(str(tenant) if tenant else None)
    assert body["state"]=="POLICY_AND_MANDATE_UNRATIFIED"
    assert body["session_bound_for_view"] is True
    assert body["owner_verified_for_view"] is (tenant is not None)
    assert body["draft_event_types_not_authorized"]==sorted(
        k for k, value in EVENT_SCOPE.items() if value==scope)
    assert len(body["outstanding_gates"])>=8
    assert body["available_balance_cents"] is None
    for key in (
        "policy_ratified","reviewer_grants_verified",
        "two_person_approval_verified","effective_revocation_verified",
        "real_review_approved","bank_reconciled","journal_posted",
        "payout_enabled","payment_enabled","pix_enabled",
        "production_authorized",
    ):
        assert body[key] is False
    for fragment in (
        "user_id","session_id","email","token","password","cpf",
        "reviewer_id","signature","payment_intent","amount_cents",
    ):
        assert fragment not in body
    assert "synthetic@example.invalid" not in str(body)


def test_real_main_registers_only_two_get_policy_gap_routes():
    routes={r.path:r.methods for r in app.routes if hasattr(r,"methods")}
    assert routes[MASTER_PATH]=={"GET"}
    assert routes[
        "/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox/review-policy-gaps"
    ]=={"GET"}
    db=ReadOnlyOwnerDB()
    _use(session(),db)
    try:
        with TestClient(app) as client:
            assert client.post(TENANT_PATH).status_code==405
            assert client.post(MASTER_PATH).status_code==405
    finally:
        _clear()
    assert db.queries==[]


def test_master_saas_metadata_only_and_no_db_queries():
    db=ReadOnlyOwnerDB()
    _use(session("MASTER",None,MASTER),db)
    try:
        with TestClient(app) as client:
            response=client.get(MASTER_PATH)
            tenant_attempt=client.get(TENANT_PATH)
        _assert_blocked(response,PLATFORM_MASTER,None)
        assert tenant_attempt.status_code==403
        assert db.queries==[]
    finally:
        _clear()


def test_tenant_admin_only_sees_own_draft_gaps_with_one_rls_select():
    db=ReadOnlyOwnerDB()
    _use(session(),db)
    try:
        with TestClient(app) as client:
            response=client.get(TENANT_PATH)
            master_attempt=client.get(MASTER_PATH)
        _assert_blocked(response,TENANT_ADMIN_OWN,A)
        assert master_attempt.status_code==403
        assert len(db.queries)==1
    finally:
        _clear()


def test_other_tenant_member_legacy_master_or_stale_session_is_denied():
    now=datetime.now(timezone.utc)
    principals=[
        session("TENANT_ADMIN",B),
        session("TENANT_MEMBER",A),
        session("MASTER",None,MASTER),
        session("TENANT_ADMIN",A,source="LEGACY_NO_SESSION_BINDING"),
        session("TENANT_ADMIN",A,source="FORGED_SOURCE"),
        session("TENANT_ADMIN",A,at=now-timedelta(minutes=6)),
        session("TENANT_ADMIN",A,at=now+timedelta(seconds=30)),
        session("TENANT_ADMIN",A,expiry=now-timedelta(seconds=1)),
        session("TENANT_ADMIN",A,is_master=True),
    ]
    for principal in principals:
        db=ReadOnlyOwnerDB()
        _use(principal,db)
        try:
            with TestClient(app) as client:
                response=client.get(TENANT_PATH)
            assert response.status_code==403,(principal.role,response.text)
            assert db.queries==[]
        finally:
            _clear()


def test_nonowner_and_unknown_owner_are_denied_without_financial_access():
    for claimed_owner in (OTHER,None,str(ADMIN),UUID(int=0)):
        db=ReadOnlyOwnerDB(claimed_owner)
        _use(session(),db)
        try:
            with TestClient(app) as client:
                response=client.get(TENANT_PATH)
            assert response.status_code==403,response.text
            assert len(db.queries)==1
        finally:
            _clear()



def test_asyncpg_compatible_uuid_subtype_is_accepted_without_relaxing_identity():
    # A real asyncpg UUID can be a subclass rather than exactly uuid.UUID.
    # A client-provided string must still fail the type check (covered above).
    class AsyncpgUUIDShape(UUID):
        pass

    db=ReadOnlyOwnerDB(AsyncpgUUIDShape(str(ADMIN)))
    _use(session(),db)
    try:
        with TestClient(app) as client:
            response=client.get(TENANT_PATH)
        _assert_blocked(response,TENANT_ADMIN_OWN,A)
        assert len(db.queries)==1
    finally:
        _clear()


def test_unauthenticated_requests_deny_before_db_or_return_unavailable():
    _clear()
    with TestClient(app) as client:
        assert client.get(MASTER_PATH).status_code==401
        assert client.get(TENANT_PATH).status_code==401


def test_no_approval_api_secret_or_money_paths_added():
    root=Path(__file__).resolve().parents[2]
    src=(root/"backend/app/routers/exclusive_cashbox_review_gaps.py").read_text()
    main=(root/"backend/app/main.py").read_text()
    workflow=(root/".github/workflows/frfinance-m40060-review-gaps-ci.yml").read_text()
    assert "app.include_router(_review_policy_gaps.master_router" in main
    assert "app.include_router(_review_policy_gaps.tenant_router" in main
    assert 'Depends(require_master)' in src
    assert 'Depends(get_current_session)' in src
    assert 'Depends(get_rls_db_connection)' in src
    assert "verify_review_readiness(" in src
    assert "owner != actor_id" in src
    assert "include_in_schema=False" in src
    assert "pix_enabled" in src
    for forbidden in (
        "@master_router.post","@tenant_router.post",
        "INSERT INTO","UPDATE public.","DELETE FROM","FOR UPDATE",
        "asyncpg.connect(","psycopg.connect(","httpx.",
        "requests.","create_payment(","commit(","session.email",
        "verified_session_id", "password_hash",
    ):
        assert forbidden not in src
    assert "PIX_REAL: 'OFF'" in workflow
    assert "PAGAMENTOS_REAIS: 'OFF'" in workflow
    assert "ATIVACAO_REAL: 'OFF'" in workflow
    assert "m40060_review_policy_api_ci.py" in workflow or "test_m40060_review_policy_api_ci.py" in workflow
