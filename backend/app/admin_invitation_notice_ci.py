"""M38140-M38169: offline review of an administrative invitation notice.

Preview only: source claims are not trusted DB/IdP/MFA evidence. Does not
send, store, approve, authorize onboarding or activate accounts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from hmac import compare_digest
import json
import re
from uuid import UUID

from .notifications_policy import (
    NoticeClaim, NoticeKind, NoticeRole, inspect_notification_claim,
)
from .onboarding_invitation_notice_ci import PendingInvitationNoticePreview
from .pix_automation_contract import FinancialOperationBlocked

_DOMAIN = "FR_FINANCE_M38140_ADMIN_INVITATION_REVIEW_CI_ONLY_V1"


@dataclass(frozen=True, kw_only=True)
class PendingAdminInvitationReviewEvidence:
    invitation_id: UUID
    tenant_id: UUID
    recipient_user_id: UUID
    inviter_id: UUID
    inviter_role: str
    inviter_is_master: bool
    inviter_tenant_id: UUID | None
    reviewer_id: UUID
    reviewer_tenant_id: UUID
    reviewer_approved_claimed: bool
    master_mfa_claimed: bool
    expected_revision: int
    observed_revision: int
    target_role: str
    required_document_id: UUID
    published_document_id: UUID
    required_document_sha256: str
    published_document_sha256: str
    document_published: bool
    cycle_year: int
    invitation_expires_at: datetime
    observed_at: datetime
    invitation_revoked: bool
    invitation_accepted: bool


def _uuid(value: object) -> bool:
    return type(value) is UUID and value.int != 0


def _date(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() is not None)


def admin_invitation_notice_digest(
    evidence: PendingAdminInvitationReviewEvidence,
) -> str:
    """Synthetic correlation only: SHA-256 is NOT a signature."""
    e=evidence
    if (
        type(e) is not PendingAdminInvitationReviewEvidence
        or any(not _uuid(v) for v in (
            e.invitation_id,e.tenant_id,e.recipient_user_id,e.inviter_id,
            e.reviewer_id,e.reviewer_tenant_id,e.required_document_id,
            e.published_document_id
        ))
        or e.inviter_role != "MASTER" or type(e.inviter_role) is not str
        or e.inviter_tenant_id is not None
        or e.inviter_is_master is not True
        or e.master_mfa_claimed is not True
        or e.reviewer_approved_claimed is not True
        or e.reviewer_id in (e.inviter_id,e.recipient_user_id)
        or e.inviter_id == e.recipient_user_id
        or e.reviewer_tenant_id != e.tenant_id
        or type(e.expected_revision) is not int or e.expected_revision < 1
        or type(e.observed_revision) is not int
        or e.observed_revision != e.expected_revision
        or type(e.target_role) is not str or e.target_role != "TENANT_ADMIN"
        or e.required_document_id != e.published_document_id
        or type(e.required_document_sha256) is not str
        or type(e.published_document_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}",e.required_document_sha256) is None
        or re.fullmatch(r"[0-9a-f]{64}",e.published_document_sha256) is None
        or not compare_digest(
            e.required_document_sha256,e.published_document_sha256)
        or e.document_published is not True
        or type(e.cycle_year) is not int or not 2020 <= e.cycle_year <= 2100
        or not _date(e.invitation_expires_at) or not _date(e.observed_at)
        or e.invitation_expires_at <= e.observed_at
        or e.invitation_revoked is not False or e.invitation_accepted is not False
    ):
        raise FinancialOperationBlocked("M38140_ADMIN_INVITATION_REVIEW_DENIED")
    payload={
        "domain":_DOMAIN,
        "invitation":str(e.invitation_id),
        "tenant":str(e.tenant_id),
        "recipient":str(e.recipient_user_id),
        "inviter":str(e.inviter_id),
        "reviewer":str(e.reviewer_id),
        "revision":e.observed_revision,
        "role":e.target_role,
        "document":str(e.required_document_id),
        "sha256":e.required_document_sha256,
        "cycle_year":e.cycle_year,
        "expires_at":e.invitation_expires_at.astimezone(timezone.utc).isoformat(),
    }
    canonical=json.dumps(
        payload,sort_keys=True,ensure_ascii=True,separators=(",",":"),
    ).encode("ascii")
    return sha256(canonical).hexdigest()


def inspect_pending_admin_invitation_notice(
    evidence: PendingAdminInvitationReviewEvidence,
    notice: NoticeClaim,
) -> PendingInvitationNoticePreview:
    """No inbox permission even when all hypothetical claims match."""
    digest=admin_invitation_notice_digest(evidence)
    if (
        type(notice) is not NoticeClaim
        or notice.event_kind is not NoticeKind.ADMIN_INVITATION_REVIEW_PENDING
        or notice.role is not NoticeRole.TENANT_ADMIN
        or notice.event_id != evidence.invitation_id
        or notice.recipient_id != evidence.recipient_user_id
        or notice.tenant_id != evidence.tenant_id
        or notice.cycle_year != evidence.cycle_year
        or type(notice.source_reference_digest) is not str
        or not compare_digest(notice.source_reference_digest,digest)
        or not _date(notice.occurred_at)
        or notice.occurred_at.astimezone(timezone.utc)
           != evidence.observed_at.astimezone(timezone.utc)
        or notice.authenticated_event_source is not False
        or notice.authenticated_recipient is not False
        or notice.tenant_membership_verified is not False
    ):
        raise FinancialOperationBlocked("M38140_ADMIN_NOTICE_SCOPE_MISMATCH")
    return PendingInvitationNoticePreview(
        preview=inspect_notification_claim(notice),
    )
