"""M38110–M38139: synthetic invitation/contract/notification binding regressions."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import pytest

from app.onboarding_invitation_notice_ci import (
    PendingMemberInvitationEvidence, invitation_notice_digest,
    inspect_pending_member_invitation_notice,
)
from app.notifications_policy import NoticeClaim, NoticeKind, NoticeRole
from app.pix_automation_contract import FinancialOperationBlocked

NOW=datetime(2026,11,11,12,tzinfo=timezone.utc)


def fixture():
    tenant,recipient,invite,doc=(uuid4() for _ in range(4))
    snapshot=PendingMemberInvitationEvidence(
        invitation_id=invite,tenant_id=tenant,recipient_user_id=recipient,
        required_document_id=doc,published_document_id=doc,
        required_document_sha256="a"*64,published_document_sha256="a"*64,
        target_role="TENANT_MEMBER",cycle_year=2027,invitation_revision=1,
        invitation_expires_at=NOW+timedelta(hours=2),
        observed_at=NOW,invitation_revoked=False,invitation_accepted=False,
        document_published=True,
    )
    notice=NoticeClaim(
        event_id=invite,event_kind=NoticeKind.INVITATION_ACCEPTANCE_PENDING,
        recipient_id=recipient,role=NoticeRole.TENANT_MEMBER,
        tenant_id=tenant,cycle_year=2027,occurred_at=NOW,
        authenticated_event_source=False,authenticated_recipient=False,
        tenant_membership_verified=False,
        source_reference_digest=invitation_notice_digest(snapshot),
    )
    return snapshot,notice


def test_consistent_synthetic_binding_is_redacted_and_never_deliverable():
    evidence,notice=fixture()
    result=inspect_pending_member_invitation_notice(evidence,notice)
    assert result.preview.event_kind is NoticeKind.INVITATION_ACCEPTANCE_PENDING
    assert result.preview.tenant_id==evidence.tenant_id
    assert result.preview.recipient_id==evidence.recipient_user_id
    assert result.preview.policy_only
    assert not result.preview.in_app_write_authorized
    assert not result.preview.external_send_authorized
    for field in (
        "source_database_authenticated","recipient_email_verified",
        "contract_consent_recorded","user_activated","inbox_written",
        "email_sent","push_sent","real_delivery_authorized",
        "production_authorized",
    ):
        assert getattr(result,field) is False


@pytest.mark.parametrize("field,replacement",[
    ("tenant_id",__import__("uuid").UUID(int=0)),
    ("recipient_user_id",__import__("uuid").UUID(int=0)),
    ("invitation_id",__import__("uuid").UUID(int=0)),
    ("required_document_id",uuid4()),
    ("published_document_id",uuid4()),
    ("required_document_sha256","b"*64),
    ("published_document_sha256","b"*64),
    ("required_document_sha256","A"*64),
    ("published_document_sha256","z"*64),
    ("required_document_sha256","a"*63),
    ("target_role","TENANT_ADMIN"),
    ("target_role","MASTER"),
    ("target_role",None),
    ("cycle_year",2019),
    ("cycle_year",True),
    ("invitation_revision",0),
    ("invitation_revision",False),
    ("invitation_revision",-1),
    ("invitation_revision","1"),
    ("invitation_expires_at",NOW),
    ("invitation_expires_at",NOW-timedelta(seconds=1)),
    ("observed_at",NOW.replace(tzinfo=None)),
    ("invitation_expires_at",NOW.replace(tzinfo=None)),
    ("invitation_revoked",True),
    ("invitation_accepted",True),
    ("document_published",False),
    ("document_published",1),
    ("invitation_revoked",0),
    ("invitation_accepted",None),
])
def test_bad_hypothetical_invitation_fails_closed(field,replacement):
    evidence,_=fixture()
    bad=replace(evidence,**{field:replacement})
    with pytest.raises(FinancialOperationBlocked):
        invitation_notice_digest(bad)


@pytest.mark.parametrize("field,replacement",[
    ("event_id",uuid4()),
    ("recipient_id",uuid4()),
    ("tenant_id",uuid4()),
    ("role",NoticeRole.MASTER),
    ("role",NoticeRole.TENANT_ADMIN),
    ("event_kind",NoticeKind.CONTRIBUTION_DUE_INFO),
    ("cycle_year",2028),
    ("source_reference_digest","b"*64),
    ("source_reference_digest","a"*64),
    ("source_reference_digest",None),
    ("authenticated_event_source",True),
    ("authenticated_recipient",True),
    ("tenant_membership_verified",True),
    ("occurred_at",NOW+timedelta(seconds=1)),
    ("occurred_at",NOW.replace(tzinfo=None)),
])
def test_notice_cannot_borrow_invitation_or_contract_bindings(field,replacement):
    evidence,notice=fixture()
    with pytest.raises(FinancialOperationBlocked):
        inspect_pending_member_invitation_notice(evidence,replace(notice,**{field:replacement}))


def test_timezone_changes_with_same_instant_are_valid():
    evidence,notice=fixture()
    shifted=notice.occurred_at.astimezone(timezone(timedelta(hours=-3)))
    assert inspect_pending_member_invitation_notice(
        evidence,replace(notice,occurred_at=shifted),
    ).preview.policy_only


@pytest.mark.parametrize("field,replacement",[
    ("invitation_revision",2),
    ("required_document_id",uuid4()),
    ("required_document_sha256","b"*64),
    ("recipient_user_id",uuid4()),
    ("tenant_id",uuid4()),
    ("invitation_id",uuid4()),
])
def test_digest_changes_with_version_identity_scope_and_revision(field,replacement):
    evidence,_=fixture()
    altered=replace(evidence,**{field:replacement})
    if field=="required_document_id":
        altered=replace(altered,published_document_id=replacement)
    if field=="required_document_sha256":
        altered=replace(altered,published_document_sha256=replacement)
    assert invitation_notice_digest(altered)!=invitation_notice_digest(evidence)


def test_digest_is_deterministic_and_excludes_sensitive_data():
    evidence,_=fixture()
    digest=invitation_notice_digest(evidence)
    assert len(digest)==64
    assert digest==invitation_notice_digest(evidence)
    assert "@" not in repr(evidence)
    assert "password" not in repr(evidence).lower()


def test_no_public_route_uses_synthetic_policy_or_sends():
    root=Path(__file__).resolve().parents[2]
    src=(root/"backend/app/onboarding_invitation_notice_ci.py").read_text()
    assert "inspect_notification_claim(notice)" in src
    assert "compare_digest(" in src
    for forbidden in (
        "INSERT INTO","UPDATE public.","DELETE FROM","smtplib",
        "psycopg.connect","asyncpg.connect","requests.post(",
        "submit_access_message(","FR_FINANCE_PIX_REAL",
    ):
        assert forbidden not in src
    for name in ("invitations.py","notifications.py","auth.py"):
        api=(root/"backend/app/routers"/name).read_text()
        assert "inspect_pending_member_invitation_notice" not in api


def test_mismatched_snapshot_type_never_enables_preview():
    _,notice=fixture()
    with pytest.raises(FinancialOperationBlocked):
        inspect_pending_member_invitation_notice(None,notice)
    with pytest.raises(FinancialOperationBlocked):
        inspect_pending_member_invitation_notice(object(),notice)
