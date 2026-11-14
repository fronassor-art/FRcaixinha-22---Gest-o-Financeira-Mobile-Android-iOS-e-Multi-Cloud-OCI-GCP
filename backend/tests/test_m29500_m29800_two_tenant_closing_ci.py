"""M29500-M29800: two-tenant closing, replay, arrears, exit and cent tests."""
from dataclasses import replace
from datetime import date,datetime,timezone
from decimal import Decimal
from uuid import UUID
from pathlib import Path
import pytest
from app.closing_contract_oracle import FinancialEvidence
from app.member_cycle_rules import MemberCycleReview
from app.two_tenant_closing_ci import TenantYear, review_two_tenants, checkpoint

A=UUID("00000000-0000-4000-8000-0000000000a1")
B=UUID("00000000-0000-4000-8000-0000000000b1")
M1=UUID(int=101)
M2=UUID(int=102)
STAMP=datetime(2027,6,15,12,tzinfo=timezone.utc)
ROOT=Path(__file__).resolve().parents[2]

def event(tenant, num, kind, amount, reconciled=True):
    return FinancialEvidence(tenant,UUID(int=num),kind,amount,STAMP,reconciled,"CI-EVIDENCE-NOT-AUTHENTIC")

def member(tenant, mid=M1, weight="1.00", eligible=True, overdue=0,
           triggered=None, exit_status="NO_EXIT_REQUEST", status="NO_CONTRACT_TRIGGER_FOUND",
           principal=15000):
    return MemberCycleReview(tenant,mid,date(2027,12,31),overdue,0,triggered,
                            eligible,status,principal,Decimal(weight),exit_status)

def year(tenant, seed, profit=10000, members=None, owner=False, contract=True, cost=0):
    return TenantYear(tenant,2027,"CI-VERSION-2027-FINANCIAL",contract,owner,
        (event(tenant,seed,"REALIZED_REVENUE",profit),
         event(tenant,seed+1,"ELIGIBLE_EXPENSE",cost),
         event(tenant,seed+2,"CAPITAL_PRINCIPAL",500000)),
        members if members is not None else (member(tenant,M1,"2"),member(tenant,M2,"1")))

def pair(): return (year(A,100),year(B,200))

def test_two_tenants_keep_independent_15_85_splits():
    r=review_two_tenants(pair())
    assert r.status=="OFFLINE_PREVIEW_NOT_SETTLED"
    assert r.profit_cents==20000 and r.admin_cents==3000 and r.allocated_to_members_cents==17000
    assert r.reserved_cents==0
    assert [x.tenant_id for x in r.tenant_results]==[A,B]
    assert all(x.closing.admin_remuneration_cents==1500 for x in r.tenant_results)
    assert not r.db_attested and not r.actual_provider_reconciled
    assert not r.closing_authorized and not r.pix_authorized and not r.writes_performed

@pytest.mark.parametrize("value",range(0,201))
def test_rounding_201_cases_conserve_cents_independently(value):
    from decimal import ROUND_HALF_UP
    r=review_two_tenants((year(A,100,value),year(B,200,200-value)))
    expected=sum(int((Decimal(v)*Decimal("0.15")).quantize(
        Decimal("1"),rounding=ROUND_HALF_UP)) for v in (value,200-value))
    assert r.profit_cents==200 and r.admin_cents==expected
    assert r.admin_cents+r.allocated_to_members_cents+r.reserved_cents==200

def test_reversing_tenant_input_does_not_change_outcome():
    a,b=pair()
    assert review_two_tenants((a,b))==review_two_tenants((b,a))

def test_same_person_may_appear_in_both_tenants_without_shared_ledger():
    r=review_two_tenants(pair())
    assert all(x.closing.member_shares[0].member_id==M1 for x in r.tenant_results)

def test_replay_across_tenants_denied():
    a,b=pair()
    b=replace(b,evidence=(event(B,100,"REALIZED_REVENUE",100),))
    with pytest.raises(ValueError,match="REPLAYED_EVENT"): review_two_tenants((a,b))

def test_replay_within_tenant_denied():
    a,b=pair()
    with pytest.raises(ValueError,match="REPLAYED_EVENT"):
        review_two_tenants((replace(a,evidence=a.evidence+(a.evidence[0],)),b))

def test_cross_tenant_event_and_member_denied():
    a,b=pair()
    with pytest.raises(ValueError,match="CROSS_TENANT_EVENT"):
        review_two_tenants((replace(a,evidence=(b.evidence[0],)),b))
    with pytest.raises(ValueError,match="CROSS_TENANT_MEMBER"):
        review_two_tenants((replace(a,members=b.members),b))

def test_same_tenant_mismatched_year_or_invalid_count_denied():
    a,b=pair()
    with pytest.raises(ValueError,match="CYCLE_OR_TENANT_COLLISION"): review_two_tenants((a,a))
    with pytest.raises(ValueError,match="CYCLE_OR_TENANT_COLLISION"): review_two_tenants((a,replace(b,year=2028)))
    with pytest.raises(ValueError,match="EXACTLY_TWO_TENANTS"): review_two_tenants((a,))
    with pytest.raises(ValueError,match="EXACTLY_TWO_TENANTS"): review_two_tenants([a,b])

