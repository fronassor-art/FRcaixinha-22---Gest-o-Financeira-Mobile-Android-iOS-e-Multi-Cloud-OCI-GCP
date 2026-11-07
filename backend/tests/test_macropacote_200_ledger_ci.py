"""Macropacote 200 — 20 invariantes contábeis sem tocar no PostgreSQL local."""
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.dependencies import AuthenticatedSession
from app.routers.ledger import get_ledger_integrity_preview
from app.routers.audit import create_tenant_audit_event
from app.routers.closings import close_cycle,capital_days_weight
from app.models import AuditEventCreatePayload,CycleClosePayload
from app.annual_allocation_preview import annual_allocation_preview
from datetime import date

T=str(uuid4())
B=str(uuid4())
U=str(uuid4())
def actor(role='TENANT_ADMIN',tenant=T):
    return AuthenticatedSession(U,role,tenant,'synthetic@example.invalid','CI',role=='MASTER')
def row(**changes):
    data={
        'transaction_id':uuid4(),'entry_count':2,'debit_entries':1,
        'credit_entries':1,'debit_cents':500,'credit_cents':500,
        'invalid_entries':0
    }
    return {**data,**changes}
class DB:
    def __init__(self,rows=None):
        self.rows=[row()] if rows is None else rows
        self.calls=[]
    async def fetch(self,sql,*params):
        self.calls.append((sql,params))
        return self.rows
    async def execute(self,*_):
        raise AssertionError('Prévia nunca escreve no banco')
    async def fetchrow(self,*_):
        raise AssertionError('Nenhuma consulta extra autorizada')

@pytest.mark.asyncio
async def test_balanced_ledger_preview_has_no_bank_claim_or_financial_details():
    db=DB([row(),row()])
    result=await get_ledger_integrity_preview(T,actor(),db)
    assert result.source=='POSTGRESQL_RLS'
    assert result.scope=='TENANT_ADMIN_READ_ONLY'
    assert result.tenant_id==T
    assert result.status=='BALANCED'
    assert result.checked_transactions==2
    assert result.balanced_transactions==2
    assert result.review_required_transactions==0
    assert result.bank_reconciled is False
    assert result.financial_closing_authorized is False
    assert len(db.calls)==1
    sql,args=db.calls[0]
    assert sql.lstrip().startswith('SELECT')
    assert 'WHERE t.tenant_id=$1' in sql
    assert 'e.tenant_id=t.tenant_id' in sql
    assert 'a.tenant_id=t.tenant_id' in sql
    assert 'LIMIT 501' in sql
    assert args==(uuid4() if False else __import__('uuid').UUID(T),)

@pytest.mark.asyncio
async def test_empty_ledger_never_claims_consistency_or_reconciliation():
    db=DB([])
    r=await get_ledger_integrity_preview(T,actor(),db)
    assert r.status=='NO_TRANSACTIONS'
    assert r.balanced_transactions==0
    assert r.bank_reconciled is False

@pytest.mark.asyncio
async def test_imbalanced_or_invalid_postings_are_review_required():
    cases=[
        row(debit_cents=501),row(debit_cents=0),row(credit_cents=0),
        row(entry_count=1,credit_entries=0),
        row(entry_count=3,debit_entries=1,credit_entries=1),
        row(invalid_entries=1),row(debit_entries=0),
        row(credit_entries=0)
    ]
    for bad in cases:
        db=DB([row(),bad])
        result=await get_ledger_integrity_preview(T,actor(),db)
        assert result.status=='REVIEW_REQUIRED'
        assert result.checked_transactions==2
        assert result.review_required_transactions==1

@pytest.mark.asyncio
async def test_malformed_or_excessive_ledger_fails_closed():
    for rows in [
        [row(debit_cents='500')],
        [row(debit_cents=-1)],
        [row(entry_count=True)],
        [row(invalid_entries=None)],
        [row(transaction_id='')],
        [dict(row(),debit_entries=-1)],
        [row(transaction_id=None)],
        [row(transaction_id='dup'),row(transaction_id='dup')],
        [row() for _ in range(501)]
    ]:
        with pytest.raises(HTTPException) as err:
            await get_ledger_integrity_preview(T,actor(),DB(rows))
        assert err.value.status_code==503

