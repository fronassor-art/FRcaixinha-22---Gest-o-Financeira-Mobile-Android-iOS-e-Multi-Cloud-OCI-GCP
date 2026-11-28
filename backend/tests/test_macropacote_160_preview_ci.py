"""Macropacote 160: tests without modifying any real database."""
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import AuthenticatedSession,get_current_session
from app.database import get_rls_db_connection
TA='123e4567-e89b-42d3-a456-426614174000'
TB='223e4567-e89b-42d3-a456-426614174001'
USER='323e4567-e89b-42d3-a456-426614174002'
class DB:
    def __init__(self,change=None):
        self.calls=[]
        self.row={'contribution_count':12,'pending_count':12,
                  'total_due':Decimal('1800.00'),'amount_paid_recorded':Decimal('0.00')}
        if change: self.row.update(change)
    async def fetchrow(self,sql,*params):
        self.calls.append((sql,params))
        return self.row
def go(role,session_tenant,endpoint,change=None):
    db=DB(change)
    master=role=='MASTER'
    app.dependency_overrides[get_current_session]=lambda:AuthenticatedSession(
        USER,role,session_tenant,'ci@example.invalid','CI',master)
    app.dependency_overrides[get_rls_db_connection]=lambda:db
    try:
        with TestClient(app) as c:
            response=c.get(f'/api/v1/tenants/{TA}/contributions/annual-preview/{endpoint}?year=2027')
    finally:
        app.dependency_overrides.clear()
    return response,db
def test_authorized_read_only():
    for role,endpoint in [('TENANT_MEMBER','me'),('TENANT_ADMIN','admin')]:
        r,db=go(role,TA,endpoint)
        assert r.status_code==200,r.text
        data=r.json()
        assert data['remaining_due']=='1800.00' and data['profit_amount'] is None
        assert data['result_status']=='PREVIA_NAO_E_LIQUIDACAO'
        assert len(db.calls)==1
        sql,params=db.calls[0]
        assert str(params[0])==TA and 'SELECT ' in sql
        assert not any(x in sql.upper() for x in ('INSERT ','UPDATE ','DELETE ','TRUNCATE '))
        if endpoint=='me':
            assert "m.user_id=$2" in sql and "m.status='ATIVA'" in sql
        else:
            assert "m.role='TENANT_MEMBER'" in sql
def test_forbidden_never_queries_db():
    for role,tenant,endpoint in [
        ('MASTER',None,'me'),('MASTER',None,'admin'),
        ('TENANT_ADMIN',TB,'admin'),('TENANT_MEMBER',TB,'me'),
        ('TENANT_MEMBER',TA,'admin'),('TENANT_ADMIN',TA,'me')
    ]:
        r,db=go(role,tenant,endpoint)
        assert r.status_code==403,(role,tenant,endpoint,r.text)
        assert not db.calls
def test_invalid_counts_or_money_fail_closed():
    for change in [
        {'pending_count':13},{'pending_count':-1},{'contribution_count':-1},
        {'contribution_count':12.5},{'total_due':Decimal('-1.00')},
        {'amount_paid_recorded':Decimal('1800.01')},
        {'amount_paid_recorded':Decimal('NaN')},
        {'total_due':Decimal('Infinity')}
    ]:
        for role,endpoint in [('TENANT_MEMBER','me'),('TENANT_ADMIN','admin')]:
            r,db=go(role,TA,endpoint,change)
            assert r.status_code==503,(change,r.text)
            assert len(db.calls)==1
