"""M31900-M32300: CI-only capacity/renewal preflights; never real permissions."""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID
import re

SHA = re.compile(r"^[0-9a-f]{64}$")

@dataclass(frozen=True)
class CapacitySnapshot:
    tenant: UUID
    licensed_tenant: UUID
    actor: UUID
    administrator: UUID
    tenant_active: bool
    admin_active: bool
    license_active: bool
    payment_verified: bool
    refund: bool
    valid_from: datetime
    valid_until: datetime
    now: datetime
    plan_active: bool
    members: int
    quotas: int
    held_members: int
    held_quotas: int
    max_members: int | None
    max_quotas: int | None
    category: str
    quantity: int
    source: str = "CI_SERVER_SNAPSHOT"

@dataclass(frozen=True)
class RenewalSnapshot:
    capacity: CapacitySnapshot
    entitlement: UUID
    price_version: UUID
    period: str
    currency: str
    amount_cents: int
    contract_published_sha: str
    contract_accepted_sha: str
    pending_term: bool
    source: str = "CI_SERVER_SNAPSHOT"

@dataclass(frozen=True)
class Preview:
    state: str
    review_only: bool = False
    term_key: str | None = None
    persisted: bool = False
    real_members_authorized: bool = False
    real_quotas_authorized: bool = False
    real_charge_authorized: bool = False
    real_renewal_authorized: bool = False
    pix_authorized: bool = False
    tenant_ledger_authorized: bool = False
    production_authorized: bool = False

def _valid(s: CapacitySnapshot) -> None:
    if not all(type(v) is UUID for v in (s.tenant,s.licensed_tenant,s.actor,s.administrator)):
        raise ValueError("INVALID_CAPACITY_SNAPSHOT")
    if not all(type(v) is bool for v in (s.tenant_active,s.admin_active,s.license_active,
        s.payment_verified,s.refund,s.plan_active)):
        raise ValueError("INVALID_CAPACITY_SNAPSHOT")
    if not all(type(v) is int and 0<=v<=1_000_000_000 for v in
        (s.members,s.quotas,s.held_members,s.held_quotas)):
        raise ValueError("INVALID_CAPACITY_SNAPSHOT")
    if not type(s.quantity) is int or not 1<=s.quantity<=100:
        raise ValueError("INVALID_CAPACITY_SNAPSHOT")
    if any(v is not None and (type(v) is not int or not 1<=v<=1_000_000_000)
           for v in (s.max_members,s.max_quotas)):
        raise ValueError("INVALID_CAPACITY_SNAPSHOT")
    if any(type(v) is not datetime or v.tzinfo is None or v.utcoffset() is None
           for v in (s.valid_from,s.valid_until,s.now)) or s.valid_until<=s.valid_from:
        raise ValueError("INVALID_CAPACITY_SNAPSHOT")

def preview_capacity(s: CapacitySnapshot) -> Preview:
    if type(s) is not CapacitySnapshot:
        raise TypeError("INVALID_CAPACITY_TYPE")
    _valid(s)
    if s.source!="CI_SERVER_SNAPSHOT":
        return Preview("UNTRUSTED_SOURCE")
    if s.tenant!=s.licensed_tenant:
        return Preview("CROSS_TENANT_LICENSE")
    if s.actor!=s.administrator or not s.tenant_active or not s.admin_active:
        return Preview("ADMIN_DENIED")
    if not s.plan_active or s.max_members is None or s.max_quotas is None:
        return Preview("UNVERIFIED_PLAN")
    if not s.license_active or not s.payment_verified or s.refund:
        return Preview("UNVERIFIED_LICENSE_PAYMENT")
    if not s.valid_from<=s.now<s.valid_until:
        return Preview("ZERO_GRACE_LICENSE_EXPIRED")
    if s.category not in ("MEMBER","QUOTA"):
        return Preview("INVALID_CATEGORY")
    more_m=s.quantity if s.category=="MEMBER" else 0
    more_q=s.quantity if s.category=="QUOTA" else 0
    if s.members+s.held_members+more_m>s.max_members or s.quotas+s.held_quotas+more_q>s.max_quotas:
        return Preview("CAPACITY_EXCEEDED")
    return Preview("CAPACITY_REVIEW_CI_ONLY",True)

def preview_renewal(s: RenewalSnapshot) -> Preview:
    if type(s) is not RenewalSnapshot:
        raise TypeError("INVALID_RENEWAL_TYPE")
    if type(s.capacity) is not CapacitySnapshot:
        raise ValueError("INVALID_RENEWAL_SNAPSHOT")
    _valid(s.capacity)
    if (type(s.entitlement) is not UUID or type(s.price_version) is not UUID
        or type(s.amount_cents) is not int or not 1<=s.amount_cents<=1_000_000_000
        or type(s.pending_term) is not bool):
        raise ValueError("INVALID_RENEWAL_SNAPSHOT")
    if s.source!="CI_SERVER_SNAPSHOT" or s.capacity.source!="CI_SERVER_SNAPSHOT":
        return Preview("UNTRUSTED_SOURCE")
    # Existing active term and verified payment are prerequisites to review,
    # not evidence of an actual provider charge or a release gate.
    c=s.capacity
    common=preview_capacity(c)
    if not common.review_only:
        # Renewal is not an extra seat allocation. A fully occupied plan
        # can be renewed if total occupied + held remains <= proposed limit.
        if common.state!="CAPACITY_EXCEEDED" or (
            c.members+c.held_members>c.max_members or
            c.quotas+c.held_quotas>c.max_quotas):
            return Preview("BASE_"+common.state)
    if s.period not in ("MONTHLY","ANNUAL") or s.currency!="BRL":
        return Preview("INVALID_RENEWAL_OFFER")
    if not SHA.fullmatch(s.contract_published_sha) or s.contract_accepted_sha!=s.contract_published_sha:
        return Preview("CONSENT_UNVERIFIED")
    if s.pending_term:
        return Preview("DUPLICATE_TERM")
    # Quota/member totals checked WITHOUT a newly requested slot.
    if c.members+c.held_members>c.max_members or c.quotas+c.held_quotas>c.max_quotas:
        return Preview("RENEWAL_UNDERCAPACITY")
    term="|".join((str(c.tenant),str(s.entitlement),
        c.valid_until.astimezone(timezone.utc).isoformat(),s.period))
    # Request ID, price version and amount deliberately absent.
    key=sha256(("FR_FINANCE_RENEWAL_V1|"+term).encode("ascii")).hexdigest()
    return Preview("RENEWAL_REVIEW_CI_NO_CHARGE",True,key)