def test_unreconciled_receipt_holds_only_affected_tenant():
    a,b=pair()
    a=replace(a,evidence=a.evidence+(event(A,903,"REALIZED_REVENUE",500,False),))
    r=review_two_tenants((a,b))
    assert r.status=="REVIEW_HOLD_NO_SETTLEMENT"
    assert r.tenant_results[0].closing.reserved_undistributed_cents==10000
    assert r.tenant_results[1].closing.status=="SIMULATED_NOT_AUTHORIZED"
    assert r.reserved_cents==10000

def test_pending_exit_preserves_principal_and_holds():
    a,b=pair()
    pending=member(A,M1,"2",eligible=None,status="VOLUNTARY_EXIT_UNRESOLVED",
                   exit_status="REQUESTED_AWAITING_REVIEW",principal=15000)
    a=replace(a,members=(pending,a.members[1]))
    r=review_two_tenants((a,b))
    assert "EXIT_OBLIGATIONS_UNRESOLVED" in r.tenant_results[0].holds
    assert r.tenant_results[0].closing.reserved_undistributed_cents==10000
    assert pending.principal_preserved_cents==15000

def test_documented_exit_retains_historical_weight_without_payout():
    a,b=pair()
    leaving=member(A,M1,"2",principal=0,exit_status="EXIT_DOCUMENTED_RIGHTS_PRESERVED")
    r=review_two_tenants((replace(a,members=(leaving,a.members[1])),b))
    assert r.tenant_results[0].closing.member_pool_cents==8500
    assert r.pix_authorized is False

def test_ninety_days_different_from_three_unpaid_months():
    a,b=pair()
    overdue=member(A,M1,"2",overdue=90,triggered=None)
    r=review_two_tenants((replace(a,members=(overdue,a.members[1])),b))
    assert "90_DAY_ARREARS_LEGAL_REVIEW" in r.tenant_results[0].holds
    assert "OWNER_THREE_UNPAID_LEGAL_REVIEW" not in r.tenant_results[0].holds
    assert r.tenant_results[0].closing.reserved_undistributed_cents==10000

def test_owner_exclusion_only_profit_with_principal_intact():
    a,b=pair()
    excluded=member(A,M1,"0",eligible=False,principal=45000,
         triggered=date(2027,3,11),status="OWNER_CYCLE_PROFIT_EXCLUDED")
    r=review_two_tenants((replace(a,owner_box=True,members=(excluded,a.members[1])),b))
    assert r.tenant_results[0].closing.member_shares[0].final_cents==0
    assert r.tenant_results[0].closing.member_shares[1].final_cents==8500
    assert excluded.principal_preserved_cents==45000
    assert not r.closing_authorized

def test_unapproved_owner_exclusion_holds():
    a,b=pair()
    unresolved=member(A,M1,"2",eligible=None,triggered=date(2027,3,11),
             status="OWNER_EXCLUSION_WAITING_LEGAL_REVIEW")
    r=review_two_tenants((replace(a,owner_box=True,members=(unresolved,a.members[1])),b))
    assert "OWNER_THREE_UNPAID_LEGAL_REVIEW" in r.tenant_results[0].holds
    assert r.tenant_results[0].closing.member_shares==()

def test_other_tenant_cannot_inherit_owner_exclusion():
    a,b=pair()
    unresolved=member(B,M1,"2",eligible=None,triggered=date(2027,3,11),
             status="TENANT_POLICY_REVIEW_REQUIRED")
    r=review_two_tenants((a,replace(b,members=(unresolved,b.members[1]))))
    assert "TENANT_SPECIFIC_THREE_UNPAID_REVIEW" in r.tenant_results[1].holds
    assert r.tenant_results[0].closing.status=="SIMULATED_NOT_AUTHORIZED"

def test_no_eligible_members_reserves_85_percent():
    a,b=pair()
    r=review_two_tenants((replace(a,members=(member(A,M1,"0",eligible=False),)),b))
    assert r.tenant_results[0].closing.admin_remuneration_cents==1500
    assert r.tenant_results[0].closing.reserved_undistributed_cents==8500

def test_expense_and_principal_are_not_profit():
    a,b=pair()
    a=year(A,100,profit=250,cost=500)
    r=review_two_tenants((a,b))
    assert r.tenant_results[0].closing.net_result_cents==-250
    assert r.tenant_results[0].closing.distributable_profit_cents==0

def test_unreviewed_contract_blocks_allocation():
    a,b=pair()
    r=review_two_tenants((replace(a,contract_reviewed_claim=False),b))
    assert r.tenant_results[0].closing.reserved_undistributed_cents==10000
    assert r.tenant_results[0].closing.admin_remuneration_cents==0

def test_no_external_effects_or_prod_permission_claim():
    source=(ROOT/"backend/app/two_tenant_closing_ci.py").read_text()
    routes=(ROOT/"backend/app/routers/closings.py").read_text()
    assert "two_tenant_closing_ci" not in routes
    for prohibited in ("asyncpg.connect(", "psycopg.connect(", "import oci", "requests.post(", "INSERT INTO ", "UPDATE public."):
        assert prohibited not in source
    c=checkpoint()
    assert c["project"]=="FR_FINANCE_AI_STUDIO"
    assert c["package"]=="M29500_M29800"
    assert not any(v for k,v in c.items() if k.endswith(("_touched","_applied","_verified","_enabled","_authorized")))
