"""M601–M760: invariantes de escrituração versus cadastro (zero dinheiro real)."""
from dataclasses import replace
from decimal import Decimal
from uuid import UUID
import pytest

from app.financial_integrity import (
    MemberFact,ContributionFact,LedgerFact,CyclePolicyFact,
    analyze_financial_integrity,money_cents,
)

T=UUID(int=50001)
B=UUID(int=50002)
CYCLE=UUID(int=50003)
A=UUID(int=50004)
M1=UUID(int=50005)
M2=UUID(int=50006)
P=UUID(int=50007)
ACCOUNTS=("1.1.1","1.2.1","2.1.1","2.2.1","4.1.1")


def make(*,amounts=(15000,7500,0),ledger_change=0,extra_members=0,
         policy_count=1,owner=T,year=2027,cycle_status="ABERTO",
         account_codes=ACCOUNTS):
    members=[MemberFact(A,owner,UUID(int=88),"TENANT_ADMIN","ATIVA"),
             MemberFact(M1,owner,UUID(int=88),"TENANT_MEMBER","ATIVA"),
             MemberFact(M2,owner,UUID(int=89),"TENANT_MEMBER","ATIVA")]
    for n in range(extra_members):
        members.append(MemberFact(UUID(int=700+n),owner,
            UUID(int=10000+n),"TENANT_MEMBER","ATIVA"))
    rows=[]
    postings=[]
    for i,value in enumerate(amounts):
        payment_status=("QUITADA" if value==15000 else
                        "PARCIAL" if value>0 else "PENDENTE")
        contribution_id=UUID(int=100+i)
        rows.append(ContributionFact(contribution_id,owner,CYCLE,
            M1,f"2027-{i+1:02d}",15000,value,payment_status))
        if value>0:
            postings.append(LedgerFact(UUID(int=300+i),owner,
                str(contribution_id),2,1,1,value+ledger_change,
                value+ledger_change,value+ledger_change,
                value+ledger_change,0))
    policies=tuple(CyclePolicyFact(UUID(int=900+j),owner,CYCLE,j+1,
                 Decimal("15.00"),Decimal("85.00"),15000,"ACTIVE")
                 for j in range(policy_count))
    return dict(tenant_id=T,cycle_id=CYCLE,year=year,
        cycle_status=cycle_status,members=tuple(members),
        contributions=tuple(rows),ledger=tuple(postings),
        policies=policies,account_codes=tuple(account_codes))


def evaluate(**kwargs):
    return analyze_financial_integrity(**make(**kwargs))


def test_baseline_ledger_contributions_roles_profits_never_claimed():
    r=evaluate()
    assert r.status=="REGISTERED_INTEGRITY_ONLY"
    assert r.findings==()
    assert (r.members_links,r.members_distinct,r.member_role_links,r.admin_role_links)==(3,2,2,1)
    assert r.registered_due_cents==45000
    assert r.registered_paid_cents==22500
    assert r.registered_open_cents==22500
    assert (r.complete_count,r.partial_count,r.pending_count)==(1,1,1)
    assert (r.ledger_transactions,r.balanced_transactions)==(2,2)
    assert (r.ledger_dr_cents,r.ledger_cr_cents)==(22500,22500)
    assert r.linked_contributions==2
    assert r.linked_payment_cents==22500
    assert r.missing_ledger_count==0 and r.incorrect_link_count==0
    assert r.quota_value_cents==15000
    assert (r.admin_percent,r.member_percent)==("15.00","85.00")
    assert r.no_bank_evidence and not r.bank_reconciled
    assert r.cash_available_cents is None
    assert r.master_saas_revenue_cents is None
    assert r.member_profit_share_cents is None
    assert not r.closing_authorized and not r.transfer_authorized


