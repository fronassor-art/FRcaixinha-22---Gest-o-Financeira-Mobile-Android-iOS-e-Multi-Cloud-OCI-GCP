"""M401+ — mais de 300 testes para mora simples e imputação de empréstimo.

Não confundir com contribuição de cota nem com direito à distribuição.
"""
from datetime import date,timedelta
from decimal import Decimal,ROUND_HALF_UP
from uuid import UUID
import pytest

from app.loan_arrears_contract import (
    LoanArrearsPolicy, LoanInstallmentState, quote_loan_arrears,
    apply_partial_loan_payment, ordered_loan_debt,
)

TENANT=UUID("00000000-0000-4000-8000-0000000000a1")
OTHER=UUID("00000000-0000-4000-8000-0000000000b1")
DUE=date(2027,1,10)
POLICY=LoanArrearsPolicy(Decimal("0.20"),1000,"owner-policy-2027")


def installment(*,ident=1,principal=10000,interest=2500,
                mora=0,fine=0,charged=False,tenant=TENANT,due=DUE):
    return LoanInstallmentState(tenant,UUID(int=ident),due,
                               principal,interest,mora,fine,charged)


@pytest.mark.parametrize("days",range(121))
def test_121_daily_simple_mora_no_compounding(days):
    quote=quote_loan_arrears(installment(),DUE+timedelta(days=days),POLICY)
    expected=int((Decimal(10000)*Decimal("0.20")*
                  Decimal(days)/Decimal(30)).quantize(
        Decimal("1"),rounding=ROUND_HALF_UP))
    assert quote.elapsed_days==days
    assert quote.mora_cents==expected
    assert quote.interest_cents==2500
    assert quote.principal_cents==10000
    assert quote.fine_cents==(0 if days==0 else 1000)
    assert quote.total_due_cents==12500+expected+(0 if days==0 else 1000)


@pytest.mark.parametrize("principal",range(1,500,3))
def test_167_principal_bases_get_independent_mora(principal):
    q=quote_loan_arrears(
        installment(principal=principal,interest=0),
        DUE+timedelta(days=17),POLICY)
    mora=int((Decimal(principal)*Decimal("0.20")*Decimal(17)/
              Decimal(30)).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
    assert q.mora_cents==mora
    assert q.principal_cents==principal
    assert q.fine_cents==1000


@pytest.mark.parametrize("paid_cents",range(1,121))
def test_120_payment_amounts_earliest_components_first(paid_cents):
    q=quote_loan_arrears(installment(),DUE+timedelta(days=1),POLICY)
    p=apply_partial_loan_payment(q,paid_cents)
    assert p.paid_interest_cents==paid_cents
    assert p.paid_mora_cents==0 and p.paid_fine_cents==0
    assert p.paid_principal_cents==0
    assert p.new_overdue_principal_cents==10000
    assert p.remaining_cents==q.total_due_cents-paid_cents


def test_full_hierarchy_and_amortize_only_principal_paid():
    q=quote_loan_arrears(installment(principal=10000,interest=100,
                                   mora=50,fine=1000,charged=True),
                         DUE,POLICY)
    assert q.total_due_cents==11150
    p=apply_partial_loan_payment(q,1200)
    assert (p.paid_interest_cents,p.paid_mora_cents,p.paid_fine_cents,
            p.paid_principal_cents)==(100,50,1000,50)
    assert p.new_overdue_principal_cents==9950
    assert p.remaining_cents==9950


def test_fixed_fine_one_time_and_prior_mora_preserved():
    row=installment(principal=10000,interest=0,mora=90,fine=1000,charged=True)
    q=quote_loan_arrears(row,DUE+timedelta(days=1),POLICY)
    assert q.fine_cents==1000
    assert q.mora_cents==157 # 90 + arredondamento de 66,666 centavos
    assert quote_loan_arrears(row,DUE+timedelta(days=1),POLICY).fine_cents==1000


def test_oldest_installment_first_regardless_of_input_order():
    records=(
        installment(ident=3,due=date(2027,3,10)),
        installment(ident=1,due=date(2027,1,10)),
        installment(ident=2,due=date(2027,2,10)),
    )
    assert [x.installment_id.int for x in ordered_loan_debt(TENANT,records)]==[1,2,3]


def test_duplicate_installment_or_wrong_tenant_rejected():
    item=installment()
    with pytest.raises(ValueError):ordered_loan_debt(TENANT,(item,item))
    with pytest.raises(ValueError):ordered_loan_debt(TENANT,(installment(tenant=OTHER),))


def test_invalid_policy_is_not_auto_applied_to_cota():
    with pytest.raises(ValueError):
        LoanArrearsPolicy(Decimal("-0.01"),1000,"2027-policy")
    with pytest.raises(ValueError):
        LoanArrearsPolicy(Decimal("0.20"),-1,"2027-policy")
    with pytest.raises(ValueError):
        LoanArrearsPolicy(Decimal("0.20"),1000,"")
    assert POLICY.contract_revision=="owner-policy-2027"


def test_partial_payment_never_allocates_future_interest():
    q=quote_loan_arrears(installment(principal=10000,interest=0),DUE,POLICY)
    p=apply_partial_loan_payment(q,100)
    assert p.paid_interest_cents==0
    assert p.paid_mora_cents==0
    assert p.paid_fine_cents==0
    assert p.paid_principal_cents==100


@pytest.mark.parametrize("bad",[0,-1,True,1.01])
def test_invalid_payment_rejected(bad):
    q=quote_loan_arrears(installment(),DUE,POLICY)
    with pytest.raises(ValueError):
        apply_partial_loan_payment(q,bad)


def test_overpayment_rejected():
    q=quote_loan_arrears(installment(),DUE,POLICY)
    with pytest.raises(ValueError):
        apply_partial_loan_payment(q,q.total_due_cents+1)
