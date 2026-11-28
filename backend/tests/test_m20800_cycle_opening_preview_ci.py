"""M20800 opening preview: administrator choice without database mutation."""
import uuid
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.dependencies import AuthenticatedSession
from app.routers.cycle_contribution_price import CycleOpeningPreviewRequest, opening_preview
TENANT=uuid.UUID("00000000-0000-4000-8000-0000000000a1")
OTHER=uuid.UUID("00000000-0000-4000-8000-0000000000b1")
ADMIN=uuid.UUID("00000000-0000-4000-8000-0000000000a2")
def actor(role="TENANT_ADMIN",tenant=TENANT):
 return AuthenticatedSession(str(ADMIN),role,str(tenant) if tenant else None,
   "ci@example.invalid","Pessoa CI",role=="MASTER")
def payload(amount=20000,year=2030):
 return CycleOpeningPreviewRequest(year=year,amount_cents=amount,
   reason="Valor escolhido formalmente pelo administrador")
class ReadOnly:
 def __init__(self,years=()):
  self.calls=[];self.years=years
 async def fetchrow(self,query,*args):
  self.calls.append(query)
  return {"id":TENANT,"status":"ATIVO","admin_user_id":ADMIN}
 async def fetchval(self,query,*args):
  self.calls.append(query);return 1
 async def fetch(self,query,*args):
  self.calls.append(query)
  return [{"year":year,"status":"ABERTO"} for year in self.years]
 async def execute(self,*args):
  raise AssertionError("Preview must not modify database")
@pytest.mark.asyncio
async def test_preflight_is_readonly_and_explicit_200():
 db=ReadOnly()
 out=await opening_preview(TENANT,payload(),actor(),db)
 assert out["amount_cents"]==20000
 assert out["minimum_amount_cents"]==15000
 assert out["preconditions_satisfied"] is True
 assert out["cycle_creation_enabled"] is False
 assert out["historical_obligations_unchanged"] is True
 assert out["financial_effect"] is False
 assert len(db.calls)==3
 assert all("INSERT " not in q and "UPDATE " not in q for q in db.calls)
@pytest.mark.asyncio
async def test_reject_existing_and_unclosed_cycle():
 db=ReadOnly((2030,))
 out=await opening_preview(TENANT,payload(),actor(),db)
 assert "YEAR_ALREADY_EXISTS" in out["blocked_reasons"]
 assert "PREVIOUS_CYCLE_NOT_CLOSED" in out["blocked_reasons"]
@pytest.mark.asyncio
async def test_unauthorized_roles_blocked_before_database_calls():
 for who in [actor("MASTER",None),actor("TENANT_MEMBER"),actor("TENANT_ADMIN",OTHER)]:
  db=ReadOnly()
  with pytest.raises(HTTPException) as e:
   await opening_preview(TENANT,payload(),who,db)
  assert e.value.status_code==403 and db.calls==[]
def test_minimum_and_reason_are_mandatory():
 with pytest.raises(ValidationError): payload(amount=10000)
 with pytest.raises(ValidationError): payload(amount=14999)
 with pytest.raises(ValidationError):
  CycleOpeningPreviewRequest(year=2030,amount_cents=15000,reason="curto")
 assert payload(amount=15000).amount_cents==15000
