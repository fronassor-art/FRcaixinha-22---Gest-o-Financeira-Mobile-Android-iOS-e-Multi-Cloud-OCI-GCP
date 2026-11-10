"""M37435 CI-only tests, no DB connection and no SQL writes."""
import ast
from pathlib import Path
import pytest
from psycopg.sql import Composed
from app.dev_legacy_dependency_readonly import (
 BASELINE,TRIGGERS,FKS,DependencyBlocked,examine,count_sql,report
)
ROOT=Path(__file__).resolve().parents[2]
class Result:
 def __init__(self,row,allrows=None):self.row=row;self.allrows=allrows
 def fetchone(self):return self.row
 def fetchall(self):return self.allrows
class DB:
 def __init__(self,counts=(1,1,12,1,0,0,0,0),triggers=2,refs=None,matches=None):
  self.counts=counts;self.triggers=triggers
  self.refs=refs if refs is not None else [
   ("contributions","policies","fk_policy",["policy_id"],["id"]),
   ("cycle_contribution_price_audit","policies","fk_audit_policy",["policy_id"],["id"])]
  self.matches=list(matches if matches is not None else [0,1]);self.n=0
 def execute(self,q):
  self.n+=1
  if q==BASELINE:return Result(self.counts)
  if q==TRIGGERS:return Result((self.triggers,))
  if q==FKS:return Result(None,self.refs)
  assert isinstance(q,Composed)
  return Result((self.matches.pop(0),))
def test_fk_counts_are_readonly_and_non_authorizing():
 db=DB()
 e=examine(db)
 assert db.n==5
 assert e.counts[:4]==(1,1,12,1)
 assert sum(l.matches for l in e.links)==1
 out="\n".join(report(e))
 assert "M37435_STATUS=READ_ONLY_PASS" in out
 assert "M37435_FK_MATCHES=1" in out
 assert "M37435_NON_FK_RELATIONSHIPS=NOT_ATTESTED" in out
 assert "M37435_AUDIT_DELETION=NOT_AUTHORIZED" in out
def test_no_fk_not_equivalent_to_clean_data():
 r=report(examine(DB(refs=[])))
 assert "M37435_FK_MATCHES=0" in r
 assert "M37435_NON_FK_RELATIONSHIPS=NOT_ATTESTED" in r
@pytest.mark.parametrize("counts",[
 (0,1,12,1,0,0,0,0),(1,1,11,1,0,0,0,0),
 (1,1,12,0,0,0,0,0),(1,1,12,1,1,0,0,0),
])
def test_baseline_or_money_trace_blocks(counts):
 with pytest.raises(DependencyBlocked):
  examine(DB(counts=counts))
def test_audit_trigger_required():
 with pytest.raises(DependencyBlocked,match="IMMUTABLE"):
  examine(DB(triggers=1))
@pytest.mark.parametrize("name",["x;DROP","-x","x.y","x z"])
def test_no_dynamic_untrusted_sql_identifier(name):
 with pytest.raises(DependencyBlocked):count_sql(name,"policies",["id"],["id"])
 with pytest.raises(DependencyBlocked):count_sql("contributions","policies",[name],["id"])
 with pytest.raises(DependencyBlocked):count_sql("contributions",name,["id"],["id"])
def test_unsupported_or_mismatched_fks_denied():
 with pytest.raises(DependencyBlocked):count_sql("x","users",["a"],["b"])
 with pytest.raises(DependencyBlocked):count_sql("x","policies",["a"],[])
def test_only_catalog_select_and_readonly_connection():
 code=(ROOT/"backend/app/dev_legacy_dependency_readonly.py").read_text()
 cli=(ROOT/"backend/scripts/aistudio_dev_legacy_dependencies_readonly.py").read_text()
 ast.parse(code);ast.parse(cli)
 assert "default_transaction_read_only=on" in cli
 assert "getpass.getpass" in cli and "dbname=DBNAME" in cli
 assert "M37435_NEW_DATABASE=NO" in code
 for illegal in ("DELETE FROM ","DROP DATABASE ","TRUNCATE ",
                 "UPDATE public.","INSERT INTO ","pg_restore","pg_dump"):
  assert illegal not in code+cli
