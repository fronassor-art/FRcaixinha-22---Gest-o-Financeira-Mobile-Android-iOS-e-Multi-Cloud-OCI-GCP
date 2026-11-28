"""FR Finance M31100: SaaS preproduction decision, **never** a release token.

This pure evaluator requires a server-built snapshot. The UI and webhook
must not supply these fields as authoritative evidence. Positive outcome
only permits further independent staging verification; it never enables
real accounts, MP payments, tenant ledger entries or production release.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
import re

_SHA = re.compile(r"^[0-9a-f]{64}$")
_COLLECTOR = re.compile(r"^[0-9]{1,40}$")


@dataclass(frozen=True)
class SaaSReadinessSnapshot:
    tenant_id: UUID
    preparation_tenant_id: UUID
    payment_tenant_id: UUID
    entitlement_tenant_id: UUID
    administrator_active: bool
    admin_membership_active: bool
    tenant_status: str
    published_contract_sha: str
    accepted_contract_sha: str
    offer_plan_tier: str
    entitlement_plan_tier: str
    plan_status: str
    payment_status: str
    provider_readback_confirmed: bool
    provider_collector_id: str
    platform_collector_id: str
    currency: str
    chargeback_or_refund: bool
    entitlement_status: str
    valid_from: datetime
    valid_until: datetime
    checked_at: datetime
    members_count: int
    quotas_count: int
    members_limit: int | None
    quotas_limit: int | None
    source: str = "CI_SYNTHETIC"


@dataclass(frozen=True)
class SaaSReadinessDecision:
    state: str
    staging_preflight_eligible: bool
    real_registration_authorized: bool = False
    real_billing_authorized: bool = False
    real_pix_authorized: bool = False
    tenant_ledger_write_authorized: bool = False
    production_release_authorized: bool = False


def evaluate_saas_readiness(s: SaaSReadinessSnapshot) -> SaaSReadinessDecision:
    """No grace period, no implicit plan, no cross-tenant entitlement."""
    if type(s) is not SaaSReadinessSnapshot:
        raise TypeError("SaaS readiness requires a typed server snapshot")
    if (any(type(x) is not UUID for x in
            (s.tenant_id, s.preparation_tenant_id, s.payment_tenant_id,
             s.entitlement_tenant_id))
            or any(type(x) is not bool for x in
              (s.administrator_active,s.admin_membership_active,
               s.provider_readback_confirmed,s.chargeback_or_refund))
            or any(type(x) is not int or x < 0 or x > 1_000_000_000
              for x in (s.members_count,s.quotas_count))
            or any(x is not None and
                (type(x) is not int or x <= 0 or x > 1_000_000_000)
              for x in (s.members_limit,s.quotas_limit))
            or any(type(t) is not datetime or t.tzinfo is None
                or t.utcoffset() is None
              for t in (s.valid_from,s.valid_until,s.checked_at))
            or not s.valid_from < s.valid_until):
        raise ValueError("INVALID_SAAS_READINESS_SNAPSHOT")
    if s.source != "CI_SYNTHETIC":
        return SaaSReadinessDecision("UNTRUSTED_EVIDENCE",False)
    if len({s.tenant_id,s.preparation_tenant_id,s.payment_tenant_id,
            s.entitlement_tenant_id}) != 1:
        return SaaSReadinessDecision("TENANT_CROSS_SCOPE",False)
    if s.tenant_status != "ATIVO" or not s.administrator_active        or not s.admin_membership_active:
        return SaaSReadinessDecision("TENANT_OR_ADMIN_INACTIVE",False)
    if (not _SHA.fullmatch(s.published_contract_sha)
        or s.published_contract_sha != s.accepted_contract_sha):
        return SaaSReadinessDecision("CONTRACT_VERSION_UNVERIFIED",False)
    if (s.offer_plan_tier not in ("ESSENCIAL","INTERMEDIARIO","AMPLIADO")
        or s.offer_plan_tier != s.entitlement_plan_tier
        or s.plan_status != "ACTIVE"
        or s.members_limit is None or s.quotas_limit is None):
        return SaaSReadinessDecision("PLAN_UNAPPROVED_OR_UNCAPPED",False)
    if s.members_count > s.members_limit or s.quotas_count > s.quotas_limit:
        return SaaSReadinessDecision("PLAN_CAPACITY_EXCEEDED",False)
    if (s.payment_status != "APPROVED" or not s.provider_readback_confirmed
        or s.currency != "BRL"
        or not _COLLECTOR.fullmatch(s.platform_collector_id)
        or s.provider_collector_id != s.platform_collector_id):
        return SaaSReadinessDecision("PROVIDER_PAYMENT_NOT_ATTESTED",False)
    if s.chargeback_or_refund:
        return SaaSReadinessDecision("REFUND_OR_CHARGEBACK_HOLD",False)
    if s.entitlement_status != "ACTIVE":
        return SaaSReadinessDecision("LICENSE_NOT_ACTIVE",False)
    if s.checked_at < s.valid_from:
        return SaaSReadinessDecision("LICENSE_NOT_STARTED",False)
    if s.checked_at >= s.valid_until:
        return SaaSReadinessDecision("LICENSE_EXPIRED_ZERO_GRACE",False)
    return SaaSReadinessDecision("STAGING_PREFLIGHT_ONLY",True)
