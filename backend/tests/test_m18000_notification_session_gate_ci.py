"""M18000 session shape, API authentication, no fake read actions."""
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import AuthenticatedSession,get_current_session
from app.notification_session_gate import (
    CONTRACT,validate_notification_session_shape
)
from app.notifications_policy import NoticeRole
from app.pix_automation_contract import FinancialOperationBlocked

T="ffffffff-0000-4000-8000-000000000011"
U="ffffffff-0000-4000-8000-000000000001"
ID="eeeeeeee-0000-4000-8000-000000000001"

def session(role="TENANT_MEMBER",tenant=T,master=False,user=U):
    return AuthenticatedSession(user,role,tenant,
            "test@example.invalid","Synthetic",master)

def test_session_scope_types_and_no_authority():
    for role,tenant,master in (
        ("MASTER",None,True),
        ("TENANT_ADMIN",T,False),
        ("TENANT_MEMBER",T,False),
    ):
        g=validate_notification_session_shape(session(role,tenant,master))
        assert g.scope.user_id==UUID(U)
        assert g.scope.tenant_id==(UUID(tenant) if tenant else None)
        assert g.scope.role==NoticeRole(role)
        assert g.authenticated_by_dependency is False
        assert not g.inbox_source_authorized
        assert not g.notification_read_allowed
        assert not g.marking_read_allowed
        assert not g.financial_effect_allowed
    assert CONTRACT=="AI_STUDIO_M18000_SESSION_SCOPE_NO_REAL_INBOX_V1"

@pytest.mark.parametrize("role,tenant,master,user",[
    ("MASTER",T,True,U),("MASTER",None,False,U),
    ("TENANT_ADMIN",None,False,U),
    ("TENANT_MEMBER",T,True,U),
    ("TENANT_ADMIN",T,False,"00000000-0000-0000-0000-000000000000"),
    ("TENANT_ADMIN",T,False,"BAD"),
    ("TENANT_ADMIN",T,False,U.upper()),
    ("TENANT_MEMBER",T.upper(),False,U),
    ("USER",T,False,U),
    ("TENANT_MEMBER","00000000-0000-0000-0000-000000000000",False,U),
])
def test_bad_session_context_rejected(role,tenant,master,user):
    with pytest.raises(FinancialOperationBlocked):
        validate_notification_session_shape(session(role,tenant,master,user))

def test_no_auth_http401_and_no_success_for_mark_read():
    with TestClient(app) as client:
        for method,path in (
            ("get","/api/v1/notifications/readiness"),
            ("post",f"/api/v1/notifications/{ID}/read"),
            ("get","/api/v1/notifications"),
        ):
            r=getattr(client,method)(path)
            assert r.status_code==401,(method,path,r.status_code)

@pytest.mark.parametrize("role,tenant,master",[
    ("MASTER",None,True),
    ("TENANT_ADMIN",T,False),
    ("TENANT_MEMBER",T,False),
])
def test_readiness_never_claims_live_inbox(role,tenant,master):
    async def valid():
        return session(role,tenant,master)
    app.dependency_overrides[get_current_session]=valid
    try:
        with TestClient(app) as client:
            r=client.get("/api/v1/notifications/readiness",headers={
                "X-User-Id":"ffffffff-0000-4000-8000-000000000099",
                "X-Tenant-Id":"ffffffff-0000-4000-8000-000000000099",
                "X-Role":"MASTER",
            })
            assert r.status_code==200
            d=r.json()
            assert d["role"]==role
            assert d["session_dependency_checked"] is True
            for key in (
                "production_event_authentication","inbox_schema_deployed",
                "inbox_api_connected","unread_count_authoritative",
                "mark_read_active","external_delivery_active",
                "bank_reconciled","real_payments_enabled",
            ):
                assert d[key] is False,key
            assert d.get("recipient_id") is None
            assert d.get("tenant_id") is None
            assert client.get("/api/v1/notifications").status_code==503
            post=client.post(f"/api/v1/notifications/{ID}/read")
            assert post.status_code==503
            assert "bloqueada" in post.json()["detail"]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.parametrize("role,tenant,master",[
    ("MASTER",T,True),
    ("MASTER",None,False),
    ("TENANT_MEMBER",None,False),
    ("TENANT_ADMIN",T,True),
])
def test_wrong_context_http403(role,tenant,master):
    async def invalid():
        return session(role,tenant,master)
    app.dependency_overrides[get_current_session]=invalid
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/notifications/readiness").status_code==403
            assert client.post(f"/api/v1/notifications/{ID}/read").status_code==403
    finally:
        app.dependency_overrides.clear()

def test_health_m18000_truthful():
    with TestClient(app) as client:
        r=client.get("/api/health/features/m18000")
    assert r.status_code==200
    d=r.json()
    assert d["contract"]=="AI_STUDIO_M18000_NOTIFICATION_CI_SESSION_GATE_V1"
    assert d["workstream"]=="AI_STUDIO"
    for k in (
        "session_scope_guard_prepared","ci_disposable_reader_prepared",
        "read_receipt_ci_only_prepared","ci_keyset_cursor_integrated",
        "route_readiness_requires_auth",
    ):
        assert d[k] is True,k
    for k in (
        "app_uses_real_inbox","real_inbox_api_connected",
        "real_read_receipt_active","production_event_source_authenticated",
        "local_migration_applied","oci_staging_deployed",
        "in_app_delivery_active","email_send_active","push_send_active",
        "whatsapp_send_active","real_payments_enabled",
        "bank_reconciled","ledger_written",
        "financial_closing_authorized","payout_authorized",
    ):
        assert d[k] is False,k