@pytest.mark.parametrize("paid",range(0,121))
def test_121_partial_amounts_reconcile_to_exact_cent(paid):
    r=evaluate(amounts=(paid,))
    assert r.registered_paid_cents==paid
    assert r.registered_open_cents==15000-paid
    assert r.linked_payment_cents==paid
    assert r.status=="REGISTERED_INTEGRITY_ONLY"
    assert r.missing_ledger_count==0 and r.incorrect_link_count==0


@pytest.mark.parametrize("drift",range(1,121))
def test_120_mismatched_registered_vs_ledger_detected(drift):
    r=evaluate(amounts=(7500,),ledger_change=drift)
    assert r.status=="REVIEW_REQUIRED"
    assert "CONTRIBUTION_LEDGER_DISAGREEMENT" in r.findings
    assert r.incorrect_link_count==1
    assert r.registered_paid_cents==7500
    assert r.ledger_dr_cents==7500+drift
    assert not r.bank_reconciled


@pytest.mark.parametrize("count",range(0,120))
def test_120_unique_members_with_admin_member_double_role(count):
    r=evaluate(extra_members=count)
    assert r.members_links==3+count
    assert r.members_distinct==2+count
    assert r.member_role_links==2+count
    assert r.admin_role_links==1
    assert r.status=="REGISTERED_INTEGRITY_ONLY"


@pytest.mark.parametrize("month",range(1,13))
def test_12_months_preserve_competence_and_payment_integrity(month):
    args=make()
    args["contributions"]=(replace(
        args["contributions"][0],competence=f"2027-{month:02d}"),)
    args["ledger"]=args["ledger"][:1]
    r=analyze_financial_integrity(**args)
    assert r.registered_contributions==1
    assert r.status=="REGISTERED_INTEGRITY_ONLY"


@pytest.mark.parametrize("delta",range(1,121))
def test_120_unbalanced_dr_cr_detected_without_bank_claim(delta):
    d=make(amounts=(7500,))
    ledger=d["ledger"][0]
    d["ledger"]=(replace(ledger,dr_cents=ledger.dr_cents+delta),)
    r=analyze_financial_integrity(**d)
    assert r.status=="REVIEW_REQUIRED"
    assert r.balanced_transactions==0
    assert "UNBALANCED_LEDGER_TRANSACTION" in r.findings
    assert "LEDGER_TOTALS_DIFFER" in r.findings
    assert r.linked_contributions==1
    assert r.incorrect_link_count==1


@pytest.mark.parametrize("status",["QUITADA","PARCIAL","PENDENTE","NOVO",None])
def test_bad_contribution_status_never_reports_healthy(status):
    args=make(amounts=(7500,))
    args["contributions"]=(replace(args["contributions"][0],payment_status=status),)
    r=analyze_financial_integrity(**args)
    if status=="PARCIAL":
        assert r.status=="REGISTERED_INTEGRITY_ONLY"
    else:
        assert "CONTRIBUTION_STATUS_INCONSISTENT" in r.findings


@pytest.mark.parametrize("bad",[-1,True,1.2,Decimal("12.00"),999999999999999])
def test_noninteger_cents_rejected(bad):
    args=make()
    args["contributions"]=(replace(args["contributions"][0],paid_cents=bad),)
    with pytest.raises(ValueError):
        analyze_financial_integrity(**args)


@pytest.mark.parametrize("bad",["15.001","NaN","-1","Infinity"])
def test_invalid_money_precision_fails_closed(bad):
    with pytest.raises(ValueError):
        money_cents(Decimal(bad))


def test_missing_ledger_is_not_fake_bank_proof():
    d=make()
    d["ledger"]=()
    r=analyze_financial_integrity(**d)
    assert r.missing_ledger_count==2
    assert "REGISTERED_PAYMENTS_WITHOUT_LEDGER" in r.findings
    assert "NO_LEDGER_FOR_RECORDED_PAYMENTS" in r.findings
    assert not r.bank_reconciled


def test_cycle_with_zero_transactions_and_zero_paid_is_safe_but_not_cash_available():
    r=evaluate(amounts=(0,0,0))
    assert r.ledger_transactions==0
    assert r.registered_paid_cents==0
    assert r.findings==()
    assert r.cash_available_cents is None and r.no_bank_evidence


