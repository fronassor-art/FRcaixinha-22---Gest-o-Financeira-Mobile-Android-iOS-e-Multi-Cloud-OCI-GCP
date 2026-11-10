"""M37446: mobile UI/API integration contract tests, zero actual DB effects."""
from pathlib import Path
import pytest
from fastapi import HTTPException
from uuid import UUID,uuid4
from app.dependencies import AuthenticatedSession
from app.routers.cycle_contribution_price import CycleOpeningPreviewRequest,opening_preview

TENANT=UUID("00000000-0000-4000-8000-0000000000a1")
ADMIN=UUID("00000000-0000-4000-8000-0000000000a2")
def actor(role="TENANT_ADMIN",tenant=TENANT):
 return AuthenticatedSession(str(ADMIN),role,str(tenant) if tenant else None,
     "ci@example.invalid","Synthetic admin",role=="MASTER")
class PreviewReadOnly:
 def __init__(self,ready=True):
  self.calls=[]
  self.ready=ready
 async def fetchrow(self,sql,*args):
  self.calls.append(sql)
  return {"id":TENANT,"status":"ATIVO","admin_user_id":ADMIN}
 async def fetchval(self,sql,*args):
  self.calls.append(sql)
  return self.ready if "to_regprocedure" in sql else 1
 async def fetch(self,sql,*args):
  self.calls.append(sql)
  return []
 async def execute(self,*args):
  raise AssertionError("No DML should occur in opening preview")

@pytest.mark.asyncio
@pytest.mark.parametrize("cents",[15000,20000,32500])
async def test_real_preview_function_is_readonly_admin_only(monkeypatch,cents):
 db=PreviewReadOnly()
 monkeypatch.delenv("FR_FINANCE_CYCLE_OPEN_ENABLED",raising=False)
 req=CycleOpeningPreviewRequest(year=2030,amount_cents=cents,
  reason="Valor escolhido explicitamente pelo administrador")
 result=await opening_preview(TENANT,req,actor(),db)
 assert result["year"]==2030 and result["amount_cents"]==cents
 assert result["cycle_creation_enabled"] is False
 assert result["historical_obligations_unchanged"] is True
 assert result["financial_effect"] is False
 assert all("INSERT " not in s and "UPDATE " not in s for s in db.calls)

@pytest.mark.asyncio
@pytest.mark.parametrize("role,tenant",[
 ("MASTER",None),("TENANT_MEMBER",TENANT),("TENANT_ADMIN",uuid4())
])
async def test_roles_and_cross_tenant_never_query_preview_db(monkeypatch,role,tenant):
 monkeypatch.delenv("FR_FINANCE_CYCLE_OPEN_ENABLED",raising=False)
 db=PreviewReadOnly()
 req=CycleOpeningPreviewRequest(year=2030,amount_cents=15000,
  reason="Administrador confirma uma escolha financeira expressa")
 with pytest.raises(HTTPException) as err:
  await opening_preview(TENANT,req,actor(role,tenant),db)
 assert err.value.status_code==403
 assert db.calls==[]

def test_client_has_no_preset_and_requires_validated_preview_reason():
 root=Path(__file__).resolve().parents[2]
 src=(root/"src/components/CycleOpeningPreviewPanel.tsx").read_text()
 api=(root/"src/services/financialApiService.ts").read_text()
 boundary=(root/"src/services/cycleOpeningBoundary.ts").read_text()
 assert "onChange={e=>{invalidate();setReason(e.target.value);" in src
 assert "openingPreviewMatchesForm(preview,intent" in src
 assert "revision.current" in src
 assert "authService.isSessionSnapshotCurrent" in src
 assert "assertTenantReadScope(this.currentTenantReader(),tenantId,'MEMBERS');" in api
 assert "function openingPreviewMatchesForm(" in boundary
 assert "useState('150')" not in src
