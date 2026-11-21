"""M39056 — testes da investigação de senha/verifier, sem PostgreSQL real."""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.scripts import frfinance_m39056_verifier_connection_diag as m


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakePG:
    def __init__(self, *, role=m.OWNER, canlogin=True, superuser=False,
                 bypass=False, expired=False, connect=True, password=True,
                 connlimit=-1):
        self.role = role
        self.canlogin = canlogin
        self.superuser = superuser
        self.bypass = bypass
        self.expired = expired
        self.connect = connect
        self.password = password
        self.connlimit = connlimit
        self.statements = []

    def transaction(self):
        return nullcontext()

    def execute(self, sql, args=None):
        self.statements.append((sql, args))
        if sql == "SET TRANSACTION READ ONLY":
            return Result(None)
        if "SELECT current_database(),session_user,host" in sql:
            return Result((m.DB, m.OWNER, "127.0.0.1", 5433,
                           m.DATA_DIRECTORY, 180006, "on"))
        if "FROM pg_roles" in sql:
            expiry = (datetime.now(timezone.utc) +
                      timedelta(days=(-1 if self.expired else 3)))
            return Result((self.canlogin, self.superuser, self.bypass,
                           expiry, self.connlimit))
        if "has_database_privilege" in sql:
            return Result((self.connect,))
        if "FROM pg_authid" in sql:
            return Result((self.password,))
        if "SELECT current_database(),session_user,current_user" in sql:
            return Result((m.DB, m.ROLE, m.ROLE,
                           "127.0.0.1", 5433, 180006, "on"))
        raise AssertionError("UNEXPECTED_SQL")


def test_metadata_original_pg18_readonly():
    c = FakePG()
    result = m.inspect_owner_metadata(c)
    assert all(result.values())
    assert c.statements[0][0] == "SET TRANSACTION READ ONLY"
    assert all(sql == "SET TRANSACTION READ ONLY" or sql.startswith("SELECT ")
               for sql, _ in c.statements)
    assert c.statements[-1][1] == (m.ROLE,)


@pytest.mark.parametrize("flag", ["canlogin", "connect", "password"])
def test_deny_missing_role_requirements(flag):
    c = FakePG(**{flag: False})
    result = m.inspect_owner_metadata(c)
    assert not all(result.values())


@pytest.mark.parametrize("flag", ["superuser", "bypass", "expired"])
def test_deny_privilege_or_expired_role(flag):
    c = FakePG(**{flag: True})
    result = m.inspect_owner_metadata(c)
    assert not all(result.values())


def test_deny_zero_connections():
    result = m.inspect_owner_metadata(FakePG(connlimit=0))
    assert result["connection_limit_not_zero"] is False


def test_verified_connection_readonly():
    c = FakePG(role=m.ROLE)
    m.verify_verifier_connection(c)
    assert c.statements[0][0] == "SET TRANSACTION READ ONLY"
    assert all(sql == "SET TRANSACTION READ ONLY" or sql.startswith("SELECT ")
               for sql, _ in c.statements)


@pytest.mark.parametrize(("sqlstate","raw","expected"), [
    ("28P01", "", "INVALID_PASSWORD"),
    (None, "FATAL: password authentication failed for user 'test'", "INVALID_PASSWORD"),
    (None, "FATAL: no pg_hba.conf entry", "PG_HBA_REJECTED"),
    ("42501", "permission denied", "AUTHORIZATION_OR_HBA_REJECTED"),
    (None, "permission denied for database", "DATABASE_CONNECT_DENIED"),
    ("53300", "", "CONNECTION_CAPACITY"),
    (None, "connection refused", "PG18_NOT_REACHABLE"),
    (None, "timeout expired", "CONNECTION_TIMEOUT"),
    (None, "unclassified reason", "CONNECTION_REJECTED_UNCLASSIFIED"),
])
def test_errors_classified_without_displaying_raw_exception(sqlstate, raw, expected):
    exc = RuntimeError(raw)
    exc.sqlstate = sqlstate
    assert m.classify_connection_failure(exc) == expected
    assert "test" not in m.classify_connection_failure(exc)


def test_source_no_credential_exposure_or_mutation():
    code = (Path(__file__).resolve().parents[1] /
            "scripts/frfinance_m39056_verifier_connection_diag.py").read_text()
    assert 'AI_STUDIO_APPROVED_SHA' not in code or "verify_original()" in code
    assert "getpass.getpass" in code
    assert "default_transaction_read_only=on" in code
    assert "SET TRANSACTION READ ONLY" in code
    assert "rolpassword IS NOT NULL" in code
    assert "classify_connection_failure(exc)" in code
    assert "print(str(exc))" not in code
    assert "print(password)" not in code
    for command in ("INSERT INTO ", "UPDATE public.", "DELETE FROM public.",
                    "ALTER ROLE ", "GRANT SELECT ", "CREATE DATABASE ",
                    "uvicorn.run(", "subprocess.Popen(", "os.system("):
        assert command not in code
