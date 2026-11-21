"""M29500-M29800: two-tenant closing cross-check, offline only.

Composes existing annual closing oracle; never authorizes settlement, real
users, Pix, contract enforcement, or any PostgreSQL/OCI operation.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
from .closing_contract_oracle import AnnualClosingPreview, FinancialEvidence, simulate_contract_closing
from .member_cycle_rules import MemberCycleReview

@dataclass(frozen=True)
class TenantYear:
    tenant_id: UUID
    year: int
    contract_version: str
    contract_reviewed_claim: bool
    owner_box: bool
    evidence: tuple[FinancialEvidence, ...]
    members: tuple[MemberCycleReview, ...]

    def __post_init__(self):
        if (type(self.tenant_id) is not UUID or self.tenant_id.int == 0
            or type(self.year) is not int or not 2026 <= self.year <= 2100
            or type(self.contract_version) is not str or len(self.contract_version) < 8
            or type(self.contract_reviewed_claim) is not bool or type(self.owner_box) is not bool
            or type(self.evidence) is not tuple or type(self.members) is not tuple):
            raise ValueError("M29500_INVALID_YEAR")

@dataclass(frozen=True)
class TenantResult:
    tenant_id: UUID
    closing: AnnualClosingPreview
    holds: tuple[str, ...]

@dataclass(frozen=True)
class PortfolioResult:
    tenant_results: tuple[TenantResult, ...]
    profit_cents: int
    admin_cents: int
    allocated_to_members_cents: int
    reserved_cents: int
    status: str
    synthetic_only: bool = True
    actual_provider_reconciled: bool = False
    db_attested: bool = False
    closing_authorized: bool = False
    pix_authorized: bool = False
    writes_performed: bool = False

def _holds(case: TenantYear) -> tuple[str, ...]:
    holds: set[str] = set()
    for member in case.members:
        if not isinstance(member, MemberCycleReview) or member.tenant_id != case.tenant_id:
            raise ValueError("M29600_CROSS_TENANT_MEMBER")
        if (type(member.longest_overdue_days) is not int or member.longest_overdue_days < 0
            or type(member.principal_preserved_cents) is not int or member.principal_preserved_cents < 0):
            raise ValueError("M29600_INVALID_MEMBER_PROOF")
        if member.longest_overdue_days >= 90:
            holds.add("90_DAY_ARREARS_LEGAL_REVIEW")
        if member.historic_three_unpaid_on is not None:
            if case.owner_box:
                if not (member.profit_eligible is False
                        and member.status == "OWNER_CYCLE_PROFIT_EXCLUDED"
                        and member.capital_days_weight == Decimal(0)):
                    holds.add("OWNER_THREE_UNPAID_LEGAL_REVIEW")
            else:
                holds.add("TENANT_SPECIFIC_THREE_UNPAID_REVIEW")
        if member.exit_status in ("REQUESTED_AWAITING_REVIEW", "APPROVED_BUT_SETTLEMENT_UNVERIFIED"):
            holds.add("EXIT_OBLIGATIONS_UNRESOLVED")
        if member.profit_eligible is None:
            holds.add("ELIGIBILITY_UNATTESTED")
    return tuple(sorted(holds))

def review_two_tenants(cases: tuple[TenantYear, ...]) -> PortfolioResult:
    if (type(cases) is not tuple or len(cases) != 2
        or any(type(c) is not TenantYear for c in cases)):
        raise ValueError("M29500_EXACTLY_TWO_TENANTS")
    a,b=cases
    if a.tenant_id == b.tenant_id or a.year != b.year:
        raise ValueError("M29500_CYCLE_OR_TENANT_COLLISION")
    event_ids: set[UUID] = set()
    reports: list[TenantResult] = []
    for case in sorted(cases,key=lambda item:str(item.tenant_id)):
        for e in case.evidence:
            if not isinstance(e,FinancialEvidence) or e.tenant_id != case.tenant_id:
                raise ValueError("M29500_CROSS_TENANT_EVENT")
            if e.event_id.int == 0 or e.event_id in event_ids:
                raise ValueError("M29500_REPLAYED_EVENT")
            event_ids.add(e.event_id)
        reasons=_holds(case)
        snapshot=simulate_contract_closing(
            tenant_id=case.tenant_id,cycle_year=case.year,
            admin_percent=Decimal("15.00"),member_percent=Decimal("85.00"),
            fixed_cycle_policy_version=case.contract_version,
            evidence=case.evidence,reviews=case.members,
            contract_compliant=case.contract_reviewed_claim and not reasons,
        )
        awarded=sum(member.final_cents for member in snapshot.member_shares)
        if (snapshot.admin_remuneration_cents+awarded
            +snapshot.reserved_undistributed_cents != snapshot.distributable_profit_cents):
            raise AssertionError("M29700_CENT_CONSERVATION")
        reports.append(TenantResult(case.tenant_id,snapshot,reasons))
    profit=sum(x.closing.distributable_profit_cents for x in reports)
    admin=sum(x.closing.admin_remuneration_cents for x in reports)
    member_pool=sum(s.final_cents for x in reports for s in x.closing.member_shares)
    reserve=sum(x.closing.reserved_undistributed_cents for x in reports)
    if profit != admin+member_pool+reserve:
        raise AssertionError("M29700_CROSS_TENANT_CENT_CONSERVATION")
    pending=any(x.holds or x.closing.status in (
        "PENDING_REVIEW_OR_RECONCILIATION","NO_ELIGIBLE_MEMBERS_RESERVE_PENDING") for x in reports)
    return PortfolioResult(tuple(reports),profit,admin,member_pool,reserve,
        "REVIEW_HOLD_NO_SETTLEMENT" if pending else "OFFLINE_PREVIEW_NOT_SETTLED")

def checkpoint() -> dict:
    return {"project":"FR_FINANCE_AI_STUDIO","package":"M29500_M29800",
            "mode":"OFFLINE_TWO_TENANT_AUDIT",
            "local_postgres_5433_touched":False,"oci_automation_touched":False,
            "sql_migrations_applied":False,"staging_verified":False,
            "real_users_enabled":False,"real_pix_enabled":False,
            "production_authorized":False}
