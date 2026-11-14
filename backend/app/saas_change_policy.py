"""FR Finance M31700: preproduction SaaS change/recovery decisions, no side effects.

Plans review of cancellation, renewal, upgrade, refund and resumption.
No function here charges Pix, changes a subscription or grants rights.
External contracts and real payment provider must be independently verified.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Literal
import re

Action = Literal["CANCEL_AT_END", "RENEW_PREPARE", "UPGRADE_PREPARE",
                 "REFUND_REVIEW", "RESUME_REVIEW"]
_SHA = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SaaSChangeSnapshot:
    action: Action
    tenant_id: UUID
    current_entitlement_tenant_id: UUID
    actor_id: UUID
    tenant_admin_id: UUID
    reviewer_id: UUID | None
    actor_role: str
    current_status: str
    current_plan_tier: str
    proposed_plan_tier: str
    proposed_plan_active: bool
    proposal_price_version_id: UUID | None
    current_price_version_id: UUID
    acceptance_sha256: str
    offer_sha256: str
    current_valid_until: datetime
    checked_at: datetime
    current_member_count: int
    current_quota_count: int
    held_member_count: int
    held_quota_count: int
    proposed_members_limit: int | None
    proposed_quotas_limit: int | None
    pending_action: bool
    refund_or_chargeback: bool
    provider_verified: bool
    independent_approval: bool
    reason: str
    source: str = "SERVER_STAGING_CI"


@dataclass(frozen=True)
class SaaSChangeDecision:
    state: str
    review_candidate: bool
    persisted: bool = False
    real_charge_authorized: bool = False
    real_entitlement_mutation_authorized: bool = False
    real_pix_authorized: bool = False
    tenant_ledger_write_authorized: bool = False
    production_authorized: bool = False


def review_saas_change(x: SaaSChangeSnapshot) -> SaaSChangeDecision:
    if type(x) is not SaaSChangeSnapshot:
        raise TypeError("INVALID_SAAS_CHANGE_OBJECT")
    if (any(type(u) is not UUID for u in (
            x.tenant_id, x.current_entitlement_tenant_id,
            x.actor_id,x.tenant_admin_id,x.current_price_version_id))
        or (x.reviewer_id is not None and type(x.reviewer_id) is not UUID)
        or (x.proposal_price_version_id is not None and
            type(x.proposal_price_version_id) is not UUID)
        or any(type(i) is not int or i<0 for i in (
            x.current_member_count,x.current_quota_count,
            x.held_member_count,x.held_quota_count))
        or any(type(t) is not datetime or t.tzinfo is None or
               t.utcoffset() is None for t in
               (x.current_valid_until,x.checked_at))
        or any(type(flag) is not bool for flag in
            (x.proposed_plan_active,x.pending_action,
             x.refund_or_chargeback,x.provider_verified,
             x.independent_approval))
        or any(v is not None and (type(v) is not int or v<=0)
            for v in (x.proposed_members_limit,x.proposed_quotas_limit))):
        raise ValueError("INVALID_SAAS_CHANGE_EVIDENCE")
    if x.source!="SERVER_STAGING_CI":
        return SaaSChangeDecision("UNTRUSTED_SOURCE",False)
    if x.tenant_id!=x.current_entitlement_tenant_id:
        return SaaSChangeDecision("TENANT_SCOPE_MISMATCH",False)
    if x.pending_action:
        return SaaSChangeDecision("EXISTING_ACTION_PENDING",False)
    if x.current_status not in ("ACTIVE","SUSPENDED","EXPIRED","REVOKED"):
        return SaaSChangeDecision("UNKNOWN_LICENSE_STATE",False)
    if len(x.reason.strip())<15 or len(x.reason)>240:
        return SaaSChangeDecision("AUDIT_REASON_MISSING",False)
    if x.action not in ("CANCEL_AT_END","RENEW_PREPARE","UPGRADE_PREPARE",
                         "REFUND_REVIEW","RESUME_REVIEW"):
        return SaaSChangeDecision("UNKNOWN_ACTION",False)
    if (x.actor_role not in ("MASTER","TENANT_ADMIN")
        or (x.actor_role=="TENANT_ADMIN" and x.actor_id!=x.tenant_admin_id)):
        return SaaSChangeDecision("ACTOR_NOT_AUTHORIZED",False)
    if x.action in ("REFUND_REVIEW","RESUME_REVIEW") and (
        x.actor_role!="MASTER" or not x.independent_approval
        or x.reviewer_id is None or x.reviewer_id==x.actor_id):
        return SaaSChangeDecision("INDEPENDENT_REVIEW_REQUIRED",False)
    if x.action in ("RENEW_PREPARE","UPGRADE_PREPARE"):
        if (not _SHA.fullmatch(x.acceptance_sha256)
            or x.acceptance_sha256 != x.offer_sha256
            or x.proposal_price_version_id is None
            or x.proposal_price_version_id == x.current_price_version_id
            or not x.proposed_plan_active
            or x.proposed_members_limit is None
            or x.proposed_quotas_limit is None):
            return SaaSChangeDecision("OFFER_OR_CONSENT_UNVERIFIED",False)
        if (x.current_member_count+x.held_member_count>x.proposed_members_limit
            or x.current_quota_count+x.held_quota_count>x.proposed_quotas_limit):
            return SaaSChangeDecision("PROPOSED_PLAN_UNDERCAPACITY",False)
        if x.current_status=="REVOKED" or x.refund_or_chargeback:
            return SaaSChangeDecision("LICENSE_REVOKED_OR_REFUNDED",False)
        if x.action=="UPGRADE_PREPARE" and (
            x.current_status!="ACTIVE" or x.checked_at>=x.current_valid_until
            or x.proposed_plan_tier==x.current_plan_tier):
            return SaaSChangeDecision("UPGRADE_NOT_ELIGIBLE",False)
        return SaaSChangeDecision("RENEWAL_REVIEW_ONLY" if
            x.action=="RENEW_PREPARE" else "UPGRADE_REVIEW_ONLY",True)
    if x.action=="CANCEL_AT_END":
        if x.current_status not in ("ACTIVE","SUSPENDED"):
            return SaaSChangeDecision("CANCELLATION_NOT_ELIGIBLE",False)
        return SaaSChangeDecision("CANCEL_REVIEW_NO_REFUND",True)
    if x.action=="REFUND_REVIEW":
        if not x.provider_verified or not x.refund_or_chargeback or            x.current_status=="REVOKED":
            return SaaSChangeDecision("VERIFIED_REFUND_REQUIRED",False)
        return SaaSChangeDecision("REFUND_REVIEW_NO_MONEY_MOVED",True)
    # RESUME_REVIEW; no grace after valid_until.
    if (x.current_status!="SUSPENDED" or
        x.checked_at>=x.current_valid_until or
        not x.provider_verified or x.refund_or_chargeback):
        return SaaSChangeDecision("RESUME_DENIED",False)
    return SaaSChangeDecision("RESUME_REVIEW_NO_ENTITLEMENT_WRITE",True)
