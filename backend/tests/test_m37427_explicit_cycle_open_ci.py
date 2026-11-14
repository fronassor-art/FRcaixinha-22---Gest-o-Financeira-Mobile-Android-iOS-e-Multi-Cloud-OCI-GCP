"""M37427: explicit admin-selected price at cycle opening, flag stays off by default."""
import uuid
import pytest
from datetime import date
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request
from app.dependencies import AuthenticatedSession
from app.routers.cycle_contribution_price import (
 CycleOpeningCommitRequest,CycleOpeningPreviewRequest,commit_cycle_opening,opening_preview,
)

TENANT=uuid.UUID("00000000-0000-4000-8000-0000000000a1")
ADMIN=uuid.UUID("00000000-0000-4000-8000-0000000000a2")
def actor(role="TENANT_ADMIN",tenant=TENANT):
 return AuthenticatedSession(str(ADMIN),role,str(tenant) if tenant else None,
  "example@invalid.test","Synthetic Admin",role=="MASTER")
def req():
 return Request({"type":"http","method":"POST","path":"/api/v1/tenants/test/cycle-contribution-price/opening",
  "headers":[(b"authorization",b"Bearer synthetic-ci-token-at-least-32-characters-00000")],
  "query_string":b""})
def payload(amount=20000):
 return CycleOpeningCommitRequest(year=2030,amount_cents=amount,
  reason="Valor explicitamente escolhido pelo administrador da caixinha",
  idempotency_key=uuid.uuid4())
class FakeDB:
 def __init__(self):self.calls=[]
 async def fetchrow(self,sql,*args):
  self.calls.append((sql,args))
  if "cycle_open_create" in sql:
   return {"opened_cycle_id":uuid.uuid4(),"opened_policy_id":uuid.uuid4(),
    "opened_year":2030,"opened_amount_cents":20000,"opening_status":"CREATED"}
  return {"id":TENANT,"status":"ATIVO","admin_user_id":ADMIN}
 async def fetchval(self,sql,*args):
  self.calls.append((sql,args))
  return True if "to_regprocedure" in sql else 1
 async def fetch(self,sql,*args):
  self.calls.append((sql,args));return []

def test_under_contract_minimum_is_invalid():
 for cents in (0,10000,14999,1000001):
  with pytest.raises(ValidationError):
   payload(cents)
 assert payload(15000).amount_cents==15000
 assert payload(20000).amount_cents==20000

@pytest.mark.asyncio
async def test_flag_off_does_not_touch_db(monkeypatch):
 monkeypatch.delenv("FR_FINANCE_CYCLE_OPEN_ENABLED",raising=False)
 db=FakeDB()
 with pytest.raises(HTTPException) as exc:
  await commit_cycle_opening(TENANT,payload(),req(),actor(),db)
 assert exc.value.status_code==503 and db.calls==[]

@pytest.mark.asyncio
async def test_cross_tenant_master_member_cannot_open(monkeypatch):
 monkeypatch.setenv("FR_FINANCE_CYCLE_OPEN_ENABLED","YES")
 for who in (actor("MASTER",None),actor("TENANT_MEMBER"),actor("TENANT_ADMIN",uuid.uuid4())):
  db=FakeDB()
  with pytest.raises(HTTPException) as exc:
   await commit_cycle_opening(TENANT,payload(),req(),who,db)
  assert exc.value.status_code==403 and db.calls==[]

@pytest.mark.asyncio
async def test_explicit_amount_server_function_and_receipt(monkeypatch):
 monkeypatch.setenv("FR_FINANCE_CYCLE_OPEN_ENABLED","YES")
 db=FakeDB()
 p=payload()
 r=await commit_cycle_opening(TENANT,p,req(),actor(),db)
 assert r["amount_cents"]==20000 and r["year"]==2030
 assert r["source"]=="POSTGRESQL_AUTHENTICATED_ADMIN_M044"
 assert r["opening_audit_persisted"] is True
 assert r["existing_contributions_repriced"] is False
 assert r["payments_executed"] is False
 assert len(db.calls)==1 and "public.cycle_open_create(" in db.calls[0][0]
 assert db.calls[0][1][3]==20000 and db.calls[0][1][5]==p.idempotency_key

@pytest.mark.asyncio
async def test_preview_only_when_flag_enabled_and_m044_present(monkeypatch):
 db=FakeDB()
 monkeypatch.delenv("FR_FINANCE_CYCLE_OPEN_ENABLED",raising=False)
 p=CycleOpeningPreviewRequest(year=2030,amount_cents=30000,
  reason="Valor escolhido pelo administrador no inicio do ciclo")
 a=await opening_preview(TENANT,p,actor(),db)
 assert a["amount_cents"]==30000 and a["cycle_creation_enabled"] is False
 assert not any("cycle_open_create" in sql for sql,_ in db.calls)
 db=FakeDB()
 monkeypatch.setenv("FR_FINANCE_CYCLE_OPEN_ENABLED","YES")
 b=await opening_preview(TENANT,p,actor(),db)
 assert b["cycle_creation_enabled"] is True
 assert len(db.calls)==4
 assert b["financial_effect"] is False
