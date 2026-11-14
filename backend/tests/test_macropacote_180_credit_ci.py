"""Macropacote 180: cenários sintéticos de Price, consentimento e bloqueio financeiro."""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.routers.loans import (
    compute_price_schedule,simulate_loan_price,disburse_loan,
    repay_loan_installment,settle_loan_early
)
from app.models import LoanSimulateRequest, LoanRepayPayload
from app.dependencies import AuthenticatedSession
from app.annual_consent import ActiveMember, ConsentEvent, assess_annual_consent
TENANT=str(uuid4())
USER=str(uuid4())

def session(role='TENANT_MEMBER',tenant=TENANT):
    return AuthenticatedSession(USER,role,tenant,'ci@example.invalid','CI',role=='MASTER')
class ReadOnlyPolicy:
    def __init__(self,cycle=True,policy=True,rate='0.20',limit=6):
        self.cycle,self.policy,self.rate,self.limit=cycle,policy,rate,limit
        self.calls=[]
    async def fetchrow(self,sql,*args):
        self.calls.append((sql,args))
        if 'FROM public.cycles' in sql:
            return {'id':uuid4(),'start_date':date(2027,1,1),'end_date':date(2027,12,31)} if self.cycle else None
        if 'FROM public.policies' in sql:
            return {'monthly_interest_rate':self.rate,'max_installments':self.limit} if self.policy else None
        raise AssertionError('Unexpected SQL '+sql)
    async def execute(self,*_):
        raise AssertionError('Read-only simulation cannot write')

def test_price_decimal_and_cent_audit():
    result=compute_price_schedule(Decimal('500.00'),5,Decimal('0.20'))
    assert result.uniform_payment==Decimal('167.19')
    assert result.last_payment==Decimal('167.20')
    assert result.total_interest==Decimal('335.96')
    assert result.total_payable==Decimal('835.96')
    assert sum(x.amortization_portion for x in result.schedule)==result.principal
    assert sum(x.monthly_payment for x in result.schedule)==result.total_payable
    assert result.schedule[-1].closing_balance==Decimal('0.00')
    assert [x.due_date for x in result.schedule]==[
        '2027-01-10','2027-02-10','2027-03-10','2027-04-10','2027-05-10']

@pytest.mark.parametrize('principal,term,rate',[
    (Decimal('0.00'),5,Decimal('0.20')),
    (Decimal('50000.01'),5,Decimal('0.20')),
    (Decimal('500.001'),5,Decimal('0.20')),
    (Decimal('NaN'),5,Decimal('0.20')),
    (Decimal('Infinity'),5,Decimal('0.20')),
    (Decimal('500'),0,Decimal('0.20')),
    (Decimal('500'),7,Decimal('0.20')),
    (Decimal('500'),5,Decimal('-0.01')),
    (Decimal('500'),5,Decimal('NaN')),
    (Decimal('500'),5,Decimal('1.01')),
])
def test_price_direct_invocation_is_bounded(principal,term,rate):
    with pytest.raises(ValueError):
        compute_price_schedule(principal,term,rate)

def test_irregular_first_period_and_cycle_bounds():
    r=compute_price_schedule(Decimal('500'),5,Decimal('0.20'),
                             disbursement_date=date(2027,1,28))
    assert r.first_period_days==13
    assert r.is_irregular_first_period
    assert r.schedule[0].due_date=='2027-02-10'
    assert r.effective_first_rate==Decimal('0.08666667')
    with pytest.raises(ValueError):
        compute_price_schedule(Decimal('500'),5,Decimal('0.20'),
                               disbursement_date=date(2027,1,28),
                               first_due_date=date(2027,2,11))
    with pytest.raises(ValueError):
        compute_price_schedule(Decimal('500'),5,Decimal('0.20'),
                               disbursement_date=date(2027,11,28))

@pytest.mark.asyncio
async def test_price_policy_is_authoritative_and_read_only():
    c=ReadOnlyPolicy(rate='0.15')
    r=await simulate_loan_price(
        TENANT,LoanSimulateRequest(principal=Decimal('500'),term_months=5),
        session(),c)
    assert r.monthly_rate==Decimal('0.15')
    assert len(c.calls)==2
    assert all(x[0].lstrip().startswith('SELECT') for x in c.calls)

@pytest.mark.asyncio
async def test_denied_contexts_do_not_read_policy():
    for who in (session('MASTER',None),session('TENANT_MEMBER',str(uuid4()))):
        c=ReadOnlyPolicy()
        with pytest.raises(HTTPException) as exc:
            await simulate_loan_price(
                TENANT,LoanSimulateRequest(principal=500,term_months=5),who,c)
        assert exc.value.status_code==403
        assert c.calls==[]

@pytest.mark.asyncio
async def test_policy_contract_fail_closed():
    for opts,expected in [
        ({'cycle':False},409),({'policy':False},409),
        ({'limit':2},422),({'limit':0},503),({'limit':'6'},503),
        ({'rate':'NaN'},422),({'rate':'1.01'},422)
    ]:
        c=ReadOnlyPolicy(**opts)
        with pytest.raises(HTTPException) as err:
            await simulate_loan_price(
                TENANT,LoanSimulateRequest(principal=500,term_months=5),
                session(),c)
        assert err.value.status_code==expected,(opts,err.value.status_code)

def active(uid,mid): return ActiveMember(mid,uid)
def evt(mid,kind,at):return ConsentEvent(TENANT,2027,USER,mid,'consent-v1',kind,at)
def assess(members,events,at):
    return assess_annual_consent(tenant_id=TENANT,cycle_year=2027,
        admin_user_id=USER,members=members,events=events,
        terms_version='consent-v1',at=at)
def test_annual_consent_pure_and_revocation_wins_ties():
    now=datetime(2027,6,1,tzinfo=timezone.utc)
    a,b,c=active(USER,'adm'),active('other-1','m1'),active('other-2','m2')
    assert assess([a,b,c],[],now).reason=='ANUENCIA_PENDENTE_OU_REVOGADA'
    s1,s2=evt('m1','SIGNED',now-timedelta(days=1)),evt('m2','SIGNED',now)
    assert assess([a,b,c],[s1,s2],now).authorized
    revoked=evt('m1','REVOKED',s1.occurred_at)
    for events in ([s1,revoked,s2],[revoked,s1,s2]):
        result=assess([a,b,c],events,now)
        assert not result.authorized
        assert result.missing_membership_ids==('m1',)
    assert not assess([a,b,c],[s1,s2,evt('m2','UNKNOWN',now)],now).authorized
    assert not assess([a,b,c],[s1],now).authorized
    assert assess([a,b,b],[s1],now).reason=='VINCULOS_INVALIDOS'
    assert not assess([a,b,c],[s1,s2],datetime(2028,1,2,tzinfo=timezone.utc)).authorized

@pytest.mark.asyncio
async def test_real_disburse_repay_and_early_settlement_stay_blocked():
    class NoDB:
        async def fetchrow(self,*_):raise AssertionError('No SQL allowed')
        async def execute(self,*_):raise AssertionError('No SQL allowed')
    db=NoDB()
    for thunk in [
        lambda:disburse_loan(TENANT,str(uuid4()),session('TENANT_ADMIN'),db),
        lambda:repay_loan_installment(
            TENANT,str(uuid4()),LoanRepayPayload(amount=Decimal('10')),session(),db),
        lambda:settle_loan_early(TENANT,str(uuid4()),session(),db)
    ]:
        with pytest.raises(HTTPException) as err:
            await thunk()
        assert err.value.status_code==503
