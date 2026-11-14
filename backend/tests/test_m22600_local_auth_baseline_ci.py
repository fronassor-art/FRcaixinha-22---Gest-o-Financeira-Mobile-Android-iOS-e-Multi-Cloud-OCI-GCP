"""M22600: catalog-only checks over mocked role boundaries."""
import inspect
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import aistudio_auth_baseline_readonly as b

class Db:
    def __init__(self, answers=None):
        self.answers=list(answers) if answers is not None else [True]*6
        self.sql=[]
    def execute(self,query):
        self.sql.append(query)
        class Result:
            def __init__(self,v):self.v=v
            def fetchone(self):return (self.v,)
        return Result(self.answers.pop(0))

def test_every_boundary_check_passes_without_mutations():
    db=Db()
    assert len(b.inspect_local_auth_baseline(db))==6
    assert len(db.sql)==6
    for sql in db.sql:
        assert sql.strip().startswith("SELECT")
        for banned in ("INSERT INTO","ALTER TABLE","DROP TABLE",
                       "UPDATE public", "DELETE FROM"):
            assert banned not in sql

@pytest.mark.parametrize("index",list(range(6)))
def test_one_missing_boundary_fails_closed(index):
    flags=[True]*6
    flags[index]=False
    with pytest.raises(b.BaselineBlocked):
        b.inspect_local_auth_baseline(Db(flags))

def test_malformed_catalog_response_fails_closed():
    db=Db([None]+[True]*5)
    with pytest.raises(b.BaselineBlocked):
        b.inspect_local_auth_baseline(db)

def test_does_not_read_auth_data_or_write_secrets():
    source=inspect.getsource(b)
    assert "password_hash','SELECT')" in source
    assert "SELECT password_hash " not in source
    assert "SELECT * FROM public.credentials" not in source
    assert "INSERT INTO public." not in source
    assert "UPDATE public." not in source
    assert "getpass.getpass" in source
    assert "default_transaction_read_only=on" in source
    assert "M22600_MIGRATION_001_027_EXECUTION_HISTORY=UNVERIFIED" in source
