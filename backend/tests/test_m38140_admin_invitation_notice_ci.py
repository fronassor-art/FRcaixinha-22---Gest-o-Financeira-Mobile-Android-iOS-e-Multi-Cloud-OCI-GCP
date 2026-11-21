"""M38140-M38169: immutable, undeliverable admin invitation review."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import UUID,uuid4
import pytest

from app.admin_invitation_notice_ci import (
    PendingAdminInvitationReviewEvidence,
    admin_invitation_notice_digest,inspect_pending_admin_invitation_notice,
)
from app.notifications_policy import (
    NoticeClaim,NoticeKind,NoticeRole,inspect_notification_claim,
)
from app.onboarding_invitation_notice_ci import PendingInvitationNoticePreview
from app.pix_automation_contract import FinancialOperationBlocked

NOW=datetime(2026,11,11,13,tzinfo=timezone.utc)


def fixture():
    tenant,recipient,inviter,reviewer,invitation,document=(
        uuid4() for _ in range(6)
    )
    evidence=PendingAdminInvitationReviewEvidence(
        invitation_id=invitation,tenant_id=tenant,recipient_user_id=recipient,
        inviter_id=inviter,inviter_role="MASTER",inviter_is_master=True,
        inviter_tenant_id=None,reviewer_id=reviewer,
        reviewer_tenant_id=tenant,reviewer_approved_claimed=True,
        master_mfa_claimed=True,expected_revision=3,observed_revision=3,
        target_role="TENANT_ADMIN",required_document_id=document,
        published_document_id=document,required_document_sha256="a"*64,
        published_document_sha256="a"*64,document_published=True,
        cycle_year=2027,invitation_expires_at=NOW+timedelta(hours=3),
        observed_at=NOW,invitation_revoked=False,invitation_accepted=False,
    )
    notice=NoticeClaim(
        event_id=invitation,event_kind=NoticeKind.ADMIN_INVITATION_REVIEW_PENDING,
        recipient_id=recipient,role=NoticeRole.TENANT_ADMIN,tenant_id=tenant,
        cycle_year=2027,occurred_at=NOW,
        authenticated_event_source=False,authenticated_recipient=False,
        tenant_membership_verified=False,
        source_reference_digest=admin_invitation_notice_digest(evidence),
    )
    return evidence,notice


def test_admin_candidate_preview_cannot_authorize_anything():
    e,n=fixture()
    result=inspect_pending_admin_invitation_notice(e,n)
    assert type(result) is PendingInvitationNoticePreview
    assert result.preview.role is NoticeRole.TENANT_ADMIN
    assert result.preview.event_kind is NoticeKind.ADMIN_INVITATION_REVIEW_PENDING
    assert result.preview.recipient_id==e.recipient_user_id
    assert result.preview.tenant_id==e.tenant_id
    assert "independente" in result.preview.message
    assert result.preview.policy_only is True
    assert not result.preview.in_app_write_authorized
    assert not result.preview.external_send_authorized
    for key in ("source_database_authenticated","recipient_email_verified",
                "contract_consent_recorded","user_activated","inbox_written",
                "email_sent","push_sent","real_delivery_authorized",
                "production_authorized"):
        assert getattr(result,key) is False


@pytest.mark.parametrize("field,bad",[
    ("tenant_id",UUID(int=0)),
    ("recipient_user_id",UUID(int=0)),
    ("inviter_id",UUID(int=0)),
    ("reviewer_id",UUID(int=0)),
    ("invitation_id",UUID(int=0)),
    ("required_document_id",UUID(int=0)),
    ("published_document_id",UUID(int=0)),
    ("reviewer_tenant_id",UUID(int=0)),
    ("inviter_role","TENANT_ADMIN"),
    ("inviter_role","TENANT_MEMBER"),
    ("inviter_role",None),
    ("inviter_is_master",False),
    ("inviter_is_master",1),
    ("inviter_tenant_id",uuid4()),
    ("master_mfa_claimed",False),
    ("master_mfa_claimed","yes"),
    ("reviewer_approved_claimed",False),
    ("reviewer_approved_claimed",None),
    ("reviewer_tenant_id",uuid4()),
    ("expected_revision",0),
    ("expected_revision",False),
    ("expected_revision",5),
    ("observed_revision",False),
    ("observed_revision",-1),
    ("observed_revision","3"),
    ("target_role","TENANT_MEMBER"),
    ("target_role","MASTER"),
    ("required_document_id",uuid4()),
    ("published_document_id",uuid4()),
    ("required_document_sha256","b"*64),
    ("published_document_sha256","b"*64),
    ("required_document_sha256","A"*64),
    ("published_document_sha256","z"*64),
    ("document_published",False),
    ("document_published",1),
    ("cycle_year",True),
    ("cycle_year",2019),
    ("invitation_expires_at",NOW),
    ("invitation_expires_at",NOW-timedelta(seconds=1)),
    ("invitation_expires_at",NOW.replace(tzinfo=None)),
    ("observed_at",NOW.replace(tzinfo=None)),
    ("invitation_revoked",True),
    ("invitation_revoked",None),
    ("invitation_accepted",True),
    ("invitation_accepted",1),
])
def test_untrusted_admin_evidence_denied(field,bad):
    e,_=fixture()
    with pytest.raises(FinancialOperationBlocked):
        admin_invitation_notice_digest(replace(e,**{field:bad}))


@pytest.mark.parametrize("field,bad",[
    ("event_id",uuid4()),
    ("recipient_id",uuid4()),
    ("tenant_id",uuid4()),
    ("role",NoticeRole.TENANT_MEMBER),
    ("role",NoticeRole.MASTER),
    ("event_kind",NoticeKind.INVITATION_ACCEPTANCE_PENDING),
    ("event_kind",NoticeKind.SECURITY_SESSION_ALERT),
    ("cycle_year",2028),
    ("source_reference_digest","b"*64),
    ("source_reference_digest",None),
    ("authenticated_event_source",True),
    ("authenticated_recipient",True),
    ("tenant_membership_verified",True),
    ("occurred_at",NOW+timedelta(seconds=1)),
    ("occurred_at",NOW.replace(tzinfo=None)),
])
def test_admin_notice_must_be_bound_to_exact_review(field,bad):
    e,n=fixture()
    with pytest.raises(FinancialOperationBlocked):
        inspect_pending_admin_invitation_notice(e,replace(n,**{field:bad}))


def test_self_invite_and_self_approval_denied():
    e,_=fixture()
    for changes in (
        {"recipient_user_id":e.inviter_id},
        {"reviewer_id":e.inviter_id},
        {"reviewer_id":e.recipient_user_id},
    ):
        with pytest.raises(FinancialOperationBlocked):
            admin_invitation_notice_digest(replace(e,**changes))


def test_no_member_or_master_can_receive_admin_notice_as_is():
    e,n=fixture()
    for role in (NoticeRole.TENANT_MEMBER,NoticeRole.MASTER):
        with pytest.raises(FinancialOperationBlocked):
            inspect_notification_claim(replace(n,role=role))


def test_digest_version_independent_approval_and_tenant_scoped():
    e,n=fixture()
    first=admin_invitation_notice_digest(e)
    assert len(first)==64
    assert admin_invitation_notice_digest(e)==first
    switched_tenant=uuid4()
    alternatives=(
        {"observed_revision":4,"expected_revision":4},
        {"recipient_user_id":uuid4()},
        {"tenant_id":switched_tenant,"reviewer_tenant_id":switched_tenant},
        {"reviewer_id":uuid4()},
        {"inviter_id":uuid4()},
        {"required_document_sha256":"b"*64,"published_document_sha256":"b"*64},
    )
    for change in alternatives:
        # Each changed attribute must materially affect the correlation.
        assert admin_invitation_notice_digest(replace(e,**change)) != first


def test_timezone_equivalent_utc_instant_does_not_split_notice():
    e,n=fixture()
    shift=NOW.astimezone(timezone(timedelta(hours=-3)))
    assert inspect_pending_admin_invitation_notice(
        e,replace(n,occurred_at=shift),
    ).preview.policy_only


def test_public_routers_still_have_no_new_authority():
    root=Path(__file__).resolve().parents[2]
    module=(root/"backend/app/admin_invitation_notice_ci.py").read_text()
    for forbidden in (
        "INSERT INTO","UPDATE public.","DELETE FROM",
        "smtplib","requests.post(","asyncpg.connect",
        "psycopg.connect","submit_access_message(",
    ):
        assert forbidden not in module
    for name in ("invitations.py","notifications.py","auth.py"):
        router=(root/"backend/app/routers"/name).read_text()
        assert "inspect_pending_admin_invitation_notice" not in router
    assert "FR_FINANCE_M38140_ADMIN_INVITATION_REVIEW_CI_ONLY_V1" in module


def test_none_and_wrong_evidence_type_never_pass():
    _,n=fixture()
    for bad in (None,False,{},object()):
        with pytest.raises(FinancialOperationBlocked):
            inspect_pending_admin_invitation_notice(bad,n)
