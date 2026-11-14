"""M38110-M38139: preview-only binding of invitation, document and notice.

Synthetic snapshots are NOT independently authenticated. No invitation, email,
contract consent, member admission, inbox write, RLS permission or activation
is granted; this file has zero IO. Real worker integration is prohibited.
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
    NoticeClaim, NoticeKind, NoticeRole, NoticePreview,
    inspect_notification_claim,
)
from .pix_automation_contract import FinancialOperationBlocked

_DOMAIN = "FR_FINANCE_M38110_INVITE_MEMBER_NOTICE_CI_ONLY_V1"
_SHA = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, kw_only=True)
class PendingMemberInvitationEvidence:
    invitation_id: UUID
    tenant_id: UUID
    recipient_user_id: UUID
    required_document_id: UUID
    published_document_id: UUID
    required_document_sha256: str
    published_document_sha256: str
    target_role: str
    cycle_year: int
    invitation_revision: int
    invitation_expires_at: datetime
    observed_at: datetime
    invitation_revoked: bool
    invitation_accepted: bool
    document_published: bool


@dataclass(frozen=True)
class PendingInvitationNoticePreview:
    preview: NoticePreview
    invitation_document_binding_validated_synthetically: bool = True
    source_database_authenticated: bool = False
    recipient_email_verified: bool = False
    contract_consent_recorded: bool = False
    user_activated: bool = False
    inbox_written: bool = False
    email_sent: bool = False
    push_sent: bool = False
    real_delivery_authorized: bool = False
    production_authorized: bool = False


def _uuid(value: object) -> bool:
    return type(value) is UUID and value.int != 0


def _date(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() is not None)


def _valid(e: PendingMemberInvitationEvidence) -> None:
    if (
        type(e) is not PendingMemberInvitationEvidence
        or not all(_uuid(x) for x in (
            e.invitation_id, e.tenant_id, e.recipient_user_id,
            e.required_document_id, e.published_document_id
        ))
        or type(e.target_role) is not str or e.target_role != "TENANT_MEMBER"
        or type(e.cycle_year) is not int or not 2020 <= e.cycle_year <= 2100
        or type(e.invitation_revision) is not int or e.invitation_revision < 1
        or not _date(e.invitation_expires_at)
        or not _date(e.observed_at)
        or any(type(x) is not bool for x in (
            e.invitation_revoked,e.invitation_accepted,e.document_published
        ))
        or type(e.required_document_sha256) is not str
        or type(e.published_document_sha256) is not str
        or _SHA.fullmatch(e.required_document_sha256) is None
        or _SHA.fullmatch(e.published_document_sha256) is None
    ):
        raise FinancialOperationBlocked("M38110_INVALID_INVITATION_NOTICE_EVIDENCE")
    if (
        e.required_document_id != e.published_document_id
        or not compare_digest(e.required_document_sha256,
                              e.published_document_sha256)
        or not e.document_published or e.invitation_revoked
        or e.invitation_accepted
        or e.invitation_expires_at <= e.observed_at
    ):
        raise FinancialOperationBlocked("M38110_UNSAFE_INVITATION_NOTICE_STATE")


def invitation_notice_digest(e: PendingMemberInvitationEvidence) -> str:
    """Domain-separated idempotency binding, NOT a signature or proof.

    Inputs must be a trusted read-side snapshot in a future worker. The digest
    excludes email, CPF, name, invitation token and contract body.
    """
    _valid(e)
    payload={
        "domain":_DOMAIN,
        "invitation":str(e.invitation_id),
        "tenant":str(e.tenant_id),
        "recipient":str(e.recipient_user_id),
        "role":e.target_role,
        "document":str(e.required_document_id),
        "sha256":e.required_document_sha256,
        "cycle_year":e.cycle_year,
        "revision":e.invitation_revision,
        "expires_at":e.invitation_expires_at.astimezone(timezone.utc).isoformat(),
    }
    canonical=json.dumps(
        payload,sort_keys=True,ensure_ascii=True,separators=(",",":"),
    ).encode("ascii")
    return sha256(canonical).hexdigest()


def inspect_pending_member_invitation_notice(
    evidence: PendingMemberInvitationEvidence, notice: NoticeClaim,
) -> PendingInvitationNoticePreview:
    """Return a redacted, non-deliverable policy preview only."""
    digest=invitation_notice_digest(evidence)
    if (
        type(notice) is not NoticeClaim
        or notice.event_kind is not NoticeKind.INVITATION_ACCEPTANCE_PENDING
        or notice.role is not NoticeRole.TENANT_MEMBER
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
        raise FinancialOperationBlocked("M38110_INVITATION_NOTICE_SCOPE_MISMATCH")
    preview=inspect_notification_claim(notice)
    return PendingInvitationNoticePreview(preview=preview)
