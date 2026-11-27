from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import product_v23

def test_routes_fail_closed_without_provider():
    app=FastAPI()
    app.include_router(product_v23.router)
    client=TestClient(app)
    t,c,r=uuid4(),uuid4(),uuid4()
    prefix=f"/tenants/{t}/v23"
    assert client.get(prefix+"/capabilities").json()["available"] is False
    for path,body in [
        ("/cycles",dict(request_id=str(r),start="2026-12-10",first_due="2026-12-10",last_due="2027-11-10",closing="2027-12-20",quota_cents=100,admin_bps=1300,late_days=90,late_competences=3,mode="MANUAL",document_id=str(c))),
        (f"/cycles/{c}/admissions",dict(membership_id=str(r),joined="2026-12-10",quotas=1)),
        ("/manual-receipts",dict(request_id=str(r),contribution_id=str(c),cents=50,method="DINHEIRO",occurred="2026-12-10",reference="CI-REF",evidence_ref="CI-EVIDENCE")),
        (f"/manual-receipts/{r}/CONFIRM",dict(request_id=str(c),occurred="2026-12-10",evidence_ref="CI-EVIDENCE"))
    ]:
        assert client.post(prefix+path,json=body).status_code==503
    assert client.get(prefix+f"/manual-receipts/{r}").status_code==503
    assert client.get(prefix+f"/cycles/{c}/financial-summary").status_code==503
    assert client.get(prefix+f"/cycles/{c}/my-contributions").status_code==503