def test_duplicate_membership_and_duplicate_user_role_rejected():
    d=make()
    m=d["members"][0]
    for duplicate in (m,replace(m,id=UUID(int=999))):
        d2=dict(d,members=d["members"]+(duplicate,))
        with pytest.raises(ValueError):
            analyze_financial_integrity(**d2)


def test_same_identity_can_hold_distinct_admin_member_links():
    r=evaluate()
    assert r.members_distinct==2 and r.members_links==3


def test_cross_tenant_member_or_contribution_or_policy_or_ledger_rejected():
    d=make()
    for key in ("members","contributions","policies","ledger"):
        d2=dict(d)
        d2[key]=(replace(d[key][0],tenant_id=B),)+d[key][1:]
        with pytest.raises(ValueError):
            analyze_financial_integrity(**d2)


def test_incorrect_membership_reference_rejected():
    d=make()
    d["contributions"]=(replace(
        d["contributions"][0],membership_id=UUID(int=8989)),)+d["contributions"][1:]
    with pytest.raises(ValueError):
        analyze_financial_integrity(**d)


def test_duplicate_competence_and_duplicate_contribution_id_rejected():
    d=make()
    for c in (replace(d["contributions"][0],id=UUID(int=999)),
              replace(d["contributions"][0],competence="2027-03")):
        d2=dict(d,contributions=d["contributions"]+(c,))
        with pytest.raises(ValueError):
            analyze_financial_integrity(**d2)


def test_duplicate_transaction_reference_and_id_rejected():
    d=make()
    for tx in (replace(d["ledger"][0],id=UUID(int=998)),
               replace(d["ledger"][0],reference="OTHER")):
        d2=dict(d,ledger=d["ledger"]+(tx,))
        with pytest.raises(ValueError):
            analyze_financial_integrity(**d2)


def test_missing_or_multiple_active_policies_blocks_integrity():
    for n in (0,2,3):
        r=evaluate(policy_count=n)
        assert "ACTIVE_POLICY_NOT_UNIQUE" in r.findings
        assert r.status=="REVIEW_REQUIRED"


def test_not_all_canonical_accounts_blocks_integrity():
    for code in ACCOUNTS:
        r=evaluate(account_codes=tuple(x for x in ACCOUNTS if x!=code))
        assert "CANONICAL_ACCOUNTS_MISSING" in r.findings
        assert not r.closing_authorized


def test_closed_cycle_needs_external_proof_even_with_balanced_ledger():
    r=evaluate(cycle_status="LIQUIDADO")
    assert r.status=="REVIEW_REQUIRED"
    assert "ALREADY_LIQUIDATED_REQUIRES_EXTERNAL_PROOF" in r.findings


def test_no_member_role_cannot_pass_as_complete():
    d=make(amounts=())
    d["members"]=tuple(x for x in d["members"] if x.role=="TENANT_ADMIN")
    r=analyze_financial_integrity(**d)
    assert "NO_MEMBER_ROLES" in r.findings
    assert "NO_CONTRIBUTIONS_REGISTERED" in r.findings


def test_reference_id_cannot_be_recycled_with_another_contribution():
    d=make(amounts=(15000,15000))
    d["ledger"]=(d["ledger"][0],replace(d["ledger"][1],
        reference=d["ledger"][0].reference))
    with pytest.raises(ValueError):
        analyze_financial_integrity(**d)


def test_overpayments_never_generate_available_cash():
    d=make(amounts=(15000,))
    d["contributions"]=(replace(d["contributions"][0],paid_cents=16000),)
    with pytest.raises(ValueError):
        analyze_financial_integrity(**d)


def test_response_limit_prevents_truncated_all_member_report():
    d=make(extra_members=499)
    assert len(d["members"])>500
    with pytest.raises(ValueError):
        analyze_financial_integrity(**d)
