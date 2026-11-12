"""FR Finance M39055 — CI sem credenciais, sockets ou banco original."""
from contextlib import nullcontext
from pathlib import Path

import pytest
from backend.scripts import frfinance_m39055_auth_roles_readonly as m


class Response:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = many if many is not None else []
    def fetchone(self):
        return self.one
    def fetchall(self):
        return self.many


class FakeDB:
    def __init__(self, role, *, no_select=False, superuser=False, no_functions=False):
        self.role=role
        self.no_select=no_select
        self.superuser=superuser
        self.no_functions=no_functions
        self.statements=[]

    def transaction(self):
        return nullcontext()

    def execute(self, sql, args=None):
        self.statements.append((sql,args))
        if sql == "SET TRANSACTION READ ONLY":
            return Response()
        if sql.startswith("SELECT current_database(),current_user"):
            return Response(one=(m.DB,self.role,self.role,"127.0.0.1",5433,
                                 m.DATA_DIRECTORY,180006,"on"))
        if "FROM pg_roles" in sql:
            return Response(one=(True,self.superuser,False))
        if "SELECT has_table_privilege" in sql:
            return Response(one=(not self.no_select,))
        if "SELECT DISTINCT p.proname" in sql:
            names=[] if self.no_functions else m.AUTH_FUNCTIONS
            return Response(many=[(name,) for name in names])
        raise AssertionError("UNEXPECTED_SQL: " + sql[:36])


@pytest.mark.parametrize("role",m.ROLES)
def test_each_role_connects_to_original_pg_and_checks_privileges(role):
    db=FakeDB(role)
    result=m.role_connection_audit(db,role)
    assert result["role"]==role
    assert result["tables"]==2
    assert result["auth_functions"]==(len(m.AUTH_FUNCTIONS) if role=="frc_ai_auth" else 0)
    assert db.statements[0][0]=="SET TRANSACTION READ ONLY"
    assert all(s=="SET TRANSACTION READ ONLY" or s.startswith("SELECT ")
               for s,_ in db.statements)


def test_auth_role_missing_grant_fails_closed():
    with pytest.raises(RuntimeError,match="MISSING_ROLE_TABLE_GRANT"):
        m.role_connection_audit(FakeDB("frc_ai_auth",no_select=True),"frc_ai_auth")


def test_auth_role_missing_function_fails_closed():
    with pytest.raises(RuntimeError,match="AUTH_FUNCTION_EXECUTE_GRANTS_INCOMPLETE"):
        m.role_connection_audit(FakeDB("frc_ai_auth",no_functions=True),"frc_ai_auth")


def test_role_is_never_superuser_or_rls_bypass():
    with pytest.raises(RuntimeError,match="ROLE_LOGIN_OR_PRIVILEGE_UNSAFE"):
        m.role_connection_audit(FakeDB("frc_ai_app",superuser=True),"frc_ai_app")


def test_new_role_not_allowed():
    with pytest.raises(RuntimeError,match="UNAPPROVED_ROLE"):
        m.role_connection_audit(FakeDB("frc_ai_owner"),"frc_ai_owner")


def test_no_original_data_modification_or_secret_print():
    code=(Path(__file__).resolve().parents[1]/
          "scripts/frfinance_m39055_auth_roles_readonly.py").read_text()
    assert "getpass(" in code
    assert "default_transaction_read_only=on" in code
    assert "SET TRANSACTION READ ONLY" in code
    assert "verify_original()" in code
    assert "get_rls_db_connection" not in code
    for blocked in (
        "CREATE DATABASE", "ALTER ROLE ", "DROP TABLE", "INSERT INTO ",
        "UPDATE public.", "DELETE FROM public.", "print(password",
        "/root/fr-finance", "git clone", "uvicorn.run(",
        "os.system(", "subprocess.Popen("
    ):
        assert blocked not in code
