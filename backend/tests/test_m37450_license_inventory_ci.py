"""M37450 license inventory: never infer provider payment from SQL alone."""
from pathlib import Path
import ast
import pytest
from app.dev_m37450_license_inventory import (
 COUNTS,SECURITY_EXPECTED,LicenseInventoryBlocked,
 IDENTITY_SQL,LICENSING_SQL,SECURITY_SQL,examine,validate,report,
)
ROOT=Path(__file__).resolve().parents[2]
ZERO=(1,1,2,3,2,2,0,0,0,0,0,0,0,0,0,0,0)
class Cursor:
 def __init__(self,row):self.row=row
 def fetchone(self):return self.row
class Conn:
 def __init__(self,counts=ZERO,sec=SECURITY_EXPECTED,version=180006):
  self.counts=counts;self.sec=sec;self.version=version
 def execute(self,sql):
  if sql==IDENTITY_SQL:
   return Cursor(("frcaixinha_aistudio_dev","frc_ai_owner","frc_ai_owner",
     5433,"/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18",
     self.version,"on"))
  if sql==LICENSING_SQL:return Cursor(self.counts)
  assert sql==SECURITY_SQL
  return Cursor(self.sec)
def test_no_entitlement_is_not_an_activated_license():
 e=examine(Conn())
 r="\n".join(report(e))
 for line in ("M37450_STATUS=READ_ONLY_PASS",
  "M37450_LICENSE_EVIDENCE=NO_ENTITLEMENT_RECORDED",
  "M37450_PRODUCTION_RELEASE=BLOCKED",
  "M37450_PROVIDER_PAID_STATUS=NOT_ATTESTED",
  "M37450_DB_WRITES=NONE"):
  assert line in r
def test_existing_license_record_is_not_provider_proof():
 c=list(ZERO);c[9]=1;c[10]=1;c[11]=1
 r="\n".join(report(validate(tuple(c),SECURITY_EXPECTED)))
 assert "ENTITLEMENT_EXISTS_REQUIRES_INDEPENDENT_PAYMENT_ATTESTATION" in r
 assert "PRODUCTION_RELEASE=BLOCKED" in r
def test_preparations_without_license_cannot_enable_accounts():
 c=list(ZERO);c[6]=2
 r="\n".join(report(validate(tuple(c),SECURITY_EXPECTED)))
 assert "NO_ENTITLEMENT_RECORDED" in r
def test_role_escalation_fails_closed():
 for i in range(len(SECURITY_EXPECTED)):
  v=list(SECURITY_EXPECTED);v[i]=2 if i==0 else not v[i]
  with pytest.raises(LicenseInventoryBlocked):
   validate(ZERO,tuple(v))
@pytest.mark.parametrize("idx",[0,1,2,12,13,14,15,16])
def test_modified_identity_or_financial_state_blocks(idx):
 c=list(ZERO);c[idx]+=1
 with pytest.raises(LicenseInventoryBlocked):
  validate(tuple(c),SECURITY_EXPECTED)
def test_authz_readonly_pg18_identity():
 with pytest.raises(LicenseInventoryBlocked,match="WRONG_OR_WRITABLE_PG18"):
  examine(Conn(version=170009))
def test_zero_write_license_script():
 script=(ROOT/"backend/scripts/aistudio_m37450_license_inventory_readonly.py").read_text()
 core=(ROOT/"backend/app/dev_m37450_license_inventory.py").read_text()
 ast.parse(script);ast.parse(core)
 assert "default_transaction_read_only=on" in script
 assert "getpass.getpass" in script
 for forbidden in ("DELETE FROM ","UPDATE public.","INSERT INTO ","TRUNCATE ",
      "CREATE DATABASE","DROP DATABASE","GRANT ","ALTER TABLE ","pg_restore"):
  assert forbidden not in script+core
