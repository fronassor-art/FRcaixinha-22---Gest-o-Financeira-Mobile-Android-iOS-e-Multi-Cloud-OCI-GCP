from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import onboarding_v23 as api

def test_runtime_always_blocks_even_with_ci_environment(monkeypatch):
    for key,value in {"GITHUB_ACTIONS":"true","FRCAIXINHA_CI_ISOLATED":"1",
                      "PIX_REAL":"OFF","PAGAMENTOS_REAIS":"OFF","ATIVACAO_REAL":"OFF"}.items():
        monkeypatch.setenv(key,value)
    app=FastAPI()
    app.include_router(api.router)
    client=TestClient(app)
    prefix="/v23/onboarding"
    assert all(v is False for k,v in client.get(prefix+"/capabilities").json().items() if k!="contract")
    tenant,cycle,doc=map(str,(uuid4(),uuid4(),uuid4()))
    document=dict(document_id=doc,document_hash="a"*64)
    register=dict(**document,invitation_token="x"*32,verification_token="y"*32,accepted=True,
                  name="CI fictício",cpf="12345678901",phone="11999990000",password="secret-CI-test-only")
    paths=[
      ("/master/invitations",dict(**document,email="ci@example.invalid",master_password="secret-CI-test-only")),
      ("/admin/registration",dict(**register,tenant_name="CI")),
      (f"/tenants/{tenant}/checkout",dict(price_version=doc,period="MONTHLY",accepted_cents=100,accepted=True)),
      (f"/tenants/{tenant}/contract-b",dict(**document,accepted=True)),
      (f"/tenants/{tenant}/cycles/{cycle}/member-invitations",dict(email="ci@example.invalid",joined="2027-01-10",quotas=2)),
      ("/member/registration",dict(**register,cycle=cycle,policy_hash="b"*64,joined="2027-01-10",quotas=2)),
    ]
    for path,body in paths:
        response=client.post(prefix+path,json=body)
        assert response.status_code==503
        assert response.headers["cache-control"]=="no-store"
        assert "secret-CI-test-only" not in response.text
    for path in (f'/master/documents/{doc}',f'/tenants/{tenant}/documents/{doc}',f'/tenants/{tenant}/offers',f'/tenants/{tenant}/checkout/{doc}'):
        assert client.get(prefix+path).status_code==503
    assert client.post(prefix+'/invitation-terms',json=dict(invitation_token='x'*32,verification_token='y'*32)).status_code==503
    # Test schema and redaction with a fixture that cannot execute a write.
    def never(*args):
        raise AssertionError("invalid payload reached executor")
    app.dependency_overrides[api.unreleased_onboarding]=lambda:never
    for value in (False,1,"true",None):
        response=client.post(prefix+"/admin/registration",json=dict(**{k:v for k,v in register.items() if k!="accepted"},accepted=value,tenant_name="CI"))
        assert response.status_code==422
        assert "secret-CI-test-only" not in response.text and "xxxxxxxx" not in response.text
        assert response.headers["cache-control"]=="no-store"
    response=client.post(prefix+f"/tenants/{tenant}/checkout",json=dict(price_version=doc,period="MONTHLY",accepted_cents=1.5,accepted=True))
    assert response.status_code==422
    response=client.post(prefix+f"/tenants/{tenant}/checkout",json=dict(price_version=doc,period="MONTHLY",accepted_cents=100,accepted=True))
    assert response.status_code==401
