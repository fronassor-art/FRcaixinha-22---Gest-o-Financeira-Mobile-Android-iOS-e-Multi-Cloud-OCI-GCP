"""M37434: preserve same database; refuse legacy development price in API."""
from pathlib import Path
import uuid
from datetime import date
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.dependencies import AuthenticatedSession
from app.routers.cycle_contribution_price import status,CycleOpeningCommitRequest
ROOT=Path(__file__).resolve().parents[2]
TENANT=uuid.UUID("00000000-0000-4000-8000-0000000000a1")
ADMIN=uuid.UUID("00000000-0000-4000-8000-0000000000a2")
def actor():
 return AuthenticatedSession(str(ADMIN),"TENANT_ADMIN",str(TENANT),"ci@example.invalid","Synthetic",False)
class DB:
 def __init__(self,amount,pending=None): self.amount=amount;self.pending=pending
 async def fetchrow(self,*args):
  return {"tenant_id":TENANT,"cycle_id":uuid.uuid4(),"cycle_year":2027,
    "start_date":date(2027,1,1),"end_date":date(2027,12,31),
    "amount_cents":self.amount,"policy_version":1,
    "registered_contributions":12,"can_edit":False,
    "blocked_reason":"COMPETENCIAS_JA_REGISTRADAS",
    "pending_requested_cents":self.pending}
@pytest.mark.asyncio
@pytest.mark.parametrize("cents",[10000,14999])
async def test_obsolete_price_not_served(cents,monkeypatch):
 import app.routers.cycle_contribution_price as p
 monkeypatch.setattr(p,"bearer_token",lambda r:"synthetic-token")
 with pytest.raises(HTTPException) as exc:
  await status(TENANT,object(),actor(),DB(cents))
 assert exc.value.status_code==409
@pytest.mark.asyncio
async def test_allowed_prices_are_not_fixed(monkeypatch):
 import app.routers.cycle_contribution_price as p
 monkeypatch.setattr(p,"bearer_token",lambda r:"synthetic-token")
 for cents in (15000,20000,32500):
  response=await status(TENANT,object(),actor(),DB(cents))
  assert response["amount_cents"]==cents
  assert response["real_payments_enabled"] is False
@pytest.mark.asyncio
async def test_obsolete_pending_price_fails_closed(monkeypatch):
 import app.routers.cycle_contribution_price as p
 monkeypatch.setattr(p,"bearer_token",lambda r:"synthetic-token")
 with pytest.raises(HTTPException) as exc:
  await status(TENANT,object(),actor(),DB(20000,10000))
 assert exc.value.status_code==409
def test_opening_requires_admin_selected_floor():
 for cents in (10000,14999):
  with pytest.raises(ValidationError):
   CycleOpeningCommitRequest(year=2030,amount_cents=cents,
     reason="Explicit test reason",idempotency_key=uuid.uuid4())
 for cents in (15000,20000,32500):
  assert CycleOpeningCommitRequest(year=2030,amount_cents=cents,
   reason="Explicit admin-selected amount",idempotency_key=uuid.uuid4()).amount_cents==cents
def test_single_database_and_no_m37433():
 for path in ["backend/scripts/aistudio_clean_dev_schema_isolated.sh",
              "backend/tests/test_m37433_isolated_clean_schema_ci.py",
              "docs/FR_FINANCE_M37433_ISOLATED_CLEAN_SCHEMA.md"]:
  assert not (ROOT/path).exists()
 workflow=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text()
 assert "M37433 — esquema isolado" not in workflow
 assert "M37434" in workflow
 prompt=(ROOT/"docs/FR_FINANCE_PROMPT_M37434_COTAS.md").read_text()
 assert "frcaixinha_aistudio_dev" in prompt
 assert "$HOME/fr-finance" in prompt
 ui=(ROOT/"src/components/CycleOpeningPreviewPanel.tsx").read_text()
 assert "setAmount]=useState('')" in ui
 assert 'placeholder="Digite o valor escolhido"' in ui