@pytest.mark.asyncio
async def test_master_member_and_other_tenant_get_no_sql():
    for role,tenant in [('MASTER',None),('TENANT_MEMBER',T),('TENANT_ADMIN',B)]:
        db=DB()
        with pytest.raises(HTTPException) as err:
            await get_ledger_integrity_preview(T,actor(role,tenant),db)
        assert err.value.status_code==403
        assert db.calls==[]

@pytest.mark.asyncio
async def test_manual_audit_events_not_accepted_as_authoritative():
    payload=AuditEventCreatePayload(action='PAID',object_type='PAYMENT',
        object_id='synthetic',reason='Unverified',evidence_ref='CI_ONLY')
    for role,tenant,status in [
        ('TENANT_ADMIN',T,503),('TENANT_MEMBER',T,403),
        ('MASTER',None,403),('TENANT_ADMIN',B,403)
    ]:
        db=DB()
        with pytest.raises(HTTPException) as err:
            await create_tenant_audit_event(T,payload,actor(role,tenant),db)
        assert err.value.status_code==status and db.calls==[]

@pytest.mark.asyncio
async def test_real_cycle_close_stays_blocked_without_database_reads():
    payload=CycleClosePayload(cycle_id=str(uuid4()))
    for role,tenant,code in [
        ('TENANT_ADMIN',T,503),('TENANT_MEMBER',T,403),
        ('MASTER',None,403),('TENANT_ADMIN',B,403)
    ]:
        db=DB()
        with pytest.raises(HTTPException) as err:
            await close_cycle(T,payload,actor(role,tenant),db)
        assert err.value.status_code==code and db.calls==[]

def test_capital_days_pure_example_never_extends_into_settlement():
    assert capital_days_weight(Decimal('100'),date(2027,1,10),date(2027,12,31))==Decimal('35500.0000')
    assert capital_days_weight(Decimal('100'),date(2028,1,10),date(2027,12,31))==Decimal('0.0000')

def test_allocation_15_85_and_exact_cents_in_preparation():
    r=annual_allocation_preview(Decimal('100.00'),{'a':Decimal('1'),'b':Decimal('2')})
    assert r['state']=='PREVIEW_NOT_SETTLED'
    assert r['admin_provisional_cents']==1500
    assert r['member_pool_cents']==8500
    assert sum(r['member_shares_cents'].values())==8500
    assert r['segregated_undistributed_cents']==0

def test_largest_remainder_tie_is_deterministic_and_no_payment():
    r=annual_allocation_preview(Decimal('0.01'),{'z':1,'a':1,'m':1})
    assert r['admin_provisional_cents']==0
    assert r['member_pool_cents']==1
    assert r['member_shares_cents']=={'a':1,'m':0,'z':0}
    assert r['state']=='PREVIEW_NOT_SETTLED'

def test_no_eligible_weights_are_held_segregated_not_paid():
    for weights in ({},{'m1':0,'m2':0}):
        r=annual_allocation_preview(Decimal('100.00'),weights)
        assert r['member_pool_cents']==8500
        assert r['segregated_undistributed_cents']==8500
        assert sum(r['member_shares_cents'].values())==0

@pytest.mark.parametrize('amount,weights',[
    ('100.001',{'a':1}),('-1.00',{'a':1}),('NaN',{'a':1}),
    ('Infinity',{'a':1}),('1000000000.01',{'a':1}),
    ('1.00',{'a':-1}),('1.00',{'a':Decimal('NaN')}),
    ('1.00',{'a':'Infinity'}),('1.00',{'':1}),
    ('1.00',[('a',1)])
])
def test_invalid_allocation_inputs_fail_closed(amount,weights):
    with pytest.raises(ValueError):
        annual_allocation_preview(amount,weights)
