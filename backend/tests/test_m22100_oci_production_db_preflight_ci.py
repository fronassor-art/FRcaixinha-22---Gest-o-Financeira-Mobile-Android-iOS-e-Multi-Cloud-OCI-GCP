"""M22100 OCI DB preflight: no network, only mock Pg catalogs."""
import pytest
from app.oci_production_db_preflight import (
    inspect_role,audit_production_db,DbPreflightBlocked,ROLES,TABLES)
from test_m22000_production_auth_gate_ci import safe_env

class Result:
    def __init__(self,value):self.value=value
    def fetchone(self):return self.value
    def fetchall(self):return self.value

class Fake:
    def __init__(self,role):
        self.role=role
        self.identity=("frfinance_prod",role,180006,"on")
        self.tls=(True,)
        self.flags=(True,False,False,False,False,False)
        self.rls=[(name,True,True) for name in TABLES]
        self.grants={
            "frc_ai_app":(False,False,False,False,False,False),
            "frc_ai_auth":(False,False,True,False,True,True),
            "frc_ai_verifier":(True,False,False,True,False,False),
        }[role]
        self.calls=[]
    def execute(self,q):
        self.calls.append(q)
        if "current_database()" in q:return Result(self.identity)
        if "pg_stat_ssl" in q:return Result(self.tls)
        if "FROM pg_roles" in q:return Result(self.flags)
        if "JOIN pg_namespace" in q:return Result(self.rls)
        if "has_column_privilege" in q:return Result(self.grants)
        raise AssertionError("unknown SQL")

def test_three_roles_probed_readonly():
    env=safe_env()
    env["FR_FINANCE_DB_PREFLIGHT_CONFIRM"]="READ_ONLY_OCI"
    checked=[]
    class Context:
        def __init__(self,db):self.db=db
        def __enter__(self):return self.db
        def __exit__(self,*_):return False
    def connect(dsn,**kwargs):
        assert kwargs["connect_timeout"]==5
        assert "default_transaction_read_only=on" in kwargs["options"]
        role=next(role for role in ROLES if "://"+role+":" in dsn)
        db=Fake(role)
        checked.append(db)
        return Context(db)
    assert audit_production_db(env,connect)==ROLES
    assert len(checked)==3
    assert all(len(c.calls)==5 for c in checked)
    assert all(all(q.startswith("SELECT ") for q in c.calls) for c in checked)

def test_default_closed():
    with pytest.raises(DbPreflightBlocked):
        audit_production_db(safe_env(),lambda *args,**kwargs:None)

@pytest.mark.parametrize("role",ROLES)
@pytest.mark.parametrize("change,value",[
    ("identity",("frfinance_prod","frc_ai_app",170000,"on")),
    ("tls",(False,)),
    ("flags",(True,False,True,False,False,False)),
    ("rls",[(n,True,False) for n in TABLES]),
    ("rls",[(n,True,True) for n in TABLES if n!="users"]),
    ("grants",(True,True,True,True,True,True)),
])
def test_unsafe_catalog_fails(role,change,value):
    db=Fake(role)
    setattr(db,change,value)
    with pytest.raises(DbPreflightBlocked):
        inspect_role(db,role,"frfinance_prod")

@pytest.mark.parametrize("role",ROLES)
def test_wrong_db_and_role_fail(role):
    db=Fake(role)
    with pytest.raises(DbPreflightBlocked):
        inspect_role(db,role,"another_prod")
