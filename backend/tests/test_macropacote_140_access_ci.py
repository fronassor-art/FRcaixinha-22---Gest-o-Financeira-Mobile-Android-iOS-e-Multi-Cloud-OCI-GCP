"""Macropacote 140: guardas de papéis, rotas e fronteira multi-tenant sem banco local."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.dependencies import AuthenticatedSession,require_master,require_tenant_access,get_current_session
from app.main import app
T_A='123e4567-e89b-42d3-a456-426614174000'
T_B='223e4567-e89b-42d3-a456-426614174001'

def session(role,tenant=None,master=False):
    return AuthenticatedSession('323e4567-e89b-42d3-a456-426614174002',
        role,tenant,'ci@example.invalid','Conta de Teste',master)

def forbidden(call):
    with pytest.raises(HTTPException) as error: call()
    assert error.value.status_code==403

def test_require_master_only_governance():
    assert require_master(session('MASTER',None,True)).role=='MASTER'
    forbidden(lambda:require_master(session('MASTER',T_A,True)))
    forbidden(lambda:require_master(session('MASTER',None,False)))
    forbidden(lambda:require_master(session('TENANT_ADMIN',T_A,False)))
    forbidden(lambda:require_master(session('TENANT_MEMBER',T_A,False)))

def test_tenant_access_rejects_master_and_cross_tenant():
    forbidden(lambda:require_tenant_access(T_A,session('MASTER',None,True)))
    forbidden(lambda:require_tenant_access(T_B,session('TENANT_ADMIN',T_A)))
    forbidden(lambda:require_tenant_access(T_B,session('TENANT_MEMBER',T_A)))
    assert require_tenant_access(T_A,session('TENANT_ADMIN',T_A)).tenant_id==T_A
    assert require_tenant_access(T_A,session('TENANT_MEMBER',T_A)).tenant_id==T_A

@pytest.mark.parametrize('role,tenant,master,expected',[
    ('TENANT_MEMBER',T_A,False,403),
    ('TENANT_ADMIN',T_A,False,403),
    ('MASTER',None,False,403),
    ('MASTER',T_A,True,403),
    ('MASTER',None,True,200),
])
def test_owner_access_is_server_authorized(role,tenant,master,expected):
    app.dependency_overrides[get_current_session]=lambda:session(role,tenant,master)
    try:
        with TestClient(app) as client:
            result=client.get('/api/v1/master/owner-access')
        assert result.status_code==expected
        if expected==200:
            assert result.json()['scope']=='PLATFORM_GOVERNANCE_ONLY'
            assert result.json()['verified'] is True
    finally:
        app.dependency_overrides.clear()

@pytest.mark.parametrize('role,tenant,master',[
    ('MASTER',None,True),
    ('TENANT_ADMIN',T_A,False),
    ('TENANT_MEMBER',T_A,False),
])
def test_switch_context_stays_disabled(role,tenant,master):
    app.dependency_overrides[get_current_session]=lambda:session(role,tenant,master)
    try:
        with TestClient(app) as client:
            result=client.post('/api/v1/auth/switch-context',json={
                'target_role':'TENANT_ADMIN','target_tenant_id':T_B})
        assert result.status_code==403
    finally:
        app.dependency_overrides.clear()
