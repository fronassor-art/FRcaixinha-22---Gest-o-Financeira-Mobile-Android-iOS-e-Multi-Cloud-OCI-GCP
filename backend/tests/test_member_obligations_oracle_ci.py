"""M1401–M1560: obrigações por membro, centavos exatos, sem dinheiro real."""
from dataclasses import replace
from datetime import date,datetime,timezone
from uuid import UUID
import pytest

from app.member_obligation_audit import (
    ContributionRecord,LoanRecord,InstallmentRecord,
    audit_member_obligations, MAX_ROWS
)

T=UUID(int=170001)
B=UUID(int=170002)
C=UUID(int=170003)
M=UUID(int=170004)
L=UUID(int=170005)
D=date(2027,2,10)

def contribution(amount=15000,paid=0,status="PENDENTE",
                 *,id=101,month=2):
    return ContributionRecord(UUID(int=id),T,C,M,f"2027-{month:02d}",
       date(2027,month,10),amount,paid,status)

def loan(status="SOLICITADO",*,id=L,tenant=T,cycle=C,member=M):
    return LoanRecord(id,tenant,cycle,member,status,
       datetime(2027,1,20,tzinfo=timezone.utc)
       if status in ("DESEMBOLSADO","INADIMPLENTE") else None)

def installment(principal=8000,interest=2000,paid_principal=0,
                paid_interest=0,status="PENDENTE",*,id=301,
                number=1,month=2,loan_id=L):
    return InstallmentRecord(
        UUID(int=id),T,loan_id,number,date(2027,month,10),
        principal,interest,principal+interest,paid_principal,paid_interest,
        0,0,status,
    )

def assess(*,contrib=None,loans=None,installments=None,as_of=date(2027,2,11)):
    return audit_member_obligations(T,C,M,2027,as_of,
        tuple(contrib or ()),
        tuple(loans or ()),
        tuple(installments or ()),
    )

def test_proposal_is_never_borrowed_or_receivable_money():
    r=assess(contrib=[contribution()],loans=[loan()],
             installments=[installment()])
    assert r.loan_proposal_count==1
    assert r.loan_active_count==0
    assert r.loan_now_principal_cents==0
    assert r.loan_now_interest_cents==0
    assert r.loan_future_interest_cents==0
    assert r.registered_now_open_cents==15000
    assert r.status=="REGISTERED_ONLY_NOT_RECONCILED"
    assert r.net_exit_restitution_cents is None
    assert r.capital_reconciled_cents is None
    assert r.accrued_mora_cents is None and r.accrued_fine_cents is None
    assert r.profit_eligible is None
    assert not r.bank_reconciled and not r.payout_authorized
    assert not r.sanction_applied and not r.closing_authorized


def test_active_loan_due_and_future_interest_are_separated():
    r=assess(contrib=[contribution()],loans=[loan("DESEMBOLSADO")],
      installments=[installment(),installment(principal=7000,interest=1000,
                          id=302,number=2,month=3)])
    assert r.loan_now_principal_cents==8000
    assert r.loan_now_interest_cents==2000
    assert r.loan_future_principal_cents==7000
    assert r.loan_future_interest_cents==1000
    assert r.registered_now_open_cents==25000
    assert r.loan_overdue_installment_count==1
    assert not r.payout_authorized


@pytest.mark.parametrize("paid",range(0,151))
def test_151_partial_contribution_cents_exactly_preserved(paid):
    status=("PENDENTE" if paid==0 else
            "QUITADA" if paid==150 else "PARCIAL")
    r=assess(contrib=[contribution(amount=150,paid=paid,status=status)])
    assert r.contribution_due_cents==150
    assert r.contribution_paid_recorded_cents==paid
    assert r.contribution_open_cents==150-paid
    assert r.contribution_now_open_cents==150-paid
    assert r.registered_now_open_cents==150-paid
    assert r.contribution_overdue_count==(1 if paid<150 else 0)


@pytest.mark.parametrize("date_offset",range(1,121))
def test_120_asof_days_do_not_accelerate_future_interest(date_offset):
    as_of=date.fromordinal(D.toordinal()+date_offset-60)
    r=assess(loans=[loan("DESEMBOLSADO")],
             installments=[installment()],as_of=as_of)
    due=as_of>=D
    assert r.loan_now_principal_cents==(8000 if due else 0)
    assert r.loan_now_interest_cents==(2000 if due else 0)
    assert r.loan_future_principal_cents==(0 if due else 8000)
    assert r.loan_future_interest_cents==(0 if due else 2000)
    assert r.loan_overdue_installment_count==(1 if as_of>D else 0)
    assert r.net_exit_restitution_cents is None


@pytest.mark.parametrize("p",range(1,101))
def test_100_partial_loan_principal_is_never_double_counted(p):
    principal_paid=p
    r=assess(loans=[loan("DESEMBOLSADO")],installments=[
        installment(paid_principal=principal_paid,paid_interest=0,status="PARCIAL")
    ])
    assert r.loan_now_principal_cents==8000-p
    assert r.loan_now_interest_cents==2000
    assert r.registered_now_open_cents==10000-p
    assert r.accrued_mora_cents is None


@pytest.mark.parametrize("n",range(0,101))
def test_101_registered_totals_over_multiple_competences(n):
    rows=[contribution(amount=15000,paid=15000 if month<=n%12 else 0,
           status="QUITADA" if month<=n%12 else "PENDENTE",
           id=100+month,month=month) for month in range(1,13)]
    r=assess(contrib=rows,as_of=date(2027,12,31))
    assert r.contribution_count==12
    assert r.contribution_due_cents==180000
    assert r.contribution_paid_recorded_cents==15000*(n%12)
    assert r.contribution_open_cents==15000*(12-n%12)
    assert r.registered_now_open_cents==r.contribution_open_cents


