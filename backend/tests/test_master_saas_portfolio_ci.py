"""Master comercial por tenant: somente leitura e sem vazamento patrimonial."""
from datetime import datetime, timezone
from uuid import UUID,uuid4
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import require_master
from app.database import get_rls_db_connection

class DB:
    def __init__(self):
        self.sql=[]
    async def fetchval(self, sql, *args):
        self.sql.append((sql,args))
        return 1
    async def fetch(self, sql, *args):
        self.sql.append((sql,args))
        return [dict(id=uuid4(),display_name='Caixinha Teste',tenant_status='ATIVO',
                     created_at=datetime(2026,11,3,tzinfo=timezone.utc),
                     admin_user_id=uuid4(),admin_total=2,admin_active=1,
                     licensed_plan=None,license_status=None,effective_status=None,
                     valid_from=None,valid_until=None,prepared_plan='ESSENCIAL',
                     prepared_period='ANNUAL',preparation_status='PENDING_PAYMENT',
                     prepared_at=datetime(2026,11,3,tzinfo=timezone.utc),
                     members_limit=None,quotas_limit=None)]

def test_master_sees_preparation_without_claiming_payment():
    db=DB()
    app.dependency_overrides[get_rls_db_connection]=lambda:db
    app.dependency_overrides[require_master]=lambda: object()
    try:
        with TestClient(app) as c:
            r=c.get('/api/v1/master/saas-portfolio?page=1')
        assert r.status_code==200,r.text
        result=r.json()
        assert result['boxes_limit_policy']=='NOT_DEFINED'
        assert result['tenants'][0]['licensed_plan'] is None
        assert result['tenants'][0]['prepared_plan']=='ESSENCIAL'
        assert result['tenants'][0]['admin_active']==1
        sql=' '.join(s for s,_ in db.sql).lower()
        assert 'saas_license_entitlements' in sql and 'saas_subscription_preparations' in sql
        assert all(word not in sql for word in ('ledger','contributions','loans','cpf','password_hash'))
        assert all(not any(k in item for k in ('cpf','email','balance','token','profit')) for item in result['tenants'])
    finally:
        app.dependency_overrides.clear()

def test_non_master_denied_before_sql():
    db=DB()
    app.dependency_overrides[get_rls_db_connection]=lambda:db
    def denied():
        raise HTTPException(status_code=403,detail='Master somente')
    app.dependency_overrides[require_master]=denied
    try:
        with TestClient(app) as c:
            r=c.get('/api/v1/master/saas-portfolio')
        assert r.status_code==403
        assert db.sql==[]
    finally:
        app.dependency_overrides.clear()
