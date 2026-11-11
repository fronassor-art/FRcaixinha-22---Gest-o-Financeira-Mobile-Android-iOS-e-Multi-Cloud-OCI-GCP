"""M15000: pure notification policy, privacy, no delivery, and auth routes."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import AuthenticatedSession, get_current_session
from app.notifications_policy import (
    CONTRACT, NoticeKind, NoticeChannel, NoticeRole,
    NoticeClaim, NoticePreferencesClaim,
    inspect_notification_claim, inspect_notification_batch,
)
from app.pix_automation_contract import FinancialOperationBlocked

T=UUID("00000000-0000-4000-8000-0000000000a1")
B=UUID("00000000-0000-4000-8000-0000000000b1")
U=UUID("00000000-0000-4000-8000-000000000001")
V=UUID("00000000-0000-4000-8000-000000000002")
E=UUID("00000000-0000-4000-8000-000000000003")
TIME=datetime(2026,11,5,12,tzinfo=timezone.utc)


def notice(kind=NoticeKind.CONTRIBUTION_DUE_INFO,role=NoticeRole.TENANT_MEMBER,
           tenant=T,recipient=U,event=E):
    return NoticeClaim(
        event_id=event,event_kind=kind,recipient_id=recipient,role=role,
        tenant_id=tenant,cycle_year=2027 if tenant else None,
        occurred_at=TIME,authenticated_event_source=False,
        authenticated_recipient=False,tenant_membership_verified=False,
        source_reference_digest="a"*64,
    )


def test_all_notice_types_have_careful_templates_and_no_money_authority():
    for kind in NoticeKind:
        role={
            NoticeKind.LICENSE_REGULARIZATION:NoticeRole.TENANT_ADMIN,
            NoticeKind.LICENSE_REVERSED_REVIEW:NoticeRole.TENANT_ADMIN,
            NoticeKind.SUPPORT_ACCESS_ALERT:NoticeRole.TENANT_ADMIN,
            NoticeKind.ADMIN_INVITATION_REVIEW_PENDING:NoticeRole.TENANT_ADMIN,
            NoticeKind.CLOSING_REVIEW_PENDING:NoticeRole.TENANT_ADMIN,
            NoticeKind.SECURITY_SESSION_ALERT:NoticeRole.MASTER,
        }.get(kind,NoticeRole.TENANT_MEMBER)
        c=notice(kind,role,None if role is NoticeRole.MASTER else T)
        p=inspect_notification_claim(c)
        assert len(p.fingerprint)==64
        assert p.title and p.message
        assert p.policy_only
        for flag in (
            p.in_app_write_authorized,p.external_send_authorized,
            p.payment_confirmed,p.bank_reconciled,p.ledger_written,
            p.payout_authorized,
        ):
            assert flag is False


def test_master_cannot_receive_a_member_financial_notice():
    with pytest.raises(FinancialOperationBlocked):
        inspect_notification_claim(
            notice(NoticeKind.CONTRIBUTION_DUE_INFO,NoticeRole.MASTER,None)
        )


def test_member_cannot_receive_license_or_support_admin_notice():
    for kind in (NoticeKind.LICENSE_REGULARIZATION,
                 NoticeKind.SUPPORT_ACCESS_ALERT,
                 NoticeKind.CLOSING_REVIEW_PENDING):
        with pytest.raises(FinancialOperationBlocked):
            inspect_notification_claim(notice(kind))


def test_master_security_notice_must_be_platform_scoped():
    c=notice(NoticeKind.SECURITY_SESSION_ALERT,NoticeRole.MASTER,None)
    assert inspect_notification_claim(c).tenant_id is None
    with pytest.raises(FinancialOperationBlocked):
        inspect_notification_claim(replace(c,tenant_id=T))


@pytest.mark.parametrize("bad",[
    {"recipient_id":UUID(int=0)},
    {"event_id":UUID(int=0)},
    {"tenant_id":B,"cycle_year":None},
    {"role":"TENANT_MEMBER"},
    {"event_kind":"FAKE"},
    {"occurred_at":TIME.replace(tzinfo=None)},
    {"occurred_at":"2026-11-05T12:00:00"},
    {"source_reference_digest":"Invalid!"},
    {"authenticated_event_source":1},
    {"authenticated_recipient":"true"},
    {"tenant_membership_verified":None},
    {"cycle_year":2010},
    {"cycle_year":True},
])
def test_invalid_notice_fails_closed(bad):
    with pytest.raises(FinancialOperationBlocked):
        inspect_notification_claim(replace(notice(),**bad))


@pytest.mark.parametrize("channel",[NoticeChannel.EMAIL,NoticeChannel.PUSH,NoticeChannel.WHATSAPP])
def test_external_requires_all_three_claims_but_never_sends(channel):
    original=NoticePreferencesClaim(U,channel,True,True,True)
    p=inspect_notification_claim(notice(),preference=original)
    assert p.external_send_authorized is False
    for field in ("opt_in","address_verified","purpose_documented"):
        with pytest.raises(FinancialOperationBlocked):
            inspect_notification_claim(
                notice(),preference=replace(original,**{field:False})
            )


def test_cross_recipient_preference_cannot_be_reused():
    with pytest.raises(FinancialOperationBlocked):
        inspect_notification_claim(
            notice(),preference=NoticePreferencesClaim(V,NoticeChannel.PUSH,True,True,True)
        )


def test_in_app_preference_is_only_a_preview():
    p=inspect_notification_claim(
        notice(),preference=NoticePreferencesClaim(U,NoticeChannel.IN_APP,False,False,False)
    )
    assert p.in_app_write_authorized is False


def test_no_recipient_email_phone_cpf_or_address_in_preview():
    p=inspect_notification_claim(notice())
    assert "@" not in repr(p)
    assert "CPF" not in p.title.upper()
    assert "CPF" not in p.message.upper()


def test_timestamps_normalize_utc_for_deterministic_dedup():
    c=notice()
    a=inspect_notification_claim(c)
    b=inspect_notification_claim(
        replace(c,occurred_at=c.occurred_at.astimezone(timezone(timedelta(hours=-3))))
    )
    assert a.fingerprint==b.fingerprint


def test_batch_exact_replay_does_not_persist_or_deliver():
    c=notice()
    r=inspect_notification_batch((c,c),tenant_id=T)
    assert r.candidate_count==1
    assert r.exact_replays_suppressed==1
    assert r.delivered is False
    assert r.persisted is False
    assert r.external_send_authorized is False


def test_batch_conflicting_replay_rejected():
    c=notice()
    with pytest.raises(FinancialOperationBlocked):
        inspect_notification_batch(
            (c,replace(c,source_reference_digest="b"*64)),tenant_id=T,
        )


def test_batch_wrong_tenant_rejected():
    c=notice()
    with pytest.raises(FinancialOperationBlocked):
        inspect_notification_batch((c,),tenant_id=B)
    with pytest.raises(FinancialOperationBlocked):
        inspect_notification_batch((c,replace(c,tenant_id=B)),tenant_id=T)


def test_batch_master_platform_only():
    c=notice(NoticeKind.SECURITY_SESSION_ALERT,NoticeRole.MASTER,None)
    assert inspect_notification_batch((c,),tenant_id=None).candidate_count==1
    with pytest.raises(FinancialOperationBlocked):
        inspect_notification_batch((c,),tenant_id=T)


def test_batch_limit_and_invalid_container():
    c=notice()
    with pytest.raises(FinancialOperationBlocked):
        inspect_notification_batch((c,)*101,tenant_id=T)
    for bad in ([],{},None,"",object()):
        with pytest.raises(FinancialOperationBlocked):
            inspect_notification_batch(bad,tenant_id=T)


def test_health_route_m15000_is_not_dispatch():
    with TestClient(app) as client:
        r=client.get("/api/health/features/m15000")
        assert r.status_code==200
        d=r.json()
        assert d["workstream"]=="AI_STUDIO"
        assert d["contract"]=="AI_STUDIO_M15000_NOTIFICATION_POLICY_OFFLINE_V1"
        assert d["policy_contract"]==CONTRACT
        for key in (
            "notification_kinds_validated","recipient_tenant_role_binding_policy",
            "external_channel_consent_policy","deterministic_dedupe_preview",
            "notification_center_ui_available",
        ):
            assert d[key] is True,key
        for key in (
            "durable_inbox_persisted","in_app_dispatch_active","email_send_active",
            "push_send_active","whatsapp_send_active","schedule_approved",
            "real_payments_enabled","bank_reconciled","ledger_written",
            "payout_authorized","financial_closing_authorized",
        ):
            assert d[key] is False,key


def test_inbox_cannot_fake_empty_without_auth_or_db():
    with TestClient(app) as client:
        assert client.get("/api/v1/notifications").status_code==401


@pytest.mark.parametrize("role,tenant,is_master",[
    ("MASTER",None,True),
    ("TENANT_ADMIN",str(T),False),
    ("TENANT_MEMBER",str(T),False),
])
def test_auth_context_has_capabilities_but_inbox_503(role,tenant,is_master):
    async def fake_session():
        return AuthenticatedSession(str(U),role,tenant,"u@example.invalid","Teste",is_master)
    app.dependency_overrides[get_current_session]=fake_session
    try:
        with TestClient(app) as client:
            r=client.get("/api/v1/notifications/capabilities")
            assert r.status_code==200
            d=r.json()
            assert d["role"]==role
            assert d["inbox_read_available"] is False
            assert d["in_app_delivery_active"] is False
            assert d["whatsapp_delivery_active"] is False
            assert client.get("/api/v1/notifications").status_code==503
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("role,tenant,is_master",[
    ("MASTER",None,False),
    ("MASTER",str(T),True),
    ("TENANT_MEMBER",None,False),
    ("OUTRO",str(T),False),
])
def test_wrong_active_context_denied(role,tenant,is_master):
    async def fake_session():
        return AuthenticatedSession(str(U),role,tenant,"u@example.invalid","Teste",is_master)
    app.dependency_overrides[get_current_session]=fake_session
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/notifications/capabilities").status_code==403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("role",["TENANT_ADMIN","TENANT_MEMBER"])
def test_master_identity_with_valid_tenant_role_is_not_rejected_by_shape(role):
    """The same person may be Master and hold independent tenant memberships."""
    async def fake_session():
        return AuthenticatedSession(str(U),role,str(T),"u@example.invalid","Teste",True)
    app.dependency_overrides[get_current_session]=fake_session
    try:
        with TestClient(app) as client:
            r=client.get("/api/v1/notifications/capabilities")
            assert r.status_code==200
            assert r.json()["role"]==role
            assert r.json()["bank_reconciled"] is False
            assert r.json()["real_payments_enabled"] is False
            # No private Postgres local: shaping a session cannot produce an inbox.
            assert r.json()["inbox_schema_connected"] is False
    finally:
        app.dependency_overrides.clear()
