"""M37436: scope of legacy cycle FK references, no PG mutation."""
import ast
from pathlib import Path
import pytest
from psycopg.sql import Composed
from app.dev_legacy_cycle_scope_readonly import (
 SCOPE_SQL,CYCLE_FKS,CycleScopeBlocked,cycle_count_query,examine,report,
)
ROOT=Path(__file__).resolve().parents[2]
class Cursor:
 def __init__(self,row=None,rows=None):self.row=row;self.rows=rows
 def fetchone(self):return self.row
 def fetchall(self):return self.rows
class DB:
 def __init__(self,scope=(1,1,1,1,12,1,1,0,0,0),fks=None,counts=None):
  self.scope=scope
  self.fks=fks if fks is not None else [
   ("contributions","cycles","contrib_cycle_fk",["cycle_id"],["id"]),
   ("policies","cycles","policy_cycle_fk",["cycle_id"],["id"]),
  ]
  self.counts=list(counts if counts is not None else [12,1])
 def execute(self,q):
  if q==SCOPE_SQL:return Cursor(self.scope)
  if q==CYCLE_FKS:return Cursor(rows=self.fks)
  assert isinstance(q,Composed)
  return Cursor((self.counts.pop(0),))
def test_only_counts_and_original_database():
 e=examine(DB())
 assert e.counts[:2]==(1,1)
 assert not e.review_required
 out="\n".join(report(e))
 assert "M37436_CONTRIBUTIONS_IN_LEGACY_CYCLE=12" in out
 assert "M37436_SAFE_TO_PURGE=NOT_AUTHORIZED" in out
 assert "M37436_NEW_DATABASE=NO" in out
 assert "M37436_DATABASE_WRITES=NONE" in out
def test_other_cycle_references_require_review():
 db=DB(fks=[("some_other_table","cycles","fk",["cycle_id"],["id"])],counts=[4])
 assert examine(db).review_required
@pytest.mark.parametrize("scope",[
 (2,1,1,1,12,1,1,0,0,0),
 (1,1,1,1,11,1,1,0,0,0),
 (1,0,1,1,12,1,1,0,0,0),
])
def test_drift_blocks(scope):
 with pytest.raises(CycleScopeBlocked,match="CYCLE_LEGACY_COUNTS_CHANGED"):
  examine(DB(scope=scope))
def test_no_user_supplied_identifiers():
 for bad in ("cycles;DROP","weird name","-bad"):
  with pytest.raises(Exception):
   cycle_count_query(bad,["id"],["id"])
  with pytest.raises(Exception):
   cycle_count_query("policies",[bad],["id"])
@pytest.mark.parametrize("source,target",[(["id"],[]),([],[]),
 (["id"],["id","cycle_id"])])
def test_bad_fk_cardinality(source,target):
 with pytest.raises(CycleScopeBlocked):
  cycle_count_query("policies",source,target)
def test_only_readonly_sql_and_password_hidden():
 code=(ROOT/"backend/app/dev_legacy_cycle_scope_readonly.py").read_text()
 script=(ROOT/"backend/scripts/aistudio_dev_legacy_cycle_scope_readonly.py").read_text()
 ast.parse(code);ast.parse(script)
 assert "default_transaction_read_only=on" in script
 assert "getpass.getpass" in script
 assert "dbname=DBNAME" in script
 for bad in ("INSERT INTO ","DELETE FROM ","UPDATE public.","TRUNCATE ",
             "DROP DATABASE ","CREATE DATABASE ","pg_restore","pg_dump"):
  assert bad not in code+script
