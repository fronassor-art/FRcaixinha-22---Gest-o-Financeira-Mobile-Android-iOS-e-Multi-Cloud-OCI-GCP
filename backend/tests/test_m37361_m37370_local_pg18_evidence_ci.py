"""M37370: PG18 identity guard, catalog-only inspection, zero live changes."""
from dataclasses import replace
from pathlib import Path
import importlib.util
import pytest

from app.local_pg18_evidence_readonly import (
    DBNAME,ROLE,PORT,PGDATA,LocalEvidenceBlocked,LocalEvidence,
    IDENTITY_SQL,LIFECYCLE_SQL,ROUND_INDEX_SQL,PARITY_SQL,INBOX_SQL,PRICE_SQL,
    audit_local_catalog,format_local_evidence,
)
ROOT=Path(__file__).resolve().parents[2]
class DB:
    def __init__(self,vals=None):
        self.vals=list(vals if vals is not None else [
            (DBNAME,ROLE,PORT,180006,PGDATA,"on"),
            (True,),(True,),(True,),(True,),(True,),
        ])
        self.sql=[]
    def execute(self,sql):
        self.sql.append(sql)
        outer=self
        class R:
            def fetchone(self):
                return outer.vals.pop(0)
        return R()

def auth_stub(conn):
    return ("A","B","C","D","E","F")

def test_all_readonly_catalog_signals_present():
    db=DB()
    r=audit_local_catalog(db,auth_stub)
    assert (r.lifecycle,r.synthetic_parity,r.inbox,r.price_043,r.auth_baseline)==(True,)*5
    assert not r.db_writes and not r.users_authorized and not r.payments_authorized
    assert len(db.sql)==6
    assert db.sql==[IDENTITY_SQL,LIFECYCLE_SQL,ROUND_INDEX_SQL,PARITY_SQL,INBOX_SQL,PRICE_SQL]

@pytest.mark.parametrize("index,value",[
    (0,("wrong",ROLE,PORT,180006,PGDATA,"on")),
    (0,(DBNAME,"other",PORT,180006,PGDATA,"on")),
    (0,(DBNAME,ROLE,5432,180006,PGDATA,"on")),
    (0,(DBNAME,ROLE,PORT,170000,PGDATA,"on")),
    (0,(DBNAME,ROLE,PORT,180006,"/other", "on")),
    (0,(DBNAME,ROLE,PORT,180006,PGDATA,"off")),
    (0,(DBNAME,ROLE,True,180006,PGDATA,"on")),
])
def test_wrong_db_identity_rejected_before_schema_queries(index,value):
    db=DB()
    db.vals[index]=value
    with pytest.raises(LocalEvidenceBlocked,match="IDENTITY_OR_READ_ONLY_DENIED"):
        audit_local_catalog(db,auth_stub)
    assert len(db.sql)==1

@pytest.mark.parametrize("index", [1,2,3,4,5])
def test_any_missing_catalog_signal_reported_unverified(index):
    vals=DB().vals
    vals[index]=(False,)
    result=audit_local_catalog(DB(vals),auth_stub)
    flags=(result.lifecycle,result.synthetic_parity,result.inbox,result.price_043)
    assert not all(flags)
    assert "NOT_ATTESTED" in "\n".join(format_local_evidence(result))

@pytest.mark.parametrize("broken",[(None,),("true",),(),(1,)])
def test_malformed_catalog_response_fails_closed(broken):
    vals=DB().vals
    vals[1]=broken
    with pytest.raises(LocalEvidenceBlocked,match="CATALOG_RESULT_INVALID"):
        audit_local_catalog(DB(vals),auth_stub)

def test_auth_checker_exception_blocks_without_leak():
    def broken(conn):
        raise RuntimeError("DO NOT LEAK PASSWORD")
    with pytest.raises(LocalEvidenceBlocked,match="AUTH_BASELINE_NOT_ATTESTED"):
        audit_local_catalog(DB(),broken)

def test_auth_checker_missing_evidence_does_not_pass():
    result=audit_local_catalog(DB(),lambda c:())
    assert not result.auth_baseline
    assert "M37370_AUTH_BASELINE=NOT_ATTESTED" in format_local_evidence(result)

def test_passwords_and_rows_not_in_output():
    result=audit_local_catalog(DB(),auth_stub)
    output="\n".join(format_local_evidence(result))
    for forbidden in ("ocid1.","password_hash","SELECT *","frc_ai_owner","127.0.0.1",
                      "BEGIN PRIVATE KEY"):
        assert forbidden not in output
    assert "M37370_LOCAL_043=STRUCTURAL_PRESENT" in output

def test_only_catalog_selects_and_no_sql_mutations():
    for query in (IDENTITY_SQL,LIFECYCLE_SQL,ROUND_INDEX_SQL,PARITY_SQL,INBOX_SQL,PRICE_SQL):
        assert query.strip().startswith("SELECT")
        for unsafe in ("INSERT INTO","UPDATE public.","DELETE FROM","ALTER TABLE",
                       "DROP TABLE","TRUNCATE","pg_read_file("):
            assert unsafe not in query

def test_termux_script_refuses_unapproved_repo_and_keeps_password_hidden(capsys,monkeypatch):
    path=ROOT/"backend/scripts/aistudio_local_pg18_evidence_readonly.py"
    spec=importlib.util.spec_from_file_location("m37370_script",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module,"check_repo",lambda: (_ for _ in ()).throw(
        LocalEvidenceBlocked("LOCAL_REPOSITORY_NOT_SYNCED")))
    assert module.main()==2
    out=capsys.readouterr().out
    assert "LOCAL_REPOSITORY_NOT_SYNCED" in out
    src=path.read_text()
    for phrase in ("getpass.getpass","default_transaction_read_only=on",
                   "LOCAL_PROJECT_PATH_MISMATCH","M37370_DB_WRITES=NONE"):
        assert phrase in src
    for unsafe in ("pg_dump","pg_restore","psql -f","CREATE TABLE","ALTER TABLE",
                   "subprocess.run(","apply_migration(","terraform apply"):
        assert unsafe not in src
