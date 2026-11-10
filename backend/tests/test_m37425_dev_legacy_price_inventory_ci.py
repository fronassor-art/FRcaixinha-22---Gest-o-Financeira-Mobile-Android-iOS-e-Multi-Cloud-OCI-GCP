"""Read-only dev price inventory contract, no PII or DML."""
import pytest
from pathlib import Path
from app.dev_legacy_amount_audit import ITEMS,Evidence,DevPriceAuditBlocked,inspect,report
ROOT=Path(__file__).resolve().parents[2]
def prepared(values):
 values=list(values)
 def scalar(q):
  assert q.startswith("SELECT ")
  return values.pop(0)
 return scalar
def test_clean_database_not_imported_from_dev():
 r=inspect(prepared([0]*8+[False]))
 assert r.clean() and not r.financially_sensitive()
 assert "M37425_DEV_RESET=NOT_REQUIRED" in report(r)
def test_old_policy_and_12_months_are_identified():
 r=inspect(prepared([1,1,12,1,0,0,0,0,False]))
 assert not r.clean()
 out="\n".join(report(r))
 assert "M37425_CONTRIBUTIONS_BELOW=12" in out
 assert "M37425_DEV_RESET=REQUIRED" in out
 assert "M37425_AUDIT_DELETION=NOT_AUTHORIZED" in out
 assert "M37425_DB_WRITES=NO" in out
def test_paid_records_or_ledger_need_independent_review():
 r=inspect(prepared([0,0,0,0,1,0,1,0,True,1]))
 assert r.financially_sensitive() and not r.clean()
@pytest.mark.parametrize("item",[None,-1,1.5,"12"])
def test_invalid_counts_never_attested(item):
 with pytest.raises(DevPriceAuditBlocked):
  inspect(prepared([item]+[0]*7+[False]))
def test_only_selects_and_hidden_password():
 for _,sql in ITEMS:
  assert sql.startswith("SELECT count(*)")
  assert not any(x in sql for x in ["DELETE ","UPDATE ","INSERT ","DROP ","ALTER ","TRUNCATE "])
 s=(ROOT/"backend/scripts/aistudio_dev_legacy_price_inventory.py").read_text()
 assert "getpass.getpass" in s and "default_transaction_read_only=on" in s
 assert "M37425_DB_WRITES=NO" in s
 assert all(x not in s for x in ("DELETE FROM","UPDATE public.","ALTER TABLE","pg_restore"))