@pytest.mark.parametrize("status",["SOLICITADO","APROVADO","RESERVADO"])
def test_every_loan_proposal_excluded_even_if_schedule_exists(status):
    r=assess(loans=[loan(status)],installments=[installment()])
    assert r.loan_proposal_count==1
    assert r.loan_now_principal_cents==0
    assert r.loan_future_interest_cents==0


@pytest.mark.parametrize("status",["DESEMBOLSADO","INADIMPLENTE"])
def test_active_loan_with_no_installment_fails_to_claim_complete_debt(status):
    r=assess(loans=[loan(status)])
    assert r.loan_unscheduled_count==1
    assert r.status=="INCOMPLETE_REGISTERED_LOAN_SCHEDULE"
    assert not r.payout_authorized


def test_closed_loan_with_remaining_principal_is_inconsistent():
    with pytest.raises(ValueError):
        assess(loans=[loan("QUITADO")],installments=[installment()])


def test_closed_loan_fully_paid_is_not_new_debt():
    r=assess(loans=[loan("QUITADO")],
      installments=[installment(paid_principal=8000,paid_interest=2000,
                                status="QUITADA")])
    assert r.loan_closed_count==1
    assert r.registered_now_open_cents==0


def test_zero_loan_payment_cannot_be_marked_partial_or_settled():
    with pytest.raises(ValueError):
        installment(status="PARCIAL")
    with pytest.raises(ValueError):
        installment(status="QUITADA")


@pytest.mark.parametrize("field,value",[
   ("principal_cents",-1),
   ("interest_cents",-1),
   ("total_cents",999),
   ("paid_principal_cents",9999),
   ("paid_interest_cents",9999),
   ("status","FORGIVEN"),
   ("number",0),
   ("paid_mora_cents",-1),
   ("paid_fine_cents",True),
])
def test_invalid_loan_installments_rejected(field,value):
    with pytest.raises(ValueError):
        replace(installment(),**{field:value})


@pytest.mark.parametrize("role",["QUITADA","PARCIAL","WRONG"])
def test_contribution_status_must_match_exact_amount(role):
    with pytest.raises(ValueError):
        contribution(paid=100,status=role)


@pytest.mark.parametrize("key",["tenant_id","cycle_id","membership_id"])
def test_cross_tenant_cycle_or_member_contribution_is_rejected(key):
    c=contribution()
    new=replace(c,**{key:UUID(int=999)})
    with pytest.raises(ValueError):
        assess(contrib=[new])


@pytest.mark.parametrize("key",["tenant_id","cycle_id","membership_id"])
def test_cross_tenant_cycle_or_member_loan_is_rejected(key):
    new=replace(loan("DESEMBOLSADO"),**{key:UUID(int=999)})
    with pytest.raises(ValueError):
        assess(loans=[new])


def test_duplicate_contribution_ids_and_competence_rejected():
    c=contribution()
    with pytest.raises(ValueError):
        assess(contrib=[c,c])
    with pytest.raises(ValueError):
        assess(contrib=[c,replace(c,id=UUID(int=501))])


def test_duplicate_loan_and_installment_numbers_rejected():
    ln=loan("DESEMBOLSADO")
    i=installment()
    with pytest.raises(ValueError):
        assess(loans=[ln,ln])
    with pytest.raises(ValueError):
        assess(loans=[ln],installments=[i,i])
    with pytest.raises(ValueError):
        assess(loans=[ln],installments=[i,replace(i,id=UUID(int=999))])


def test_orphan_installment_and_cross_tenant_installment_rejected():
    with pytest.raises(ValueError):
        assess(installments=[installment()])
    with pytest.raises(ValueError):
        assess(loans=[loan()],installments=[
            replace(installment(),tenant_id=B)
        ])


def test_limits_block_truncated_aggregate_not_claim_empty():
    with pytest.raises(ValueError):
        audit_member_obligations(T,C,M,2027,date(2027,2,11),
                                 tuple(),tuple(),tuple([installment()]*501))


def test_loan_due_today_not_overdue_but_due_on_calendar():
    r=assess(loans=[loan("DESEMBOLSADO")],
      installments=[installment()],as_of=D)
    assert r.loan_now_principal_cents==8000
    assert r.loan_overdue_installment_count==0


def test_contribution_future_does_not_enter_due_now():
    r=assess(contrib=[contribution(month=3,id=202)],as_of=date(2027,2,11))
    assert r.contribution_open_cents==15000
    assert r.contribution_now_open_cents==0
    assert r.registered_now_open_cents==0


def test_unpaid_fines_do_not_reduce_principal_or_imply_repayment():
    i=replace(installment(),paid_fine_cents=1000,paid_mora_cents=400)
    r=assess(loans=[loan("DESEMBOLSADO")],installments=[i])
    assert r.loan_now_principal_cents==8000
    assert r.loan_now_interest_cents==2000
    assert r.accrued_mora_cents is None and r.accrued_fine_cents is None


def test_loan_with_disbursement_without_tz_rejected():
    with pytest.raises(ValueError):
        loan("DESEMBOLSADO").__class__(L,T,C,M,"DESEMBOLSADO",
                                         datetime(2027,1,20))
