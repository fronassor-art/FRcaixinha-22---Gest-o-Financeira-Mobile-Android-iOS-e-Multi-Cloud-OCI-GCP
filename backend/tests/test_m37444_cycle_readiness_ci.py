"""M37444 original-DB cycle opening readiness; no SQL mutations."""
from pathlib import Path
import ast
import pytest
from app.dev_m37444_cycle_readiness import (
    EXPECTED,KEYS,EXPECTED_PERMISSIONS,
    CycleReadinessBlocked,validate,examine,report,
    IDENTITY_SQL,READINESS_SQL,PERMISSIONS_SQL,
)
ROOT=Path(__file__).resolve().parents[2]
OK=EXPECTED[:9]+(79,)+EXPECTED[10:]
class Cursor:
 def __init__(self,row):self.row=row
 def fetchone(self):return self.row
class DB:
 def __init__(self,counts=OK,permissions=EXPECTED_PERMISSIONS,version=180006):
  self.counts=counts;self.permissions=permissions;self.version=version
 def execute(self,statement):
  if statement==IDENTITY_SQL:
   return Cursor(("frcaixinha_aistudio_dev","frc_ai_owner","frc_ai_owner",
    5433,"/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18",
    self.version,"on"))
  if statement==READINESS_SQL:return Cursor(self.counts)
  assert statement==PERMISSIONS_SQL
  return Cursor(self.permissions)
def test_ready_to_preview_without_opening_cycle():
    e=examine(DB())
    result="\n".join(report(e))
    for expected in ("M37444_STATUS=READ_ONLY_PASS",
      "M37444_TENANT_ADMIN=1_ACTIVE",
      "M37444_APP_ROLE_EXECUTE=YES",
      "M37444_CYCLE_OPENING_AUDIT_TRIGGERS=2_ENABLED",
      "M37444_MINIMUM_150_SQL_CONSTRAINTS=2_VALIDATED",
      "M37444_NEW_CYCLE=NOT_CREATED",
      "M37444_DB_WRITES=NONE"):
      assert expected in result
def test_each_financial_or_security_count_blocks_on_drift():
    for index in range(len(OK)):
      if index==9:continue
      modified=list(OK);modified[index]+=1
      with pytest.raises(CycleReadinessBlocked):
        validate(tuple(modified),EXPECTED_PERMISSIONS)
def test_existing_sessions_must_survive():
    with pytest.raises(CycleReadinessBlocked,match="SESSIONS_NOT_PRESENT"):
      validate(OK[:9]+(0,)+OK[10:],EXPECTED_PERMISSIONS)
@pytest.mark.parametrize("permissions",[(False,False,False,False),
   (True,True,False,False),(True,False,True,False),
   (True,False,False,True)])
def test_forged_or_leaky_role_grants_denied(permissions):
    with pytest.raises(CycleReadinessBlocked,match="PRIVILEGES_UNSAFE"):
      validate(OK,permissions)
def test_wrong_cluster_rejected_before_reads():
    with pytest.raises(CycleReadinessBlocked,match="WRONG_OR_WRITABLE"):
      examine(DB(version=170000))
def test_admin_selected_floor_and_no_default_static_contract():
    from app.routers.cycle_contribution_price import CycleOpeningCommitRequest
    from pydantic import ValidationError
    from uuid import uuid4
    for amount in (10000,14999):
      with pytest.raises(ValidationError):
        CycleOpeningCommitRequest(year=2030,amount_cents=amount,
          reason="Explicit administrator cycle opening",idempotency_key=uuid4())
    for amount in (15000,20000,32500):
      p=CycleOpeningCommitRequest(year=2030,amount_cents=amount,
          reason="Explicit administrator cycle opening",idempotency_key=uuid4())
      assert p.amount_cents==amount
    ui=(ROOT/"src/components/CycleOpeningPreviewPanel.tsx").read_text()
    assert "setAmount]=useState('')" in ui
    assert 'placeholder="Digite o valor escolhido"' in ui
def test_local_m37370_structural_attestation_accepts_validated_price_constraints():
    from app.local_pg18_evidence_readonly import PRICE_SQL
    assert "AND NOT co.convalidated" not in PRICE_SQL
    assert "policy_minimum_150_new" in PRICE_SQL
    assert "quota_minimum_150_new" in PRICE_SQL
def test_scripts_have_no_writes_or_auth_tokens():
    script=(ROOT/"backend/scripts/aistudio_m37444_cycle_readiness_readonly.py").read_text()
    app=(ROOT/"backend/app/dev_m37444_cycle_readiness.py").read_text()
    ast.parse(script);ast.parse(app)
    assert "default_transaction_read_only=on" in script
    assert "getpass.getpass" in script
    assert "FR_FINANCE_CYCLE_OPEN_ENABLED" in script
    for forbidden in ("DELETE FROM ","INSERT INTO ","UPDATE public.","ALTER TABLE ",
       "CREATE DATABASE","DROP DATABASE","psql -f","subprocess.run"):
      assert forbidden not in app+script
    assert all(q.strip().startswith("SELECT") for q in (IDENTITY_SQL,READINESS_SQL,PERMISSIONS_SQL))
