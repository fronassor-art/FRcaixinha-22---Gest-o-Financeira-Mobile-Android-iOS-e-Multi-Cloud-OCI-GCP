"""Synthetic-only tests of M37443 read-only post-reset attestation."""
from pathlib import Path
import ast
import pytest
from app.dev_m37443_post_reset import CORE_EXPECTED,EXTRA_EXPECTED,EXTRA_KEYS,validate,report,AuditBlocked,examine,IDENTITY,CORE,EXTRA
ROOT=Path(__file__).resolve().parents[2]
OK=(79,)+EXTRA_EXPECTED[1:]
class Cursor:
 def __init__(self,row):self.row=row
 def fetchone(self):return self.row
class FakeConn:
 def __init__(self,version=180006,extra=OK):self.version=version;self.extra=extra
 def execute(self,query):
  if query==IDENTITY:
   return Cursor(("frcaixinha_aistudio_dev","frc_ai_owner","frc_ai_owner",
    5433,"/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18",
    self.version,"on"))
  if query==CORE:return Cursor(CORE_EXPECTED)
  assert query==EXTRA
  return Cursor(self.extra)
def test_expected_reset_is_read_only_verified():
 x=examine(FakeConn())
 out="\n".join(report(x))
 assert "M37443_STATUS=READ_ONLY_PASS" in out
 assert "M37443_AUDIT_EVENTS=6" in out
 assert "M37443_SESSIONS_COUNT=79" in out
 assert "M37443_MINIMUM_150_CHECKS=2_VALIDATED" in out
 assert "M37443_DB_WRITES=NONE" in out
def test_extra_count_mismatch_always_fails():
 for i in range(1,15):
  changed=list(OK);changed[i]+=1
  with pytest.raises(AuditBlocked):validate(CORE_EXPECTED,tuple(changed))
def test_core_count_mismatch_always_fails():
 for i in range(10):
  changed=list(CORE_EXPECTED);changed[i]+=1
  with pytest.raises(AuditBlocked):validate(tuple(changed),OK)
def test_sessions_must_exist():
 with pytest.raises(AuditBlocked,match="SESSION_RECORDS_MISSING"):
  validate(CORE_EXPECTED,(0,)+OK[1:])
@pytest.mark.parametrize("invalid",[None,[],(1,),("1",)*10,(-1,)*10])
def test_malformed_core_rejected(invalid):
 with pytest.raises(AuditBlocked):validate(invalid,OK)
def test_wrong_pg18_version_rejected():
 with pytest.raises(AuditBlocked,match="WRONG_OR_NON_READONLY_PG18"):
  examine(FakeConn(version=170006))
def test_code_only_reads_existing_db():
 script=(ROOT/"backend/scripts/aistudio_m37443_post_reset_readonly.py").read_text()
 core=(ROOT/"backend/app/dev_m37443_post_reset.py").read_text()
 ast.parse(script);ast.parse(core)
 assert "default_transaction_read_only=on" in script
 assert "getpass.getpass" in script
 assert "frcaixinha_aistudio_dev" in script
 for word in ("DELETE FROM ","INSERT INTO ","UPDATE public.","ALTER TABLE ",
              "DROP DATABASE","CREATE DATABASE","pg_restore","subprocess"):
  assert word not in script+core
